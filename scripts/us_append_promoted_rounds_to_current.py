from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd


def monitor_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["candidate_id"].astype(str)
        + "__N"
        + frame["top_n_numeric"].astype(int).astype(str)
        + "__R"
        + frame["rebalance_days_numeric"].astype(int).astype(str)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
    parser.add_argument("--start-round", type=int, required=True)
    parser.add_argument("--end-round", type=int, required=True)
    parser.add_argument("--admission-date", default="2026-07-16")
    parser.add_argument("--current-run-id", default="")
    args = parser.parse_args()

    db_path = Path(args.db)
    run_ids = [f"2026-07-13-monitor-round{round_no}-quality-stability" for round_no in range(args.start_round, args.end_round + 1)]
    current_run_id = args.current_run_id or f"{args.admission_date}-current-compact-add-round{args.start_round}-{args.end_round}"

    con = duckdb.connect(str(db_path))
    current = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
    current_holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    incoming_parts = []
    incoming_holding_parts = []

    for run_id in run_ids:
        strategies = con.execute("select * from us_live_pool_strategies where run_id = ?", [run_id]).fetchdf()
        holdings = con.execute("select * from us_live_pool_holdings where run_id = ?", [run_id]).fetchdf()
        if strategies.empty:
            continue
        strategies["source_run_id"] = run_id
        strategies["monitor_key"] = monitor_key(strategies)
        strategies.insert(0, "current_run_id", current_run_id)
        strategies["入库日期"] = args.admission_date
        strategies["入库天数"] = [
            max(0, (date.fromisoformat(str(end)) - date.fromisoformat(args.admission_date)).days)
            for end in strategies["估值日期"].astype(str)
        ]
        strategies["当前是否跑赢基准"] = strategies["实盘超基准收益"] > 0
        strategies["入库后可用估值次数"] = 1
        strategies["入库至今持续跑赢"] = strategies["当前是否跑赢基准"]
        strategies["当前诊断"] = strategies["当前是否跑赢基准"].map(
            {True: "新增入库后当前跑赢基准，继续观察", False: "新增后当前跑输基准，需诊断"}
        )
        incoming_parts.append(strategies)

        holdings = holdings.merge(
            strategies[["run_id", "策略编号", "candidate_id", "monitor_key", "source_run_id"]],
            on=["run_id", "策略编号"],
            how="left",
        )
        holdings.insert(0, "current_run_id", current_run_id)
        incoming_holding_parts.append(
            holdings[
                [
                    "current_run_id",
                    "monitor_key",
                    "candidate_id",
                    "run_id",
                    "策略编号",
                    "股票代码",
                    "排名",
                    "目标权重",
                    "信号日期",
                    "计划入场",
                    "估值日期",
                    "策略类型",
                    "source_run_id",
                ]
            ]
        )

    incoming = pd.concat(incoming_parts, ignore_index=True) if incoming_parts else pd.DataFrame()
    incoming_holdings = pd.concat(incoming_holding_parts, ignore_index=True) if incoming_holding_parts else pd.DataFrame()
    if not incoming.empty:
        existing_keys = set(current["monitor_key"].astype(str))
        incoming = incoming[~incoming["monitor_key"].astype(str).isin(existing_keys)].copy()
        incoming_holdings = incoming_holdings[
            incoming_holdings["monitor_key"].astype(str).isin(set(incoming["monitor_key"].astype(str)))
        ].copy()

    for column in current.columns:
        if column not in incoming.columns:
            incoming[column] = pd.NA
    for column in current_holdings.columns:
        if column not in incoming_holdings.columns:
            incoming_holdings[column] = pd.NA

    combined = pd.concat([current, incoming[current.columns]], ignore_index=True)
    combined_holdings = pd.concat([current_holdings, incoming_holdings[current_holdings.columns]], ignore_index=True)
    backup_suffix = f"round{args.start_round}_{args.end_round}_append"
    con.execute(f"create or replace table us_live_monitoring_strategies_current_before_{backup_suffix} as select * from us_live_monitoring_strategies_current")
    con.execute(f"create or replace table us_live_monitoring_holdings_current_before_{backup_suffix} as select * from us_live_monitoring_holdings_current")
    con.register("combined_strategies", combined)
    con.register("combined_holdings", combined_holdings)
    con.execute("create or replace table us_live_monitoring_strategies_current as select * from combined_strategies")
    con.execute("create or replace table us_live_monitoring_holdings_current as select * from combined_holdings")
    con.close()

    print(
        {
            "incoming_after_dedupe": int(len(incoming)),
            "incoming_holdings": int(len(incoming_holdings)),
            "current_total": int(len(combined)),
            "holdings_total": int(len(combined_holdings)),
            "new_avg_excess": float(incoming["实盘超基准收益"].mean()) if not incoming.empty else 0.0,
            "new_min_excess": float(incoming["实盘超基准收益"].min()) if not incoming.empty else 0.0,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
