#!/usr/bin/env python3
"""B2/B3 ingest — load industry / current-ST / delisted parquet into duckdb tables.
Run after fetch_industry_st_delist.py. Suspension is built separately (build_tradability.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data" / "akshare_meta"


def ingest(db_path: str) -> dict:
    con = duckdb.connect(db_path)
    out = {}
    for name, fname, cols in [
        ("industry", "industry.parquet", "stock_code, industry"),
        ("stock_st", "st_current.parquet", "stock_code, name, is_st"),
        ("delisted", "delisted.parquet", "stock_code, name, exchange"),
    ]:
        p = (META / fname)
        if not p.exists():
            out[name] = "missing"
            continue
        glob = str(p).replace("\\", "/")
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(f"CREATE TABLE {name} AS SELECT {cols} FROM read_parquet('{glob}')")
        out[name] = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    con.close()
    return out


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "quant.duckdb")
    print(json.dumps(ingest(db), ensure_ascii=False, indent=2))
