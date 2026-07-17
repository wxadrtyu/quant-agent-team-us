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

DRAG_SYMBOLS = {
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
}
PREFERRED_PREFIXES = {"qmv", "mr", "microrev", "defensive", "balanced", "qm"}
DEPRIORITIZED_PREFIXES = {"pulltrend", "microtrend"}


def load_current_baskets() -> dict[str, set[str]]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        holdings = con.execute("select monitor_key, 股票代码 from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()
    return {str(key): set(group["股票代码"].astype(str)) for key, group in holdings.groupby("monitor_key")}


def load_sector_map() -> dict[str, str]:
    meta = pd.read_csv(RAW_DIR / "us_stock_meta.csv")
    return dict(zip(meta["symbol"].astype(str), meta["sector"].fillna("未知").astype(str)))


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def max_overlap(basket: set[str], current_baskets: dict[str, set[str]]) -> float:
    best = 0.0
    for current in current_baskets.values():
        best = max(best, jaccard(basket, current))
    return best


def sector_concentration(symbols: list[str], sector_map: dict[str, str]) -> tuple[float, int]:
    sectors = [sector_map.get(symbol, "未知") for symbol in symbols]
    if not sectors:
        return 1.0, 0
    counts = pd.Series(sectors).value_counts()
    return float(counts.iloc[0] / len(sectors)), int(len(counts))


def diversified_prior(prefix: str, names: set[str], top_n: int, rebalance_days: int) -> float:
    score = 0.0
    if prefix in PREFERRED_PREFIXES:
        score += 1.4
    if prefix in DEPRIORITIZED_PREFIXES:
        score -= 0.8
    if {"cmf_10", "cmf_20", "mfi_7", "mfi_14", "obv_change_20"} & names:
        score += 0.7
    if {"dollar_volume_20d", "turnover_stability_20d"} & names:
        score += 0.4
    if {"ret_skew_20d", "vol_20d", "atr_20d", "parkinson_vol_20d"} & names:
        score += 0.5
    if "ma20_above_ma60" in names and "kurtosis_20d" in names:
        score -= 0.7
    score += {5: 0.7, 7: 1.0, 10: 0.2, 20: 0.9}.get(top_n, 0.0)
    score += {5: 0.4, 10: 0.4, 20: 0.8}.get(rebalance_days, 0.0)
    return score


def generate_pool(panel: pd.DataFrame, limit: int, seen: set[tuple[str, int, int]], max_overlap_value: float) -> pd.DataFrame:
    live_frame, signal_date, _, _ = us_live_pool.build_live_period(panel, signal_date="2026-06-30", valuation_date="2026-07-16")
    benchmark_ret = float(live_frame["asset_ret"].mean())
    sector_map = load_sector_map()
    current_baskets = load_current_baskets()
    rebalance_choices = [5, 10, 20]
    top_choices = [5, 7, 20]
    ics = factory.precompute_factor_ics(panel, "2023-06-30", "2025-06-29", rebalance_choices)
    rows = []
    for candidate_id, factors in factory.candidate_hypotheses(limit):
        prefix = candidate_id.split("_", 1)[0]
        names = [factor.name for factor in factors]
        name_set = set(names)
        if prefix in {"pulltrend", "microtrend"} and len(name_set & {"cmf_10", "cmf_20", "mfi_7", "mfi_14", "obv_change_20"}) == 0:
            continue
        if len(name_set & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d", "ret_skew_20d"}) == 0:
            continue
        for rebalance_days in rebalance_choices:
            weights = factory.ic_weights_from_values(factors, ics[rebalance_days])
            scores = factory.score_panel(live_frame, weights)
            ic_score = sum(weights.get(name, 0.0) * ics[rebalance_days].get(name, 0.0) for name in names)
            for top_n in top_choices:
                key = (candidate_id[:180], top_n, rebalance_days)
                if key in seen:
                    continue
                picks = live_frame.loc[scores.nlargest(top_n).index].copy()
                symbols = picks["symbol"].astype(str).tolist()
                basket = set(symbols)
                overlap = max_overlap(basket, current_baskets)
                if overlap > max_overlap_value:
                    continue
                max_sector_weight, sector_count = sector_concentration(symbols, sector_map)
                if top_n >= 7 and max_sector_weight > 0.50:
                    continue
                if top_n == 20 and sector_count < 5:
                    continue
                drag_hits = len(basket & DRAG_SYMBOLS)
                if top_n <= 7 and drag_hits > 1:
                    continue
                if top_n == 20 and drag_hits > 3:
                    continue
                strategy_ret = float(picks["asset_ret"].mean())
                live_excess = (1.0 + strategy_ret) / (1.0 + benchmark_ret) - 1.0
                if live_excess <= 0:
                    continue
                prior = diversified_prior(prefix, name_set, top_n, rebalance_days)
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
                        "max_sector_weight": max_sector_weight,
                        "sector_count": sector_count,
                        "drag_symbol_hits": drag_hits,
                        "live_strategy_return": strategy_ret,
                        "live_benchmark_return": benchmark_ret,
                        "live_excess_return": live_excess,
                        "factory_prior_score": prior,
                        "factory_ic_score": ic_score,
                        "final_score": prior
                        + ic_score * 100.0
                        + live_excess * 160.0
                        - overlap * 2.5
                        - max_sector_weight * 1.4
                        - drag_hits * 0.7
                        - max(weights.values()) * 0.25,
                    }
                )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["final_score", "live_excess_return", "max_sector_weight", "max_current_signal_overlap"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)


def write_round_candidates(pool: pd.DataFrame, start_round: int, rounds_count: int, per_round: int) -> list[tuple[int, Path, str]]:
    out = []
    cursor = 0
    for round_no in range(start_round, start_round + rounds_count):
        chunk = pool.iloc[cursor : cursor + per_round].copy()
        if chunk.empty:
            break
        cursor += per_round
        label = f"round{round_no}-diversified-live"
        path = RESEARCH_DIR / f"2026-07-17-{label}-candidates.csv"
        chunk.to_csv(path, index=False)
        out.append((round_no, path, label))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-round", type=int, default=239)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--candidate-limit", type=int, default=35000)
    parser.add_argument("--candidates-per-round", type=int, default=24)
    parser.add_argument("--rolling-top-k", type=int, default=12)
    parser.add_argument("--null-top-k", type=int, default=12)
    parser.add_argument("--null-iter", type=int, default=700)
    parser.add_argument("--max-overlap", type=float, default=0.55)
    parser.add_argument("--seed", type=int, default=20260731)
    args = parser.parse_args()

    panel, _, _, _ = factory.load_panel(RAW_DIR, universe_mode="dynamic_liquidity")
    context = factory.make_eval_context(panel)
    pool = generate_pool(panel, args.candidate_limit, rounds.load_seen_keys(), args.max_overlap)
    pool_path = RESEARCH_DIR / f"2026-07-17-diversified-live-pool-round{args.start_round}-{args.start_round + args.rounds - 1}.csv"
    pool.to_csv(pool_path, index=False)
    round_files = write_round_candidates(pool, args.start_round, args.rounds, args.candidates_per_round)
    summary_rows = []
    for round_no, candidates_path, label in round_files:
        rolling_dir = RESEARCH_DIR / f"2026-07-17-rolling-{label}"
        null_dir = RESEARCH_DIR / f"2026-07-17-null-{label}"
        rolling_summary = rounds.run_rolling(panel, context, candidates_path, rolling_dir, args.rolling_top_k)
        null_summary = rounds.run_null(context, rolling_dir, rolling_summary, null_dir, args.null_top_k, args.null_iter, args.seed + round_no * 100)
        promoted = {"round": round_no, "strategies": 0, "holdings": 0}
        if not rolling_summary.empty and not null_summary.empty:
            promoted = rounds.promote_round(round_no, label, candidates_path, rolling_dir / "rolling_summary.csv", null_dir / "null_overfit_summary.csv")
        row = {
            "round": round_no,
            "best_rolling_ir": float(pd.to_numeric(rolling_summary.get("ir"), errors="coerce").max()) if not rolling_summary.empty else 0.0,
            "best_random_pvalue": float(pd.to_numeric(null_summary.get("pvalue_ir"), errors="coerce").min()) if not null_summary.empty else None,
            "promoted_strategies": int(promoted.get("strategies", 0)),
            "promoted_holdings": int(promoted.get("holdings", 0)),
        }
        summary_rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    summary_path = RESEARCH_DIR / f"2026-07-17-diversified-live-round{args.start_round}-{args.start_round + args.rounds - 1}-summary.csv"
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(json.dumps({"pool": str(pool_path), "summary": str(summary_path), "rounds": len(summary_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
