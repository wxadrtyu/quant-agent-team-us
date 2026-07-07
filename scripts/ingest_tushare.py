#!/usr/bin/env python3
"""Ingest Tushare parquet (fetch_tushare.py output) into quant.duckdb.

Steps (run independently so partial pulls can land early):
  constituents -> index_constituents  (PIT membership for per-universe + de-bias)
  roe          -> financials           (quality factor source, restatements deduped)
  meta         -> stock_meta, delisted (industry + survivorship list)
  valuation    -> valuation_daily      (value factor source; run after the long pull)
  panel        -> rebuild factor_panel with value(ep,bp)/quality(roe) lit up

Usage: python scripts/ingest_tushare.py --what all   (or constituents|roe|meta|valuation|panel)

Tushare dates are 'YYYYMMDD' strings -> strptime to DATE so ASOF joins line up with
market_daily.trade_date. Source tag 'tushare' is preserved on the raw tables.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TS = ROOT / "data" / "tushare"


def _glob(sub: str) -> str:
    return str((TS / sub / "*.parquet")).replace("\\", "/")


def ingest_constituents(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("DROP TABLE IF EXISTS index_constituents")
    con.execute(f"""
        CREATE TABLE index_constituents AS
        SELECT CAST(universe AS VARCHAR)            universe,
               CAST(index_code AS VARCHAR)          index_code,
               CAST(stock_code AS VARCHAR)          stock_code,
               CAST(con_code AS VARCHAR)            ts_code,
               strptime(CAST(trade_date AS VARCHAR), '%Y%m%d')::DATE AS trade_date,
               CAST(weight AS DOUBLE)               weight,
               'tushare'                            AS source
        FROM read_parquet('{_glob('constituents')}', union_by_name=true)
    """)
    r = con.execute(
        "SELECT count(*), count(DISTINCT universe), count(DISTINCT stock_code) FROM index_constituents"
    ).fetchone()
    return {"index_constituents_rows": r[0], "universes": r[1], "distinct_stocks": r[2]}


def ingest_roe(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("DROP TABLE IF EXISTS financials")
    # fina_indicator_vip can return >1 row per (stock, period) across restatements -> keep one.
    con.execute(f"""
        CREATE TABLE financials AS
        SELECT stock_code, report_date, roe, 'tushare' AS source
        FROM (
            SELECT CAST(stock_code AS VARCHAR) stock_code,
                   strptime(CAST(report_date AS VARCHAR), '%Y%m%d')::DATE AS report_date,
                   CAST(roe AS DOUBLE) roe,
                   row_number() OVER (PARTITION BY stock_code,
                       strptime(CAST(report_date AS VARCHAR), '%Y%m%d')::DATE
                       ORDER BY roe DESC NULLS LAST) AS rn
            FROM read_parquet('{_glob('roe')}', union_by_name=true)
            WHERE report_date IS NOT NULL
        ) WHERE rn = 1
    """)
    r = con.execute("SELECT count(*), count(DISTINCT stock_code) FROM financials").fetchone()
    return {"financials_rows": r[0], "financials_stocks": r[1]}


def ingest_meta(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("DROP TABLE IF EXISTS stock_meta")
    con.execute(f"""
        CREATE TABLE stock_meta AS
        SELECT CAST(stock_code AS VARCHAR) AS stock_code,
               CAST("name" AS VARCHAR) AS "name",
               CAST(industry AS VARCHAR) AS industry,
               CAST("market" AS VARCHAR) AS "market",
               strptime(CAST(list_date AS VARCHAR), '%Y%m%d')::DATE AS list_date,
               'tushare' AS source
        FROM read_parquet('{(TS / 'meta' / 'stock_basic_L.parquet').as_posix()}')
    """)
    con.execute("DROP TABLE IF EXISTS delisted")
    con.execute(f"""
        CREATE TABLE delisted AS
        SELECT CAST(stock_code AS VARCHAR) AS stock_code,
               CAST("name" AS VARCHAR) AS "name",
               strptime(CAST(delist_date AS VARCHAR), '%Y%m%d')::DATE AS delist_date,
               'tushare' AS source
        FROM read_parquet('{(TS / 'meta' / 'stock_basic_D.parquet').as_posix()}')
    """)
    r = con.execute("SELECT count(*) FROM stock_meta").fetchone()[0]
    d = con.execute("SELECT count(*) FROM delisted").fetchone()[0]
    return {"stock_meta_rows": r, "delisted_rows": d}


def ingest_valuation(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("DROP TABLE IF EXISTS valuation_daily")
    con.execute(f"""
        CREATE TABLE valuation_daily AS
        SELECT CAST(stock_code AS VARCHAR) stock_code,
               strptime(CAST(trade_date AS VARCHAR), '%Y%m%d')::DATE AS trade_date,
               CAST(pe_ttm AS DOUBLE) pe_ttm,
               CAST(pb AS DOUBLE) pb,
               CAST(ps_ttm AS DOUBLE) ps_ttm,
               CAST(total_mv AS DOUBLE) total_mv,
               CAST(circ_mv AS DOUBLE) circ_mv,
               CAST(turnover_rate AS DOUBLE) turnover_rate,
               'tushare' AS source
        FROM read_parquet('{_glob('valuation')}', union_by_name=true)
        WHERE trade_date IS NOT NULL
    """)
    r = con.execute(
        "SELECT count(*), count(DISTINCT stock_code), min(trade_date), max(trade_date) FROM valuation_daily"
    ).fetchone()
    return {"valuation_rows": r[0], "valuation_stocks": r[1],
            "valuation_date_min": str(r[2]), "valuation_date_max": str(r[3])}


def ingest_missing_prices(con: duckdb.DuckDBPyConnection) -> dict:
    """Append backfilled delisted/dropped constituent prices into market_daily
    (idempotent: removes those stock_codes first). Empty marker files are skipped
    by union_by_name reading only non-empty parquet."""
    glob = _glob("missing_prices")
    # build the set of codes we have non-empty data for, then replace them
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _mp AS
        SELECT CAST(stock_code AS VARCHAR) stock_code,
               strptime(CAST(trade_date AS VARCHAR), '%Y%m%d')::DATE AS trade_date,
               CAST(open AS DOUBLE) open, CAST(high AS DOUBLE) high, CAST(low AS DOUBLE) low,
               CAST(close_adj AS DOUBLE) close_adj, CAST(volume AS DOUBLE) volume,
               CAST(amount AS DOUBLE) amount, CAST(amplitude AS DOUBLE) amplitude,
               CAST(pct_chg AS DOUBLE) pct_chg, CAST(change AS DOUBLE) change,
               CAST(turnover_rate AS DOUBLE) turnover_rate
        FROM read_parquet('{glob}', union_by_name=true)
        WHERE trade_date IS NOT NULL
    """)
    con.execute("""
        DELETE FROM market_daily
        WHERE stock_code IN (SELECT DISTINCT stock_code FROM _mp)
    """)
    con.execute("""
        INSERT INTO market_daily
        SELECT stock_code, trade_date, open, high, low, close_adj, volume, amount,
               amplitude, pct_chg, change, turnover_rate FROM _mp
    """)
    r = con.execute("SELECT count(*), count(DISTINCT stock_code) FROM _mp").fetchone()
    return {"missing_prices_rows": r[0], "missing_prices_stocks": r[1]}


def rebuild_panel(db_path: str) -> dict:
    from quant_agent_team.factor_panel import build_factor_panel
    return build_factor_panel(db_path, add_fundamentals=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", default="all",
                    choices=["all", "constituents", "roe", "meta", "valuation",
                             "missing_prices", "panel"])
    ap.add_argument("--db", default=str(ROOT / "quant.duckdb"))
    args = ap.parse_args()

    out: dict = {}
    con = duckdb.connect(args.db)
    try:
        if args.what in ("all", "constituents"):
            out.update(ingest_constituents(con))
        if args.what in ("all", "roe"):
            out.update(ingest_roe(con))
        if args.what in ("all", "meta"):
            out.update(ingest_meta(con))
        if args.what in ("all", "valuation"):
            out.update(ingest_valuation(con))
        if args.what in ("all", "missing_prices"):
            out.update(ingest_missing_prices(con))
    finally:
        con.close()
    if args.what in ("all", "panel"):
        out["factor_panel"] = {k: rebuild_panel(args.db)[k]
                               for k in ("rows", "stocks", "columns", "fundamentals_joined")}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
