#!/usr/bin/env python3
"""Load AkShare hfq per-stock parquet into a freshly typed DuckDB table.

Produces `market_daily` with proper types (DATE / DOUBLE), close = hfq-adjusted close.
This is the clean V5 price foundation that replaces the deleted, contaminated quant.duckdb.

Usage:
    python scripts/ingest_akshare_to_duckdb.py --src data/akshare_hfq --db quant.duckdb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/akshare_hfq")
    ap.add_argument("--db", default="quant.duckdb")
    ap.add_argument("--table", default="market_daily")
    args = ap.parse_args()

    src = (ROOT / args.src).resolve()
    glob = str(src / "*.parquet").replace("\\", "/")
    n_files = len(list(src.glob("*.parquet")))
    if n_files == 0:
        print(f"[error] no parquet files in {src}", flush=True)
        return 1
    print(f"[ingest] {n_files} parquet files from {src} -> {args.db}:{args.table}", flush=True)

    con = duckdb.connect(str((ROOT / args.db).resolve()))
    con.execute(f'DROP TABLE IF EXISTS "{args.table}"')
    con.execute(f"""
        CREATE TABLE "{args.table}" AS
        SELECT
            CAST(stock_code AS VARCHAR)        AS stock_code,
            CAST(trade_date AS DATE)           AS trade_date,
            CAST(open  AS DOUBLE)              AS open,
            CAST(high  AS DOUBLE)              AS high,
            CAST(low   AS DOUBLE)              AS low,
            CAST(close AS DOUBLE)              AS close_adj,   -- hfq adjusted close
            CAST(volume AS DOUBLE)            AS volume,
            CAST(amount AS DOUBLE)            AS amount,
            CAST(amplitude AS DOUBLE)        AS amplitude,
            CAST(pct_chg AS DOUBLE)          AS pct_chg,
            CAST(change AS DOUBLE)           AS change,
            CAST(turnover_rate AS DOUBLE)    AS turnover_rate
        FROM read_parquet('{glob}', union_by_name=true)
    """)

    n, stocks, mn, mx = con.execute(
        f'SELECT count(*), count(DISTINCT stock_code), min(trade_date), max(trade_date) FROM "{args.table}"'
    ).fetchone()
    dups = con.execute(f"""
        SELECT count(*) FROM (
            SELECT stock_code, trade_date FROM "{args.table}"
            GROUP BY 1,2 HAVING count(*) > 1)
    """).fetchone()[0]
    print(f"[done] rows={n:,}  stocks={stocks:,}  dates {mn}..{mx}  dup_keys={dups}", flush=True)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
