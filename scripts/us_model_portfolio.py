from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def cap_and_redistribute(weights: pd.Series, cap: float, tolerance: float = 1e-12) -> pd.Series:
    if weights.empty:
        return weights.astype(float)
    if cap <= 0:
        raise ValueError("cap must be positive")
    if cap * len(weights) < 1.0 - tolerance:
        raise ValueError("cap is too low to allocate 100% across the available symbols")

    capped = weights.astype(float).clip(lower=0)
    total = float(capped.sum())
    if total <= 0:
        raise ValueError("weights must have a positive sum")
    capped = capped / total

    for _ in range(len(capped) + 2):
        over = capped > cap + tolerance
        if not bool(over.any()):
            return capped / float(capped.sum())
        excess = float((capped[over] - cap).sum())
        capped[over] = cap
        under = ~over
        under_sum = float(capped[under].sum())
        if under_sum <= tolerance:
            return capped / float(capped.sum())
        capped[under] += capped[under] / under_sum * excess

    return capped.clip(upper=cap) / float(capped.clip(upper=cap).sum())


def _strategy_sleeves(strategies: pd.DataFrame) -> pd.DataFrame:
    required = {"sid", "role"}
    missing = required - set(strategies.columns)
    if missing:
        raise ValueError(f"strategies missing columns: {sorted(missing)}")

    frame = strategies.copy()
    frame["role"] = frame["role"].fillna("").astype(str)
    primary = frame[frame["role"].str.lower().eq("primary")].copy()
    if "status" in primary.columns:
        primary = primary[primary["status"].fillna("").astype(str).str.contains("paper_live_ready", case=False)]
    if primary.empty:
        raise ValueError("no primary paper-live strategies found")

    primary = primary.sort_values(["rolling_ir", "sid"], ascending=[False, True], na_position="last").reset_index(drop=True)
    primary["sleeve_weight"] = 1.0 / len(primary)
    return primary[["sid", "sleeve_weight"]]


def aggregate_model_portfolio(
    strategies: pd.DataFrame,
    signals: pd.DataFrame,
    max_symbol_weight: float = 0.08,
) -> pd.DataFrame:
    required = {"sid", "symbol", "weight", "signal_date", "intended_entry"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"signals missing columns: {sorted(missing)}")

    sleeves = _strategy_sleeves(strategies)
    frame = signals.merge(sleeves, on="sid", how="inner").copy()
    if frame.empty:
        raise ValueError("no latest signals matched primary strategies")
    frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce").fillna(0.0).clip(lower=0)
    frame = frame[frame["weight"] > 0].copy()
    if frame.empty:
        raise ValueError("primary strategy signals have no positive weights")

    per_sid_total = frame.groupby("sid")["weight"].transform("sum")
    frame = frame[per_sid_total > 0].copy()
    frame["normalized_signal_weight"] = frame["weight"] / per_sid_total[per_sid_total > 0]
    frame["pre_cap_weight"] = frame["sleeve_weight"] * frame["normalized_signal_weight"]

    grouped = (
        frame.groupby("symbol", as_index=False)
        .agg(
            pre_cap_weight=("pre_cap_weight", "sum"),
            contributing_sids=("sid", lambda values: ";".join(sorted(set(map(str, values))))),
            signal_date=("signal_date", "max"),
            intended_entry=("intended_entry", "max"),
        )
        .sort_values("pre_cap_weight", ascending=False)
        .reset_index(drop=True)
    )
    capped = cap_and_redistribute(grouped.set_index("symbol")["pre_cap_weight"], cap=max_symbol_weight)
    grouped["target_weight"] = grouped["symbol"].map(capped)
    grouped["cap_binding"] = grouped["pre_cap_weight"] > max_symbol_weight
    grouped["status"] = "paper_live_ready_pending_human_review"
    grouped["active_monitoring_status"] = "blocked_pending_pit_universe"
    grouped = grouped.sort_values(["target_weight", "symbol"], ascending=[False, True]).reset_index(drop=True)
    grouped.insert(0, "rank", range(1, len(grouped) + 1))
    return grouped[
        [
            "rank",
            "symbol",
            "target_weight",
            "pre_cap_weight",
            "cap_binding",
            "contributing_sids",
            "signal_date",
            "intended_entry",
            "status",
            "active_monitoring_status",
        ]
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", default=r"G:\quant-agent-team-us\reports\us\export")
    parser.add_argument("--date", default="20260712")
    parser.add_argument("--max-symbol-weight", type=float, default=0.08)
    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    strategies_path = export_dir / f"paper_live_pool_diversified_{args.date}.csv"
    signals_path = export_dir / f"paper_live_pool_latest_signals_{args.date}.csv"
    strategies = pd.read_csv(strategies_path)
    signals = pd.read_csv(signals_path)

    portfolio = aggregate_model_portfolio(strategies, signals, max_symbol_weight=args.max_symbol_weight)
    out_path = export_dir / f"paper_live_model_portfolio_{args.date}.csv"
    portfolio.to_csv(out_path, index=False)

    primary_count = int(strategies["role"].fillna("").astype(str).str.lower().eq("primary").sum())
    manifest = {
        "output": str(out_path),
        "strategy_file": str(strategies_path),
        "signal_file": str(signals_path),
        "primary_strategies": primary_count,
        "symbols": int(len(portfolio)),
        "max_symbol_weight": args.max_symbol_weight,
        "total_weight": float(portfolio["target_weight"].sum()),
        "largest_weight": float(portfolio["target_weight"].max()),
        "status": "paper_live_ready_pending_human_review",
        "active_monitoring_status": "blocked_pending_pit_universe",
    }
    (export_dir / f"paper_live_model_portfolio_{args.date}.manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
