from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import us_live_pool
import us_strategy_factory_loop as factory


RESEARCH_DIR = Path(r"E:\quant-agent-team-us\research")


def parse_date(value: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value))
    return match.group(0) if match else ""


def days_between(start: str, end: str) -> int:
    if not start or not end:
        return 0
    return max(0, (date.fromisoformat(end) - date.fromisoformat(start)).days)


def source_tokens(source_run_id: str) -> list[str]:
    tokens = []
    match = re.search(r"round(\d+)", source_run_id)
    if match:
        tokens.append(f"round{match.group(1)}")
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
        "live-strength",
    ]:
        if part in source_run_id:
            tokens.append(part)
    if "live-all-worthy-dynamic-liquidity" in source_run_id:
        tokens.append("factory")
    return tokens


def load_candidates() -> pd.DataFrame:
    rows = []
    for path in sorted(RESEARCH_DIR.rglob("*candidate*.csv")):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        required = {"candidate_id", "top_n", "rebalance_days", "weights"}
        if not required.issubset(frame.columns):
            continue
        keep = frame[["candidate_id", "top_n", "rebalance_days", "weights"]].copy()
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
    return {str(key): float(val) for key, val in value.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--signal-date", default="2026-06-30")
    parser.add_argument("--valuation-date", required=True)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    db_path = Path(args.db)
    raw_dir = Path(args.raw_dir)
    run_id = args.run_id or f"{args.valuation_date}-current-live-intraday-valuation"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    con = duckdb.connect(str(db_path))
    current_s = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
    current_h = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    if current_s.empty or current_h.empty:
        raise RuntimeError("current tables are empty")

    con.execute(f"create or replace table us_live_monitoring_strategies_current_backup_{stamp} as select * from us_live_monitoring_strategies_current")
    con.execute(f"create or replace table us_live_monitoring_holdings_current_backup_{stamp} as select * from us_live_monitoring_holdings_current")

    candidates = load_candidates()
    panel, *_ = factory.load_panel(raw_dir, universe_mode="dynamic_liquidity")
    live_frame, signal_date, entry_date, valuation_date = us_live_pool.build_live_period(
        panel, signal_date=args.signal_date, valuation_date=args.valuation_date
    )
    benchmark_ret = float(live_frame["asset_ret"].mean())

    updated_rows = []
    holding_rows = []
    missing = []
    for _, strategy in current_s.iterrows():
        candidate = choose_candidate(candidates, strategy)
        if candidate is None:
            missing.append({"monitor_key": strategy.get("monitor_key"), "candidate_id": strategy.get("candidate_id")})
            continue
        weights = parse_weights(candidate["weights"])
        scores = factory.score_panel(live_frame, weights)
        top_n = int(strategy["top_n_numeric"])
        picks = scores.nlargest(top_n)
        trade = live_frame.loc[picks.index].copy()
        if len(trade) != top_n:
            missing.append({"monitor_key": strategy.get("monitor_key"), "candidate_id": strategy.get("candidate_id"), "reason": f"only {len(trade)} picks"})
            continue

        strategy_ret = float(trade["asset_ret"].mean())
        live_excess = (1.0 + strategy_ret) / (1.0 + benchmark_ret) - 1.0

        row = strategy.copy()
        row["实盘起点"] = signal_date
        row["入场日期"] = entry_date
        row["估值日期"] = valuation_date
        row["实盘收益"] = strategy_ret
        row["实盘基准收益"] = benchmark_ret
        row["实盘超基准收益"] = live_excess
        row["实盘持仓数量"] = top_n
        admission_date = parse_date(str(row.get("入库日期", ""))) or parse_date(str(row.get("current_run_id", "")))
        row["入库日期"] = admission_date
        row["入库天数"] = days_between(admission_date, valuation_date)
        previous_persistent = bool(row.get("入库至今持续跑赢", live_excess > 0))
        row["当前是否跑赢基准"] = live_excess > 0
        row["入库后可用估值次数"] = int(row.get("入库后可用估值次数", 1) or 1) + 1
        row["入库至今持续跑赢"] = previous_persistent and live_excess > 0
        row["当前诊断"] = (
            "继续观察：当前仍跑赢基准"
            if live_excess > 0
            else "需诊断：当前跑输基准，保留在监控池观察归因"
        )
        updated_rows.append(row)

        weight = 1.0 / top_n
        for rank, pick_index in enumerate(picks.index, start=1):
            item = live_frame.loc[pick_index]
            holding_rows.append(
                {
                    "current_run_id": strategy["current_run_id"],
                    "monitor_key": strategy["monitor_key"],
                    "candidate_id": strategy["candidate_id"],
                    "run_id": strategy["run_id"],
                    "策略编号": strategy["策略编号"],
                    "股票代码": item["symbol"],
                    "排名": rank,
                    "目标权重": weight,
                    "信号日期": signal_date,
                    "计划入场": f"{entry_date}开盘，基于{signal_date}收盘信号",
                    "估值日期": valuation_date,
                    "策略类型": strategy["策略类型"],
                    "source_run_id": strategy["source_run_id"],
                }
            )

    if missing:
        missing_df = pd.DataFrame(missing)
        con.register("missing_df", missing_df)
        con.execute(f"create or replace table us_live_monitoring_revalue_missing_{args.valuation_date.replace('-', '')} as select * from missing_df")
        raise RuntimeError(f"Missing candidate matches: {len(missing)}")

    updated = pd.DataFrame(updated_rows)
    holdings = pd.DataFrame(holding_rows)
    if len(updated) != len(current_s):
        raise RuntimeError(f"Updated {len(updated)} strategies but expected {len(current_s)}")

    suffix = args.valuation_date.replace("-", "")
    con.register("updated_all", updated)
    con.register("all_holdings", holdings)
    con.execute(f"create or replace table us_live_monitoring_strategies_revalued_{suffix} as select * from updated_all")
    con.execute(f"create or replace table us_live_monitoring_holdings_revalued_{suffix} as select * from all_holdings")
    con.execute("create or replace table us_live_monitoring_strategies_current as select * from updated_all")
    con.execute("create or replace table us_live_monitoring_holdings_current as select * from all_holdings")
    con.close()

    summary = {
        "run_id": run_id,
        "raw_dir": str(raw_dir),
        "signal_date": signal_date,
        "entry_date": entry_date,
        "valuation_date": valuation_date,
        "benchmark_ret": benchmark_ret,
        "current_strategies": int(len(updated)),
        "current_holdings": int(len(holdings)),
        "outperforming": int((updated["实盘超基准收益"] > 0).sum()),
        "underperforming_kept": int((updated["实盘超基准收益"] <= 0).sum()),
        "persistent_outperforming": int(updated["入库至今持续跑赢"].sum()),
        "holding_distribution": {str(key): int(value) for key, value in updated["top_n_numeric"].value_counts().sort_index().items()},
        "backup_suffix": stamp,
        "note": "Full current pool retained; underperforming strategies are not removed.",
    }
    out = Path(r"G:\quant-agent-team-us\reports\us\live\current") / f"us_live_revalue_{suffix}_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
