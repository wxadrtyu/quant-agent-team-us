from __future__ import annotations

from datetime import date
from pathlib import Path
import re

import duckdb
import pandas as pd


DB = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
BACKUP_STRATEGIES = "us_live_monitoring_strategies_current_backup_20260716_225429"
BACKUP_HOLDINGS = "us_live_monitoring_holdings_current_backup_20260716_225429"


def parse_date(value: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value))
    if not match:
        return ""
    return match.group(0)


def days_between(start: str, end: str) -> int:
    if not start or not end:
        return 0
    return max(0, (date.fromisoformat(end) - date.fromisoformat(start)).days)


con = duckdb.connect(str(DB))
revalued = con.execute("select * from us_live_monitoring_strategies_revalued_20260716").fetchdf()
revalued_holdings = con.execute("select * from us_live_monitoring_holdings_revalued_20260716").fetchdf()
backup = con.execute(f"select * from {BACKUP_STRATEGIES}").fetchdf()
backup_holdings = con.execute(f"select * from {BACKUP_HOLDINGS}").fetchdf()

meta = backup[["monitor_key", "current_run_id", "实盘超基准收益", "估值日期"]].rename(
    columns={
        "current_run_id": "原入库批次",
        "实盘超基准收益": "入库前回填超基准收益",
        "估值日期": "入库前回填估值日期",
    }
)
out = revalued.drop(columns=["current_run_id"], errors="ignore").merge(meta, on="monitor_key", how="left")
out.insert(0, "current_run_id", out["原入库批次"].fillna("2026-07-16-current-live-intraday-valuation"))
out["入库日期"] = out["current_run_id"].map(parse_date)
out["入库天数"] = [
    days_between(start, end) for start, end in zip(out["入库日期"], out["估值日期"].astype(str), strict=False)
]
out["当前是否跑赢基准"] = out["实盘超基准收益"] > 0
out["入库后可用估值次数"] = 1
out["入库至今持续跑赢"] = out["当前是否跑赢基准"]
out["当前诊断"] = out.apply(
    lambda row: "继续观察：当前仍跑赢基准"
    if row["当前是否跑赢基准"]
    else "需诊断：当前跑输基准，保留在监控池观察归因",
    axis=1,
)

holding_meta = backup_holdings[["monitor_key", "current_run_id"]].drop_duplicates("monitor_key").rename(
    columns={"current_run_id": "原入库批次"}
)
holdings = revalued_holdings.drop(columns=["current_run_id"], errors="ignore").merge(
    holding_meta, on="monitor_key", how="left"
)
holdings.insert(0, "current_run_id", holdings["原入库批次"].fillna("2026-07-16-current-live-intraday-valuation"))
holdings = holdings.drop(columns=["原入库批次"], errors="ignore")

con.execute("create or replace table us_live_monitoring_strategies_current_before_restore_20260716 as select * from us_live_monitoring_strategies_current")
con.register("restored_strategies", out)
con.register("restored_holdings", holdings)
con.execute("create or replace table us_live_monitoring_strategies_current as select * from restored_strategies")
con.execute("create or replace table us_live_monitoring_holdings_current as select * from restored_holdings")
con.close()

summary = {
    "restored_strategies": int(len(out)),
    "restored_holdings": int(len(holdings)),
    "outperforming": int(out["当前是否跑赢基准"].sum()),
    "underperforming_kept": int((~out["当前是否跑赢基准"]).sum()),
    "persistent_outperforming": int(out["入库至今持续跑赢"].sum()),
    "holding_distribution": {
        str(key): int(value) for key, value in out["top_n_numeric"].value_counts().sort_index().items()
    },
}
print(summary)
