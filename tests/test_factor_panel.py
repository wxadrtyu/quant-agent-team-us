"""Tests for A1 factor_panel — correctness + no look-ahead."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.factor_panel import build_factor_panel  # noqa: E402


def _make_market(db_path: Path, n_days: int = 160, stocks=("000001", "600000")) -> None:
    con = duckdb.connect(str(db_path))
    con.execute("""
        CREATE TABLE market_daily (
            stock_code VARCHAR, trade_date DATE, open DOUBLE, high DOUBLE,
            low DOUBLE, close_adj DOUBLE, volume DOUBLE, amount DOUBLE,
            amplitude DOUBLE, pct_chg DOUBLE, change DOUBLE, turnover_rate DOUBLE
        )
    """)
    rows = []
    for s in stocks:
        price = 10.0
        for d in range(n_days):
            price *= 1.0 + (0.001 * ((d % 7) - 3))  # deterministic wiggle
            date = f"2022-01-{d + 1:02d}" if d < 28 else None
            # use a real incrementing date
            from datetime import date as _date, timedelta
            dt = _date(2022, 1, 3) + timedelta(days=d)
            rows.append((s, dt, price, price, price, price, 1e6, price * 1e6, 1.0, 0.0, 0.0, 2.0))
    con.executemany("INSERT INTO market_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.close()


def test_ret20_matches_manual(tmp_path):
    db = tmp_path / "t.duckdb"
    _make_market(db)
    build_factor_panel(db, add_fundamentals=False)
    con = duckdb.connect(str(db))
    # manual ret_20d for one stock at the last date
    rows = con.execute("""
        WITH m AS (SELECT trade_date, close_adj, row_number() OVER (ORDER BY trade_date) rn
                   FROM market_daily WHERE stock_code='000001')
        SELECT a.trade_date, a.close_adj/b.close_adj - 1 manual, fp.ret_20d
        FROM m a JOIN m b ON b.rn = a.rn - 20
        JOIN factor_panel fp ON fp.stock_code='000001' AND fp.trade_date=a.trade_date
        ORDER BY a.trade_date DESC LIMIT 5
    """).fetchall()
    con.close()
    assert rows, "no overlapping rows to check"
    for _, manual, panel in rows:
        assert abs(manual - panel) < 1e-9


def test_no_lookahead_truncation_invariance(tmp_path):
    """Factor values at dates <= T must be identical whether or not future data exists."""
    full = tmp_path / "full.duckdb"
    trunc = tmp_path / "trunc.duckdb"
    _make_market(full)
    build_factor_panel(full, add_fundamentals=False)

    # truncated copy: drop the last 30 days, rebuild
    con = duckdb.connect(str(full))
    cutoff = con.execute("SELECT max(trade_date) FROM market_daily").fetchone()[0]
    import datetime
    cut = cutoff - datetime.timedelta(days=30)
    rows = con.execute("SELECT * FROM market_daily WHERE trade_date <= ?", [cut]).fetchall()
    cols = [c[0] for c in con.execute("DESCRIBE market_daily").fetchall()]
    con.close()

    con2 = duckdb.connect(str(trunc))
    con2.execute(f"CREATE TABLE market_daily ({', '.join(c + ' ' + t for c, t in [(c, 'VARCHAR' if i==0 else ('DATE' if i==1 else 'DOUBLE')) for i, c in enumerate(cols)])})")
    con2.executemany("INSERT INTO market_daily VALUES (" + ",".join(["?"] * len(cols)) + ")", rows)
    con2.close()
    build_factor_panel(trunc, add_fundamentals=False)

    cf = duckdb.connect(str(full))
    ct = duckdb.connect(str(trunc))
    full_vals = cf.execute(
        "SELECT stock_code, trade_date, ret_20d, vol_20d, px_to_ma20 FROM factor_panel "
        "WHERE trade_date <= ? ORDER BY 1,2", [cut]
    ).fetchall()
    trunc_vals = ct.execute(
        "SELECT stock_code, trade_date, ret_20d, vol_20d, px_to_ma20 FROM factor_panel ORDER BY 1,2"
    ).fetchall()
    cf.close()
    ct.close()
    assert len(full_vals) == len(trunc_vals)
    for a, b in zip(full_vals, trunc_vals):
        assert a[0] == b[0] and a[1] == b[1]
        for x, y in zip(a[2:], b[2:]):
            if x is None or y is None:
                assert x is y
            else:
                assert abs(x - y) < 1e-9, f"look-ahead leak at {a[1]}"
