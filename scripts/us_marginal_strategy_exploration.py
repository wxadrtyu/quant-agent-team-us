from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

import us_explore_strategy_rounds as rounds
import us_live_pool
import us_strategy_factory_loop as factory


RAW_DIR = Path(r"E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart")
RESEARCH_DIR = Path(r"E:\quant-agent-team-us\research")
DB_PATH = RESEARCH_DIR / "us_strategy_research.duckdb"


PREFERRED_MARGINAL_SETS = [
    {"ret_60d", "ret_5d", "px_to_ma60", "cmf_10", "parkinson_vol_20d"},
    {"ret_20d", "ret_5d", "px_to_ma20", "mfi_14", "ret_skew_20d"},
    {"overnight_gap_1d", "ret_5d", "volume_ma_ratio_5_20", "kurtosis_20d", "dollar_volume_20d"},
    {"ret_120d", "drawdown_5d", "ma20_above_ma60", "obv_change_20", "atr_20d"},
]
AVOID_CORE_ONLY = {"ret_120d", "ret_5d", "px_to_ma60", "turnover_stability_20d"}
CROWD_LIMIT_SYMBOLS = {
    "ARM",
    "ON",
    "DELL",
    "HON",
    "SNX",
    "QCOM",
    "VIRT",
    "LBRDK",
    "ALB",
    "ORCL",
    "JEF",
    "CAR",
    "CLF",
    "DUOL",
    "IBKR",
}


def load_current_baskets() -> dict[str, set[str]]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        holdings = con.execute("select monitor_key, 股票代码 from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()
    return {
        str(key): set(group["股票代码"].astype(str))
        for key, group in holdings.groupby("monitor_key", dropna=False)
    }


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def marginal_prior(prefix: str, names: set[str], top_n: int, rebalance_days: int) -> float:
    score = 0.0
    for preferred in PREFERRED_MARGINAL_SETS:
        score += 1.7 * len(names & preferred) / len(preferred)
    if names == AVOID_CORE_ONLY or AVOID_CORE_ONLY.issubset(names):
        score -= 2.5
    if "dollar_volume_20d" in names and "turnover_stability_20d" not in names:
        score += 0.8
    if "overnight_gap_1d" in names or "intraday_ret_1d" in names:
        score += 0.8
    if {"cmf_10", "cmf_20", "mfi_7", "mfi_14", "obv_change_20"} & names:
        score += 0.6
    if {"ret_skew_20d", "kurtosis_20d"} & names:
        score += 0.5
    if prefix in {"microrev", "microtrend"}:
        score += 1.1
    if prefix in {"balanced", "pulltrend"}:
        score += 0.4
    score += {5: 0.6, 7: 0.7, 10: 0.6, 20: 0.1}.get(top_n, 0.0)
    score += {5: 0.7, 10: 0.5, 20: 0.4}.get(rebalance_days, 0.0)
    return score


def max_current_overlap(candidate_basket: set[str], current_baskets: dict[str, set[str]]) -> tuple[float, str]:
    best_key = ""
    best = 0.0
    for key, basket in current_baskets.items():
        value = jaccard(candidate_basket, basket)
        if value > best:
            best = value
            best_key = key
    return best, best_key


def generate_marginal_pool(
    panel: pd.DataFrame,
    limit: int,
    seen: set[tuple[str, int, int]],
    current_baskets: dict[str, set[str]],
    max_signal_overlap: float,
) -> pd.DataFrame:
    live_frame, signal_date, _, _ = us_live_pool.build_live_period(panel, signal_date="2026-06-30", valuation_date="2026-07-16")
    benchmark_ret = float(live_frame["asset_ret"].mean())
    rebalance_choices = [5, 10, 20]
    top_choices = [5, 7, 10, 20]
    ics = factory.precompute_factor_ics(panel, "2023-06-30", "2025-06-29", rebalance_choices)
    rows: list[dict[str, object]] = []
    for candidate_id, factors in factory.candidate_hypotheses(limit):
        prefix = candidate_id.split("_", 1)[0]
        names = [factor.name for factor in factors]
        name_set = set(names)
        if len(name_set & {"px_to_ma20", "px_to_ma60", "ma20_above_ma60", "macd_hist"}) == 0:
            continue
        if len(name_set & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d", "ret_skew_20d", "kurtosis_20d"}) == 0:
            continue
        if len(name_set & {"ret_20d", "ret_60d", "ret_120d", "mom_252_21", "ret_5d", "ret_10d", "drawdown_5d", "overnight_gap_1d"}) < 2:
            continue
        for rebalance_days in rebalance_choices:
            weights = factory.ic_weights_from_values(factors, ics[rebalance_days])
            scores = factory.score_panel(live_frame, weights)
            ic_score = sum(weights.get(name, 0.0) * ics[rebalance_days].get(name, 0.0) for name in names)
            for top_n in top_choices:
                key = (candidate_id[:180], top_n, rebalance_days)
                if key in seen:
                    continue
                basket = set(live_frame.loc[scores.nlargest(top_n).index, "symbol"].astype(str))
                trade = live_frame.loc[scores.nlargest(top_n).index].copy()
                strategy_ret = float(trade["asset_ret"].mean())
                live_excess = (1.0 + strategy_ret) / (1.0 + benchmark_ret) - 1.0
                if live_excess <= 0:
                    continue
                overlap, overlap_key = max_current_overlap(basket, current_baskets)
                if overlap > max_signal_overlap:
                    continue
                crowded_hits = len(basket & CROWD_LIMIT_SYMBOLS)
                prior = marginal_prior(prefix, name_set, top_n, rebalance_days)
                rows.append(
                    {
                        "candidate_id": candidate_id[:180],
                        "factors": ";".join(names),
                        "weights": json.dumps(weights, sort_keys=True),
                        "max_factor_weight": max(weights.values()),
                        "effective_factor_count": 1.0 / sum(value * value for value in weights.values()),
                        "top_n": top_n,
                        "rebalance_days": rebalance_days,
                        "signal_date": signal_date,
                        "max_current_signal_overlap": overlap,
                        "nearest_current_monitor_key": overlap_key,
                        "crowded_symbol_hits": crowded_hits,
                        "live_strategy_return": strategy_ret,
                        "live_benchmark_return": benchmark_ret,
                        "live_excess_return": live_excess,
                        "factory_prior_score": prior,
                        "factory_ic_score": ic_score,
                        "final_score": prior
                        + ic_score * 100.0
                        + live_excess * 140.0
                        - max(weights.values()) * 0.30
                        - overlap * 2.2
                        - crowded_hits * 0.65,
                    }
                )
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(
        ["final_score", "live_excess_return", "max_current_signal_overlap", "effective_factor_count"],
        ascending=[False, False, True, False],
    ).reset_index(drop=True)
    return frame


def write_round_candidates(pool: pd.DataFrame, start_round: int, rounds_count: int, per_round: int) -> list[tuple[int, Path, str]]:
    out: list[tuple[int, Path, str]] = []
    cursor = 0
    for round_no in range(start_round, start_round + rounds_count):
        chunk = pool.iloc[cursor : cursor + per_round].copy()
        if chunk.empty:
            break
        cursor += per_round
        label = f"round{round_no}-marginal-compact"
        path = RESEARCH_DIR / f"2026-07-15-{label}-candidates.csv"
        chunk.to_csv(path, index=False)
        out.append((round_no, path, label))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-round", type=int, default=83)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--candidate-limit", type=int, default=140000)
    parser.add_argument("--candidates-per-round", type=int, default=44)
    parser.add_argument("--rolling-top-k", type=int, default=22)
    parser.add_argument("--null-top-k", type=int, default=22)
    parser.add_argument("--null-iter", type=int, default=1800)
    parser.add_argument("--max-signal-overlap", type=float, default=0.70)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    panel, _, _, _ = factory.load_panel(RAW_DIR, universe_mode="dynamic_liquidity")
    context = factory.make_eval_context(panel)
    seen = rounds.load_seen_keys()
    current_baskets = load_current_baskets()
    pool = generate_marginal_pool(panel, args.candidate_limit, seen, current_baskets, args.max_signal_overlap)
    pool_path = RESEARCH_DIR / f"2026-07-15-marginal-compact-pool-round{args.start_round}-{args.start_round + args.rounds - 1}.csv"
    pool.to_csv(pool_path, index=False)

    round_files = write_round_candidates(pool, args.start_round, args.rounds, args.candidates_per_round)
    summary_rows = []
    for round_no, candidates_path, label in round_files:
        rolling_dir = RESEARCH_DIR / f"2026-07-15-rolling-{label}"
        null_dir = RESEARCH_DIR / f"2026-07-15-null-{label}"
        rolling_summary = rounds.run_rolling(panel, context, candidates_path, rolling_dir, args.rolling_top_k)
        null_summary = rounds.run_null(context, rolling_dir, rolling_summary, null_dir, args.null_top_k, args.null_iter, args.seed + round_no * 100)
        promoted = {"round": round_no, "strategies": 0, "holdings": 0}
        if not rolling_summary.empty and not null_summary.empty:
            promoted = rounds.promote_round(
                round_no,
                label,
                candidates_path,
                rolling_dir / "rolling_summary.csv",
                null_dir / "null_overfit_summary.csv",
            )
        summary_rows.append(
            {
                "round": round_no,
                "candidates_path": str(candidates_path),
                "best_rolling_ir": float(pd.to_numeric(rolling_summary.get("ir"), errors="coerce").max()) if not rolling_summary.empty else 0.0,
                "best_random_pvalue": float(pd.to_numeric(null_summary.get("pvalue_ir"), errors="coerce").min()) if not null_summary.empty else None,
                "promoted_strategies": int(promoted.get("strategies", 0)),
                "promoted_holdings": int(promoted.get("holdings", 0)),
            }
        )
        print(json.dumps(summary_rows[-1], ensure_ascii=False))

    summary = pd.DataFrame(summary_rows)
    summary_path = RESEARCH_DIR / f"2026-07-15-marginal-compact-round{args.start_round}-{args.start_round + args.rounds - 1}-summary.csv"
    summary.to_csv(summary_path, index=False)
    print(json.dumps({"pool": str(pool_path), "summary": str(summary_path), "rounds": len(summary)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
