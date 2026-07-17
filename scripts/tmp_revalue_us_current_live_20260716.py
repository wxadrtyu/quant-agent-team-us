from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import sys

import duckdb
import pandas as pd

sys.path.insert(0, r"G:\quant-agent-team-us\scripts")
import us_live_pool
import us_strategy_factory_loop as factory


DB = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
RAW = Path(r"E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart")
RESEARCH = Path(r"E:\quant-agent-team-us\research")
RUN_ID = "2026-07-16-current-live-intraday-valuation"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

C = {
    "sid": "策略编号",
    "stype": "策略类型",
    "hold_n": "持仓数量",
    "signal": "实盘起点",
    "entry": "入场日期",
    "valuation": "估值日期",
    "ret": "实盘收益",
    "bench": "实盘基准收益",
    "excess": "实盘超基准收益",
    "live_hold_n": "实盘持仓数量",
    "stock": "股票代码",
    "rank": "排名",
    "weight": "目标权重",
    "signal_date": "信号日期",
    "plan_entry": "计划入场",
}


def source_tokens(source_run_id: str) -> list[str]:
    tokens = []
    m = re.search(r"round(\d+)", source_run_id)
    if m:
        tokens.append(f"round{m.group(1)}")
    for part in [
        "quality-stability",
        "focused-pulltrend",
        "long-momentum-tailrisk",
        "sub10-pulltrend-120",
        "top20",
        "rank21-40",
        "rank41-60",
        "rank61-80",
        "next-allowed",
    ]:
        if part in source_run_id:
            tokens.append(part)
    if "live-all-worthy-dynamic-liquidity" in source_run_id:
        tokens.append("factory")
    return tokens


def load_candidates() -> pd.DataFrame:
    rows = []
    files = sorted(RESEARCH.rglob("*candidate*.csv"))
    for path in files:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        required = {"candidate_id", "top_n", "rebalance_days", "weights"}
        if not required.issubset(df.columns):
            continue
        keep = df[["candidate_id", "top_n", "rebalance_days", "weights"]].copy()
        keep["candidate_source_path"] = str(path)
        keep["candidate_source_name"] = path.name
        rows.append(keep)
    if not rows:
        raise RuntimeError("No candidate CSV files found")
    out = pd.concat(rows, ignore_index=True)
    out["top_n"] = pd.to_numeric(out["top_n"], errors="coerce").astype("Int64")
    out["rebalance_days"] = pd.to_numeric(out["rebalance_days"], errors="coerce").astype("Int64")
    return out.dropna(subset=["candidate_id", "top_n", "rebalance_days", "weights"])


def choose_candidate(candidates: pd.DataFrame, strategy: pd.Series) -> pd.Series | None:
    base = candidates[
        candidates["candidate_id"].astype(str).eq(str(strategy["candidate_id"]))
        & candidates["top_n"].astype(int).eq(int(strategy["top_n_numeric"]))
        & candidates["rebalance_days"].astype(int).eq(int(strategy["rebalance_days_numeric"]))
    ].copy()
    if base.empty:
        return None
    tokens = source_tokens(str(strategy.get("source_run_id", "")))
    if tokens:
        mask = pd.Series(True, index=base.index)
        for token in tokens:
            if token == "factory":
                continue
            mask &= base["candidate_source_name"].str.contains(token, regex=False)
        preferred = base[mask]
        if not preferred.empty:
            return preferred.iloc[-1]
    return base.iloc[-1]


def parse_weights(raw: str) -> dict[str, float]:
    value = json.loads(str(raw))
    return {str(k): float(v) for k, v in value.items()}


def main() -> None:
    con = duckdb.connect(str(DB))
    current_s = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
    current_h = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    if current_s.empty:
        raise RuntimeError("current strategy table is empty")

    con.execute(
        f"create or replace table us_live_monitoring_strategies_current_backup_{STAMP} as "
        "select * from us_live_monitoring_strategies_current"
    )
    con.execute(
        f"create or replace table us_live_monitoring_holdings_current_backup_{STAMP} as "
        "select * from us_live_monitoring_holdings_current"
    )

    candidates = load_candidates()
    panel, *_ = factory.load_panel(RAW, universe_mode="dynamic_liquidity")
    live_frame, signal_date, entry_date, valuation_date = us_live_pool.build_live_period(
        panel, signal_date="2026-06-30", valuation_date="2026-07-16"
    )
    benchmark_ret = float(live_frame["asset_ret"].mean())

    updated_rows = []
    holdings = []
    missing = []
    for _, strategy in current_s.iterrows():
        cand = choose_candidate(candidates, strategy)
        if cand is None:
            missing.append(
                {
                    "monitor_key": strategy.get("monitor_key"),
                    "candidate_id": strategy.get("candidate_id"),
                    "source_run_id": strategy.get("source_run_id"),
                }
            )
            continue
        weights = parse_weights(cand["weights"])
        scores = factory.score_panel(live_frame, weights)
        top_n = int(strategy["top_n_numeric"])
        picks = scores.nlargest(top_n)
        trade = live_frame.loc[picks.index].copy()
        if len(trade) != top_n:
            missing.append(
                {
                    "monitor_key": strategy.get("monitor_key"),
                    "candidate_id": strategy.get("candidate_id"),
                    "source_run_id": strategy.get("source_run_id"),
                    "reason": f"only {len(trade)} picks",
                }
            )
            continue
        strategy_ret = float(trade["asset_ret"].mean())
        live_excess = (1.0 + strategy_ret) / (1.0 + benchmark_ret) - 1.0

        row = strategy.copy()
        row["current_run_id"] = RUN_ID
        row[C["signal"]] = signal_date
        row[C["entry"]] = entry_date
        row[C["valuation"]] = valuation_date
        row[C["ret"]] = strategy_ret
        row[C["bench"]] = benchmark_ret
        row[C["excess"]] = live_excess
        row[C["live_hold_n"]] = top_n
        updated_rows.append(row)

        weight = 1.0 / top_n
        for rank, pick_index in enumerate(picks.index, start=1):
            item = live_frame.loc[pick_index]
            holdings.append(
                {
                    "current_run_id": RUN_ID,
                    "monitor_key": strategy["monitor_key"],
                    "candidate_id": strategy["candidate_id"],
                    "run_id": strategy["run_id"],
                    C["sid"]: strategy[C["sid"]],
                    C["stock"]: item["symbol"],
                    C["rank"]: rank,
                    C["weight"]: weight,
                    C["signal_date"]: signal_date,
                    C["plan_entry"]: f"{entry_date}开盘，基于{signal_date}收盘信号",
                    C["valuation"]: valuation_date,
                    C["stype"]: strategy[C["stype"]],
                    "source_run_id": strategy["source_run_id"],
                }
            )

    updated = pd.DataFrame(updated_rows)
    holdings_df = pd.DataFrame(holdings)
    if missing:
        missing_df = pd.DataFrame(missing)
        con.register("missing_df", missing_df)
        con.execute(
            "create or replace table us_live_monitoring_revalue_missing_20260716 as select * from missing_df"
        )
        raise RuntimeError(f"Missing candidate matches: {len(missing)}")

    if len(updated) != len(current_s):
        raise RuntimeError(f"Updated {len(updated)} strategies but expected {len(current_s)}")

    excluded = updated[updated[C["excess"]] <= 0].copy()
    kept = updated[updated[C["excess"]] > 0].copy()
    kept_keys = set(kept["monitor_key"].astype(str))
    kept_holdings = holdings_df[holdings_df["monitor_key"].astype(str).isin(kept_keys)].copy()

    con.register("updated_all", updated)
    con.register("excluded_df", excluded)
    con.register("kept_df", kept)
    con.register("kept_holdings", kept_holdings)
    con.register("all_holdings", holdings_df)
    con.execute("create or replace table us_live_monitoring_strategies_revalued_20260716 as select * from updated_all")
    con.execute("create or replace table us_live_monitoring_holdings_revalued_20260716 as select * from all_holdings")
    con.execute("create or replace table us_live_monitoring_strategies_excluded_20260716_intraday as select * from excluded_df")
    con.execute("create or replace table us_live_monitoring_strategies_current as select * from kept_df")
    con.execute("create or replace table us_live_monitoring_holdings_current as select * from kept_holdings")
    con.close()

    summary = {
        "run_id": RUN_ID,
        "raw_dir": str(RAW),
        "signal_date": signal_date,
        "entry_date": entry_date,
        "valuation_date": valuation_date,
        "benchmark_ret": benchmark_ret,
        "input_strategies": int(len(current_s)),
        "kept_strategies": int(len(kept)),
        "excluded_under_benchmark": int(len(excluded)),
        "current_holdings": int(len(kept_holdings)),
        "min_live_excess": float(kept[C["excess"]].min()) if not kept.empty else None,
        "avg_live_excess": float(kept[C["excess"]].mean()) if not kept.empty else None,
        "holding_distribution": {
            str(k): int(v) for k, v in kept["top_n_numeric"].value_counts().sort_index().items()
        },
        "backup_suffix": STAMP,
        "note": "2026-07-16 is intraday at Asia/Shanghai update time; historical live pool preserved in backup and revalued tables.",
    }
    out = Path("reports/us/live/current") / "us_live_revalue_20260716_intraday_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
