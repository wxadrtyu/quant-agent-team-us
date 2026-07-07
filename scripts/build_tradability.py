#!/usr/bin/env python3
"""B2 (suspension part) — derive is_suspended from trading-calendar gaps.

Network-free. A stock is "suspended" on a market trading day that falls inside its
listed range [first_seen, last_seen] but has no row in market_daily. Builds table
`suspension_daily(stock_code, trade_date)` and a coverage summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def build(db_path: str) -> dict:
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE OR REPLACE TABLE suspension_daily AS
        WITH calendar AS (SELECT DISTINCT trade_date FROM market_daily),
        ranges AS (
            SELECT stock_code, min(trade_date) first_seen, max(trade_date) last_seen
            FROM market_daily GROUP BY stock_code
        ),
        listed_days AS (
            SELECT r.stock_code, c.trade_date
            FROM ranges r JOIN calendar c
              ON c.trade_date >= r.first_seen AND c.trade_date <= r.last_seen
        )
        SELECT l.stock_code, l.trade_date
        FROM listed_days l
        LEFT JOIN market_daily m
          ON m.stock_code = l.stock_code AND m.trade_date = l.trade_date
        WHERE m.stock_code IS NULL
    """)
    n, stocks = con.execute(
        "SELECT count(*), count(DISTINCT stock_code) FROM suspension_daily"
    ).fetchone()
    con.close()
    return {"suspended_rows": n, "stocks_with_suspension": stocks}


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "quant.duckdb")
    print(json.dumps(build(db), ensure_ascii=False, indent=2))
