#!/usr/bin/env python3
"""B1 ingest — load akshare fundamentals parquet into duckdb, then rebuild factor_panel
so value(ep,bp)/quality(roe) factors light up. Run after fetch_akshare_fundamentals.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def ingest(db_path: str, src: str = "data/akshare_fundamental") -> dict:
    val_glob = str((ROOT / src / "valuation" / "*.parquet")).replace("\\", "/")
    roe_glob = str((ROOT / src / "roe" / "*.parquet")).replace("\\", "/")
    con = duckdb.connect(db_path)

    con.execute("DROP TABLE IF EXISTS valuation_daily")
    con.execute(f"""
        CREATE TABLE valuation_daily AS
        SELECT CAST(stock_code AS VARCHAR) stock_code,
               CAST(trade_date AS DATE) trade_date,
               CAST(pe_ttm AS DOUBLE) pe_ttm,
               CAST(pb AS DOUBLE) pb
        FROM read_parquet('{val_glob}', union_by_name=true)
        WHERE trade_date IS NOT NULL
    """)
    con.execute("DROP TABLE IF EXISTS financials")
    con.execute(f"""
        CREATE TABLE financials AS
        SELECT CAST(stock_code AS VARCHAR) stock_code,
               CAST(report_date AS DATE) report_date,
               CAST(roe AS DOUBLE) roe
        FROM read_parquet('{roe_glob}', union_by_name=true)
        WHERE report_date IS NOT NULL
    """)
    v = con.execute("SELECT count(*), count(DISTINCT stock_code) FROM valuation_daily").fetchone()
    f = con.execute("SELECT count(*), count(DISTINCT stock_code) FROM financials").fetchone()
    con.close()

    from quant_agent_team.factor_panel import build_factor_panel
    panel = build_factor_panel(db_path, add_fundamentals=True)
    return {
        "valuation_rows": v[0], "valuation_stocks": v[1],
        "financials_rows": f[0], "financials_stocks": f[1],
        "factor_panel": {k: panel[k] for k in ("rows", "stocks", "columns", "fundamentals_joined")},
    }


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "quant.duckdb")
    print(json.dumps(ingest(db), ensure_ascii=False, indent=2))
