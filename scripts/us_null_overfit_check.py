from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import us_strategy_factory_loop as factory
import us_rolling_validation as rolling


def empirical_pvalue(observed: float, null_values: np.ndarray) -> float:
    values = np.asarray(null_values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return 1.0
    return float((1 + np.sum(values >= observed)) / (len(values) + 1))


def simulate_random_curves(periods: list[pd.Series], top_n: int, n_iter: int, seed: int, periods_per_year: float = 252 / 20) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    summaries = []
    for _ in range(n_iter):
        rows = []
        equity = 1.0
        benchmark = 1.0
        for idx, period in enumerate(periods):
            returns = np.asarray(period["asset_returns"], dtype=float)
            if len(returns) < top_n:
                continue
            picked = rng.choice(len(returns), size=top_n, replace=False)
            strategy_ret = float(returns[picked].mean())
            benchmark_ret = float(period["benchmark_ret"])
            equity *= 1.0 + strategy_ret
            benchmark *= 1.0 + benchmark_ret
            rows.append(
                {
                    "entry_date": period.get("entry_date", f"2000-01-{idx + 1:02d}"),
                    "strategy_ret": strategy_ret,
                    "benchmark_ret": benchmark_ret,
                    "excess_ret": strategy_ret - benchmark_ret,
                    "equity": equity,
                    "benchmark_equity": benchmark,
                }
            )
        summaries.append(rolling.summarize_curve(pd.DataFrame(rows), periods_per_year=periods_per_year))
    return pd.DataFrame(summaries)


def period_returns_from_curve(context: factory.EvalContext, curve: pd.DataFrame) -> list[pd.Series]:
    out = []
    for row in curve.itertuples(index=False):
        signal_date = pd.Timestamp(row.signal_date)
        entry_date = pd.Timestamp(row.entry_date)
        exit_date = pd.Timestamp(row.exit_date)
        universe = context.by_date.get(signal_date)
        entry = context.by_date.get(entry_date)
        exit_frame = context.by_date.get(exit_date)
        if universe is None or entry is None or exit_frame is None:
            continue
        frame = universe[["symbol"]].merge(entry[["symbol", "open"]].rename(columns={"open": "entry"}), on="symbol")
        frame = frame.merge(exit_frame[["symbol", "open"]].rename(columns={"open": "exit"}), on="symbol")
        frame = frame[(frame["entry"] > 0) & (frame["exit"] > 0)]
        if len(frame) < int(row.n):
            continue
        asset_returns = (frame["exit"] / frame["entry"] - 1.0 - 0.002).to_numpy(dtype=float)
        out.append(
            pd.Series(
                {
                    "signal_date": row.signal_date,
                    "entry_date": row.entry_date,
                    "exit_date": row.exit_date,
                    "asset_returns": asset_returns,
                    "benchmark_ret": float(row.benchmark_ret),
                }
            )
        )
    return out


def find_curve_file(rolling_dir: Path, candidate_id: str) -> Path | None:
    for path in rolling_dir.glob("curve_*.csv"):
        if candidate_id[:80] in path.name:
            return path
    return None


def check_candidate(
    context: factory.EvalContext,
    rolling_dir: Path,
    candidate: pd.Series,
    n_iter: int,
    seed: int,
) -> dict:
    candidate_id = str(candidate["candidate_id"])
    curve_path = find_curve_file(rolling_dir, candidate_id)
    if curve_path is None:
        return {"candidate_id": candidate_id, "status": "missing_curve"}
    curve = pd.read_csv(curve_path)
    observed = rolling.summarize_curve(curve, periods_per_year=252 / int(candidate["rebalance_days"]))
    periods = period_returns_from_curve(context, curve)
    rebalance_days = int(candidate["rebalance_days"])
    sims = simulate_random_curves(periods, int(candidate["top_n"]), n_iter, seed, periods_per_year=252 / rebalance_days)
    null_ir = sims["ir"].to_numpy(dtype=float)
    null_excess = sims["excess_return"].to_numpy(dtype=float)
    ir_std = float(np.nanstd(null_ir, ddof=0))
    return {
        "candidate_id": candidate_id,
        "top_n": int(candidate["top_n"]),
        "rebalance_days": int(candidate["rebalance_days"]),
        "observed_excess_return": observed["excess_return"],
        "observed_ir": observed["ir"],
        "observed_mdd": observed["mdd"],
        "observed_win_excess": observed["win_excess"],
        "null_mean_ir": float(np.nanmean(null_ir)),
        "null_p95_ir": float(np.nanpercentile(null_ir, 95)),
        "null_p99_ir": float(np.nanpercentile(null_ir, 99)),
        "null_mean_excess": float(np.nanmean(null_excess)),
        "pvalue_ir": empirical_pvalue(observed["ir"], null_ir),
        "pvalue_excess": empirical_pvalue(observed["excess_return"], null_excess),
        "deflated_ir_z": 0.0 if ir_std <= 0 else float((observed["ir"] - np.nanmean(null_ir)) / ir_std),
        "null_iterations": int(len(sims)),
        "periods": int(len(curve)),
        "status": "checked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
    parser.add_argument("--rolling-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-rolling-round4")
    parser.add_argument("--rolling-summary", default=r"E:\quant-agent-team-us\research\2026-07-12-rolling-round4\rolling_summary.csv")
    parser.add_argument("--out-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-null-round4")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--n-iter", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--universe-mode", choices=["current_snapshot", "dynamic_liquidity", "pit"], default="current_snapshot")
    parser.add_argument("--pit-membership")
    parser.add_argument("--pit-universes", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
    rolling_summary = pd.read_csv(args.rolling_summary).head(args.top_k)
    rows = []
    for offset, (_, candidate) in enumerate(rolling_summary.iterrows()):
        rows.append(check_candidate(context, Path(args.rolling_dir), candidate, args.n_iter, args.seed + offset))
    results = pd.DataFrame(rows)
    if "pvalue_ir" in results:
        results = results.sort_values(["pvalue_ir", "observed_ir"], ascending=[True, False])
    results.to_csv(out_dir / "null_overfit_summary.csv", index=False)
    manifest = {
        "raw_dir": args.raw_dir,
        "rolling_dir": args.rolling_dir,
        "rolling_summary": args.rolling_summary,
        "top_k": args.top_k,
        "n_iter": args.n_iter,
        "seed": args.seed,
        "panel": panel_manifest,
        "universe_mode": args.universe_mode,
        "pit_membership": args.pit_membership,
        "pit_universes": pit_universes,
        "null_model": "same signal/entry/exit dates and top_n; randomly sample top_n names from each tradable period universe",
        "gate_hint": "prefer pvalue_ir <= 0.05, pvalue_excess <= 0.05, and deflated_ir_z >= 2 before live-pool promotion",
    }
    (out_dir / "null_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(results.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
