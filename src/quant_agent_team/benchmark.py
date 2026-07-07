"""A4 helper — fetch & cache A-share index benchmark series (AkShare).

Each index pool is evaluated against its own benchmark (locked decision A7).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

# name -> index code (6-digit). Used by per-universe evaluation (A7).
INDEX_CODES: Dict[str, str] = {
    "csi300": "000300",   # 沪深300
    "csi500": "000905",   # 中证500
    "csi1000": "000852",  # 中证1000
    "sse50": "000016",    # 上证50
    "kc50": "000688",     # 科创50
    "kc100": "000698",    # 科创100
    "bj50": "899050",     # 北证50
}

# Sina symbol (market-prefixed). Sina is the PRIMARY index source: fast (~1s), full
# history, and not subject to the eastmoney throttling we hit. Eastmoney is the fallback.
INDEX_SINA: Dict[str, str] = {
    "csi300": "sh000300", "csi500": "sh000905", "csi1000": "sh000852",
    "sse50": "sh000016", "kc50": "sh000688", "kc100": "sh000698", "bj50": "bj899050",
}


def fetch_index_daily(
    name_or_code: str, start: str = "20220101", end: str = "20261231", retries: int = 3
) -> pd.DataFrame:
    """Return [trade_date, close] for an index. Primary: sina (stock_zh_index_daily);
    fallback: eastmoney (index_zh_a_hist). Resilient to a single provider throttling."""
    import time

    import akshare as ak

    start_ts, end_ts = pd.to_datetime(start), pd.to_datetime(end)

    # primary: sina
    sina_sym = INDEX_SINA.get(name_or_code)
    if sina_sym is not None:
        for attempt in range(retries):
            try:
                df = ak.stock_zh_index_daily(symbol=sina_sym)
                out = df.rename(columns={"date": "trade_date"})[["trade_date", "close"]].copy()
                out["trade_date"] = pd.to_datetime(out["trade_date"])
                out["close"] = out["close"].astype(float)
                out = out[(out["trade_date"] >= start_ts) & (out["trade_date"] <= end_ts)]
                return out.sort_values("trade_date").reset_index(drop=True)
            except Exception:  # noqa: BLE001 - fall through to eastmoney
                time.sleep(1.5 * (attempt + 1))

    # fallback: eastmoney
    code = INDEX_CODES.get(name_or_code, name_or_code)
    last = None
    for attempt in range(retries):
        try:
            df = ak.index_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end)
            out = df.rename(columns={"日期": "trade_date", "收盘": "close"})[["trade_date", "close"]].copy()
            out["trade_date"] = pd.to_datetime(out["trade_date"])
            out["close"] = out["close"].astype(float)
            return out.sort_values("trade_date").reset_index(drop=True)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"index fetch failed for {name_or_code} (sina+eastmoney): {last}")


def load_index_daily(
    name: str,
    db_path: str | Path = "quant.duckdb",
    start: str = "20220101",
    end: str = "20261231",
    refresh: bool = False,
) -> pd.DataFrame:
    """Load an index series from the cached `index_daily` table, fetching it once if
    missing. Cache schema: (index_name, trade_date DATE, close DOUBLE)."""
    import duckdb

    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE IF NOT EXISTS index_daily (index_name VARCHAR, trade_date DATE, close DOUBLE)")
    have = con.execute("SELECT count(*) FROM index_daily WHERE index_name = ?", [name]).fetchone()[0]
    if refresh or have == 0:
        df = fetch_index_daily(name, start, end)
        con.execute("DELETE FROM index_daily WHERE index_name = ?", [name])
        con.executemany(
            "INSERT INTO index_daily VALUES (?, ?, ?)",
            [(name, r.trade_date.date(), float(r.close)) for r in df.itertuples()],
        )
    out = con.execute(
        "SELECT trade_date, close FROM index_daily WHERE index_name = ? ORDER BY trade_date", [name]
    ).fetchdf()
    con.close()
    return out
