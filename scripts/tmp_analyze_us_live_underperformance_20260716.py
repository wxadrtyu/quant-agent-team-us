from __future__ import annotations

from pathlib import Path
import json
import re

import duckdb
import pandas as pd


DB = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
OUT_DIR = Path(r"E:\quant-agent-team-us\research\2026-07-16-underperformance-diagnosis")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def factor_tokens(value: str) -> list[str]:
    return [x.strip() for x in re.split(r"[、,;；]", str(value)) if x.strip()]


con = duckdb.connect(str(DB), read_only=True)
strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
con.close()

losers = strategies[strategies["实盘超基准收益"] <= 0].copy()
winners = strategies[strategies["实盘超基准收益"] > 0].copy()

by_holding = (
    strategies.groupby("top_n_numeric")
    .agg(
        策略数=("monitor_key", "count"),
        跑赢数=("当前是否跑赢基准", "sum"),
        平均超基准收益=("实盘超基准收益", "mean"),
        平均实盘收益=("实盘收益", "mean"),
        平均信息比率=("信息比率", "mean"),
    )
    .reset_index()
)
by_holding["跑赢率"] = by_holding["跑赢数"] / by_holding["策略数"]

by_type = (
    strategies.groupby("策略类型")
    .agg(
        策略数=("monitor_key", "count"),
        跑赢数=("当前是否跑赢基准", "sum"),
        平均超基准收益=("实盘超基准收益", "mean"),
        平均实盘收益=("实盘收益", "mean"),
        平均信息比率=("信息比率", "mean"),
        平均样本外超基准=("样本外滚动验证超基准收益", "mean"),
    )
    .reset_index()
)
by_type["跑赢率"] = by_type["跑赢数"] / by_type["策略数"]

factor_rows = []
for _, row in strategies.iterrows():
    for token in factor_tokens(row["主要区分因子"]):
        factor_rows.append(
            {
                "因子": token,
                "monitor_key": row["monitor_key"],
                "当前是否跑赢基准": bool(row["当前是否跑赢基准"]),
                "实盘超基准收益": float(row["实盘超基准收益"]),
                "实盘收益": float(row["实盘收益"]),
            }
        )
factor_frame = pd.DataFrame(factor_rows)
by_factor = (
    factor_frame.groupby("因子")
    .agg(
        策略数=("monitor_key", "count"),
        跑赢数=("当前是否跑赢基准", "sum"),
        平均超基准收益=("实盘超基准收益", "mean"),
        平均实盘收益=("实盘收益", "mean"),
    )
    .reset_index()
)
by_factor["跑赢率"] = by_factor["跑赢数"] / by_factor["策略数"]

report_json = Path(r"G:\quant-agent-team-us\reports\us\live\current\us_simulation_formal_monitoring_0630_0716.json")
payload = json.loads(report_json.read_text(encoding="utf-8"))
stock_rows = []
for item in payload["results"]:
    for stock in item["stocks"]:
        stock_rows.append(
            {
                "monitor_key": item["monitor_key"],
                "策略类型": item["category"],
                "持仓数量": item["n"],
                "当前是否跑赢基准": bool(item["is_outperforming"]),
                "股票": stock["display"],
                "股票代码": stock["code"],
                "个股收益": stock["return"],
                "收益贡献": stock["contribution"],
            }
        )
stock_frame = pd.DataFrame(stock_rows)
loser_stock_drag = (
    stock_frame[~stock_frame["当前是否跑赢基准"]]
    .groupby(["股票代码", "股票"])
    .agg(
        出现次数=("monitor_key", "count"),
        平均个股收益=("个股收益", "mean"),
        平均收益贡献=("收益贡献", "mean"),
        总收益贡献=("收益贡献", "sum"),
    )
    .reset_index()
    .sort_values(["总收益贡献", "出现次数"], ascending=[True, False])
)

by_admission = (
    strategies.groupby("入库日期")
    .agg(
        策略数=("monitor_key", "count"),
        跑赢数=("当前是否跑赢基准", "sum"),
        平均超基准收益=("实盘超基准收益", "mean"),
        平均入库天数=("入库天数", "mean"),
    )
    .reset_index()
)
by_admission["跑赢率"] = by_admission["跑赢数"] / by_admission["策略数"]

worst = losers.sort_values("实盘超基准收益").head(50)
best = winners.sort_values("实盘超基准收益", ascending=False).head(50)

by_holding.to_csv(OUT_DIR / "by_holding_count.csv", index=False, encoding="utf-8-sig")
by_type.sort_values("平均超基准收益").to_csv(OUT_DIR / "by_strategy_type.csv", index=False, encoding="utf-8-sig")
by_factor.sort_values("平均超基准收益").to_csv(OUT_DIR / "by_factor.csv", index=False, encoding="utf-8-sig")
loser_stock_drag.head(100).to_csv(OUT_DIR / "loser_stock_drag_top100.csv", index=False, encoding="utf-8-sig")
by_admission.to_csv(OUT_DIR / "by_admission_date.csv", index=False, encoding="utf-8-sig")
worst.to_csv(OUT_DIR / "worst_50_strategies.csv", index=False, encoding="utf-8-sig")
best.to_csv(OUT_DIR / "best_50_strategies.csv", index=False, encoding="utf-8-sig")

summary = {
    "strategies": int(len(strategies)),
    "outperformers": int(len(winners)),
    "underperformers": int(len(losers)),
    "avg_excess_all": float(strategies["实盘超基准收益"].mean()),
    "avg_excess_winners": float(winners["实盘超基准收益"].mean()),
    "avg_excess_losers": float(losers["实盘超基准收益"].mean()),
    "worst_holding_counts": by_holding.sort_values("平均超基准收益").head(4).to_dict(orient="records"),
    "worst_strategy_types": by_type.sort_values("平均超基准收益").head(8).to_dict(orient="records"),
    "weak_factors": by_factor[by_factor["策略数"] >= 20].sort_values("平均超基准收益").head(10).to_dict(orient="records"),
    "drag_stocks": loser_stock_drag.head(15).to_dict(orient="records"),
    "best_strategy_types": by_type.sort_values("平均超基准收益", ascending=False).head(5).to_dict(orient="records"),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
