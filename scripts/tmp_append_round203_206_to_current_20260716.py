from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd


DB = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
RUN_IDS = [f"2026-07-13-monitor-round{round_no}-quality-stability" for round_no in range(203, 207)]
CURRENT_RUN_ID = "2026-07-16-current-compact-add-round203-206"
ADMISSION_DATE = "2026-07-16"


def monitor_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["candidate_id"].astype(str)
        + "__N"
        + frame["top_n_numeric"].astype(int).astype(str)
        + "__R"
        + frame["rebalance_days_numeric"].astype(int).astype(str)
    )


con = duckdb.connect(str(DB))
current = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
current_holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()

incoming_parts = []
incoming_holding_parts = []
for run_id in RUN_IDS:
    s = con.execute("select * from us_live_pool_strategies where run_id = ?", [run_id]).fetchdf()
    h = con.execute("select * from us_live_pool_holdings where run_id = ?", [run_id]).fetchdf()
    if s.empty:
        continue
    s["source_run_id"] = run_id
    s["monitor_key"] = monitor_key(s)
    s.insert(0, "current_run_id", CURRENT_RUN_ID)
    s["入库日期"] = ADMISSION_DATE
    s["入库天数"] = [
        max(0, (date.fromisoformat(str(end)) - date.fromisoformat(ADMISSION_DATE)).days)
        for end in s["估值日期"].astype(str)
    ]
    s["当前是否跑赢基准"] = s["实盘超基准收益"] > 0
    s["入库后可用估值次数"] = 1
    s["入库至今持续跑赢"] = s["当前是否跑赢基准"]
    s["当前诊断"] = s["当前是否跑赢基准"].map(
        {True: "新增入库后当前跑赢基准，继续观察", False: "新增后当前跑输基准，需诊断"}
    )
    incoming_parts.append(s)

    h = h.merge(s[["run_id", "策略编号", "candidate_id", "monitor_key", "source_run_id"]], on=["run_id", "策略编号"], how="left")
    h.insert(0, "current_run_id", CURRENT_RUN_ID)
    incoming_holding_parts.append(
        h[
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

existing_keys = set(current["monitor_key"].astype(str))
incoming = incoming[~incoming["monitor_key"].astype(str).isin(existing_keys)].copy()
incoming_holdings = incoming_holdings[incoming_holdings["monitor_key"].astype(str).isin(set(incoming["monitor_key"].astype(str)))].copy()

for column in current.columns:
    if column not in incoming.columns:
        incoming[column] = pd.NA
for column in current_holdings.columns:
    if column not in incoming_holdings.columns:
        incoming_holdings[column] = pd.NA

combined = pd.concat([current, incoming[current.columns]], ignore_index=True)
combined_holdings = pd.concat([current_holdings, incoming_holdings[current_holdings.columns]], ignore_index=True)

con.execute("create or replace table us_live_monitoring_strategies_current_before_round203_206_append as select * from us_live_monitoring_strategies_current")
con.execute("create or replace table us_live_monitoring_holdings_current_before_round203_206_append as select * from us_live_monitoring_holdings_current")
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
