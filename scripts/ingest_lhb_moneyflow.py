#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B1 ingest — 龙虎榜 + 资金流向 parquet 入库 DuckDB。

读取 E:\\量化数据_tushare 下三个数据集, 建表:
  - lhb_daily       : 每日龙虎榜明细 (稀疏, 仅上榜股票)
  - lhb_inst_daily  : 每日龙虎榜机构席位明细 (多行/股/日)
  - moneyflow_daily : 每日个股资金流向 (全市场)

入库后不自动重建 factor_panel (由 build_factor_panel 单独触发, 确保因子代码就绪)。

用法:
  python scripts/ingest_lhb_moneyflow.py
  python scripts/ingest_lhb_moneyflow.py --db quant.duckdb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path(r"E:/量化数据_tushare")


def _glob(folder: str) -> str:
    p = (ARCHIVE / folder / "*.parquet").as_posix()
    return f"read_parquet('{p}', union_by_name=true)"


def ingest(db_path: str = "quant.duckdb") -> dict:
    con = duckdb.connect(db_path)

    results = {}

    # 1. 龙虎榜明细
    lhb_sql = f"""
        CREATE OR REPLACE TABLE lhb_daily AS
        SELECT
            CAST(stock_code AS VARCHAR)   AS stock_code,
            CAST(trade_date AS DATE)      AS trade_date,
            CAST(name AS VARCHAR)         AS name,
            CAST(close AS DOUBLE)         AS close,
            CAST(pct_change AS DOUBLE)    AS pct_change,
            CAST(turnover_rate AS DOUBLE)  AS turnover_rate,
            CAST(amount AS DOUBLE)        AS amount,
            CAST(l_sell AS DOUBLE)        AS l_sell,
            CAST(l_buy AS DOUBLE)         AS l_buy,
            CAST(l_amount AS DOUBLE)      AS l_amount,
            CAST(net_amount AS DOUBLE)    AS net_amount,
            CAST(net_rate AS DOUBLE)      AS net_rate,
            CAST(amount_rate AS DOUBLE)   AS amount_rate,
            CAST(float_values AS DOUBLE)  AS float_values,
            CAST(reason AS VARCHAR)       AS reason
        FROM { _glob('20_龙虎榜') }
        WHERE trade_date IS NOT NULL
    """
    con.execute(lhb_sql)
    r = con.execute("SELECT count(*), count(DISTINCT stock_code), min(trade_date), max(trade_date) FROM lhb_daily").fetchone()
    results["lhb_daily"] = {"rows": r[0], "stocks": r[1], "min": str(r[2]), "max": str(r[3])}

    # 2. 龙虎榜机构席位
    inst_sql = f"""
        CREATE OR REPLACE TABLE lhb_inst_daily AS
        SELECT
            CAST(stock_code AS VARCHAR)   AS stock_code,
            CAST(trade_date AS DATE)      AS trade_date,
            CAST(exalter AS VARCHAR)      AS exalter,
            CAST(buy AS DOUBLE)           AS buy,
            CAST(buy_rate AS DOUBLE)      AS buy_rate,
            CAST(sell AS DOUBLE)          AS sell,
            CAST(sell_rate AS DOUBLE)     AS sell_rate,
            CAST(net_buy AS DOUBLE)       AS net_buy,
            CAST(side AS INTEGER)         AS side,
            CAST(reason AS VARCHAR)       AS reason
        FROM { _glob('21_龙虎榜机构') }
        WHERE trade_date IS NOT NULL
    """
    con.execute(inst_sql)
    r = con.execute("SELECT count(*), count(DISTINCT stock_code), min(trade_date), max(trade_date) FROM lhb_inst_daily").fetchone()
    results["lhb_inst_daily"] = {"rows": r[0], "stocks": r[1], "min": str(r[2]), "max": str(r[3])}

    # 3. 资金流向
    mf_sql = f"""
        CREATE OR REPLACE TABLE moneyflow_daily AS
        SELECT
            CAST(stock_code AS VARCHAR)      AS stock_code,
            CAST(trade_date AS DATE)         AS trade_date,
            CAST(buy_sm_amount AS DOUBLE)    AS buy_sm_amount,
            CAST(sell_sm_amount AS DOUBLE)   AS sell_sm_amount,
            CAST(buy_md_amount AS DOUBLE)    AS buy_md_amount,
            CAST(sell_md_amount AS DOUBLE)   AS sell_md_amount,
            CAST(buy_lg_amount AS DOUBLE)    AS buy_lg_amount,
            CAST(sell_lg_amount AS DOUBLE)   AS sell_lg_amount,
            CAST(buy_elg_amount AS DOUBLE)   AS buy_elg_amount,
            CAST(sell_elg_amount AS DOUBLE)  AS sell_elg_amount,
            CAST(net_mf_vol AS DOUBLE)       AS net_mf_vol,
            CAST(net_mf_amount AS DOUBLE)    AS net_mf_amount
        FROM { _glob('06_资金流向') }
        WHERE trade_date IS NOT NULL
    """
    con.execute(mf_sql)
    r = con.execute("SELECT count(*), count(DISTINCT stock_code), min(trade_date), max(trade_date) FROM moneyflow_daily").fetchone()
    results["moneyflow_daily"] = {"rows": r[0], "stocks": r[1], "min": str(r[2]), "max": str(r[3])}

    con.close()
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "quant.duckdb"))
    args = ap.parse_args()
    print(json.dumps(ingest(args.db), ensure_ascii=False, indent=2))
