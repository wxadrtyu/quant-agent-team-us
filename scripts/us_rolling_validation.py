from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import us_strategy_factory_loop as factory


def iter_month_windows(start: str, end: str):
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    cursor = start_ts
    while cursor <= end_ts:
        month_end = min(cursor + pd.offsets.MonthEnd(0), end_ts)
        yield cursor, pd.Timestamp(month_end)
        cursor = pd.Timestamp(month_end) + pd.Timedelta(days=1)


def summarize_curve(curve: pd.DataFrame, periods_per_year: float) -> dict[str, float]:
    if curve.empty:
        return {
            "periods": 0,
            "total_return": 0.0,
            "benchmark_return": 0.0,
            "excess_return": 0.0,
            "mdd": 0.0,
            "benchmark_mdd": 0.0,
            "ir": 0.0,
            "avg_ir": 0.0,
            "win_excess": 0.0,
        }
    equity = curve["equity"] if "equity" in curve else (1.0 + curve["strategy_ret"]).cumprod()
    benchmark = curve["benchmark_equity"] if "benchmark_equity" in curve else (1.0 + curve["benchmark_ret"]).cumprod()
    return {
        "periods": int(len(curve)),
        "total_return": float(equity.iloc[-1] - 1.0),
        "benchmark_return": float(benchmark.iloc[-1] - 1.0),
        "excess_return": float(equity.iloc[-1] / benchmark.iloc[-1] - 1.0),
        "mdd": factory.max_drawdown(equity),
        "benchmark_mdd": factory.max_drawdown(benchmark),
        "ir": factory.information_ratio(curve["excess_ret"], periods_per_year),
        "avg_ir": factory.average_year_ir(curve, periods_per_year) if "entry_date" in curve else 0.0,
        "win_excess": float((curve["excess_ret"] > 0).mean()),
    }


def factor_specs(factor_names: str) -> tuple[factory.FactorSpec, ...]:
    by_name = {spec.name: spec for spec in factory.FACTOR_LIBRARY}
    names = [name.strip() for name in factor_names.split(";") if name.strip()]
    return tuple(by_name[name] for name in names)


def restitch_curve(curves: list[pd.DataFrame]) -> pd.DataFrame:
    rows = [curve for curve in curves if not curve.empty]
    if not rows:
        return pd.DataFrame()
    curve = pd.concat(rows, ignore_index=True)
    curve = curve.drop_duplicates(subset=["signal_date", "entry_date", "exit_date", "symbols"])
    curve = curve.sort_values(["entry_date", "exit_date"]).reset_index(drop=True)
    curve["equity"] = (1.0 + curve["strategy_ret"]).cumprod()
    curve["benchmark_equity"] = (1.0 + curve["benchmark_ret"]).cumprod()
    return curve


def rolling_validate_candidate(
    panel: pd.DataFrame,
    context: factory.EvalContext,
    candidate: pd.Series,
    oos_start: str,
    oos_end: str,
    train_years: int,
    ic_cache: dict[tuple[int, str, str], dict[str, float]] | None = None,
    period_cache: dict[tuple[int, str, str], list[factory.PeriodSlice]] | None = None,
) -> tuple[dict, pd.DataFrame]:
    ic_cache = ic_cache if ic_cache is not None else {}
    period_cache = period_cache if period_cache is not None else {}
    factors = factor_specs(candidate["factors"])
    top_n = int(candidate["top_n"])
    rebalance_days = int(candidate["rebalance_days"])
    monthly_curves = []
    for month_start, month_end in iter_month_windows(oos_start, oos_end):
        train_start = (month_start - pd.DateOffset(years=train_years)).date().isoformat()
        train_end = (month_start - pd.Timedelta(days=1)).date().isoformat()
        ic_key = (rebalance_days, train_start, train_end)
        if ic_key not in ic_cache:
            ic_cache[ic_key] = factory.precompute_factor_ics(panel, train_start, train_end, [rebalance_days])[rebalance_days]
        weights = factory.ic_weights_from_values(factors, ic_cache[ic_key])
        extended_end = (month_end + pd.Timedelta(days=max(45, rebalance_days * 4))).date().isoformat()
        period_key = (rebalance_days, month_start.date().isoformat(), extended_end)
        if period_key not in period_cache:
            periods = factory.make_period_slices(context, rebalance_days, month_start.date().isoformat(), extended_end)
            period_cache[period_key] = [period for period in periods if month_start <= period.signal_date <= month_end]
        periods = period_cache[period_key]
        _, curve = factory.evaluate_periods(periods, weights, top_n, rebalance_days)
        if not curve.empty:
            curve["rolling_month"] = month_start.strftime("%Y-%m")
            curve["weights"] = json.dumps(weights, sort_keys=True)
            monthly_curves.append(curve)
    curve = restitch_curve(monthly_curves)
    summary = summarize_curve(curve, periods_per_year=252 / rebalance_days)
    summary.update(
        {
            "candidate_id": candidate["candidate_id"],
            "factors": candidate["factors"],
            "top_n": top_n,
            "rebalance_days": rebalance_days,
            "train_years": train_years,
            "oos_start": oos_start,
            "oos_end": oos_end,
        }
    )
    return summary, curve


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
    parser.add_argument("--candidates", default=r"E:\quant-agent-team-us\research\2026-07-12-factory-round4\factory_qualified_candidates.csv")
    parser.add_argument("--out-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-rolling-round4")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--oos-start", default="2025-06-30")
    parser.add_argument("--oos-end", default="2026-06-29")
    parser.add_argument("--train-years", type=int, default=2)
    parser.add_argument("--universe-mode", choices=["current_snapshot", "dynamic_liquidity", "pit"], default="current_snapshot")
    parser.add_argument("--pit-membership")
    parser.add_argument("--pit-universes", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ["rolling_*", "curve_*.csv"]:
        for path in out_dir.glob(pattern):
            if path.is_file():
                path.unlink()

    pit_universes = [item.strip() for item in args.pit_universes.split(",") if item.strip()]
    panel, _, panel_manifest, membership = factory.load_panel(
        Path(args.raw_dir),
        universe_mode=args.universe_mode,
        pit_membership_path=Path(args.pit_membership) if args.pit_membership else None,
        pit_universes=pit_universes or None,
    )
    if membership is not None:
        membership.to_csv(out_dir / f"universe_membership_{args.universe_mode}.csv", index=False)
    context = factory.make_eval_context(panel)
    candidates = pd.read_csv(args.candidates).head(args.top_k)
    summaries = []
    ic_cache: dict[tuple[int, str, str], dict[str, float]] = {}
    period_cache: dict[tuple[int, str, str], list[factory.PeriodSlice]] = {}
    for idx, candidate in candidates.iterrows():
        summary, curve = rolling_validate_candidate(
            panel,
            context,
            candidate,
            args.oos_start,
            args.oos_end,
            args.train_years,
            ic_cache=ic_cache,
            period_cache=period_cache,
        )
        summaries.append(summary)
        if not curve.empty:
            curve.to_csv(out_dir / f"curve_{idx:03d}_{str(candidate['candidate_id'])[:80]}.csv", index=False)

    summary_frame = pd.DataFrame(summaries).sort_values("ir", ascending=False)
    summary_frame.to_csv(out_dir / "rolling_summary.csv", index=False)
    manifest = {
        "raw_dir": args.raw_dir,
        "candidates": args.candidates,
        "top_k": args.top_k,
        "oos_start": args.oos_start,
        "oos_end": args.oos_end,
        "train_years": args.train_years,
        "panel": panel_manifest,
        "universe_mode": args.universe_mode,
        "pit_membership": args.pit_membership,
        "pit_universes": pit_universes,
        "note": "Monthly rolling validation recomputes IC weights using only data before each month. Structural top_n/rebalance_days are fixed from the candidate factory result.",
    }
    (out_dir / "rolling_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(summary_frame.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
