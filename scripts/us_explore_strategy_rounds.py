from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

import us_live_pool
import us_null_overfit_check as null_check
import us_rolling_validation as rolling
import us_strategy_factory_loop as factory


RAW_DIR = Path(r"E:\quant-agent-team-us\data\us\raw\2026-07-24-intraday-chart")
RESEARCH_DIR = Path(r"E:\quant-agent-team-us\research")
REPORT_DIR = Path(r"G:\quant-agent-team-us\reports\us\live")
DB_PATH = RESEARCH_DIR / "us_strategy_research.duckdb"
LIVE_SIGNAL_DATE = "2026-06-30"
LIVE_VALUATION_DATE = "2026-07-24"
ARTIFACT_DATE = LIVE_VALUATION_DATE
MONITOR_RUN_DATE = LIVE_VALUATION_DATE


PREFERRED_SETS = [
    {"ret_5d", "px_to_ma60", "ret_120d", "turnover_stability_20d"},
    {"ret_5d", "px_to_ma60", "mom_252_21", "turnover_stability_20d"},
    {"overnight_gap_1d", "px_to_ma60", "ret_120d", "turnover_stability_20d"},
    {"overnight_gap_1d", "px_to_ma60", "mom_252_21", "turnover_stability_20d"},
]
RISK_STABILIZERS = {"atr_20d", "parkinson_vol_20d", "vol_20d", "ret_skew_20d", "kurtosis_20d"}
FLOW_FACTORS = {"mfi_7", "mfi_14", "cmf_10", "cmf_20", "obv_change_20", "volume_ma_ratio_5_20"}
TREND_FACTORS = {"px_to_ma20", "px_to_ma60", "ma20_above_ma60", "macd_hist"}
MOMENTUM_FACTORS = {"ret_60d", "ret_120d", "mom_252_21"}
SHORT_PULLBACK_FACTORS = {"ret_5d", "ret_10d", "drawdown_5d", "drawdown_10d", "overnight_gap_1d"}


def candidate_key(row: pd.Series) -> tuple[str, int, int]:
    return str(row["candidate_id"]), int(row["top_n"]), int(row["rebalance_days"])


def load_seen_keys() -> set[tuple[str, int, int]]:
    seen: set[tuple[str, int, int]] = set()
    if DB_PATH.exists():
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            for table in ["us_live_pool_strategies", "us_live_pool_candidate_review"]:
                exists = con.execute("select count(*) from information_schema.tables where table_name = ?", [table]).fetchone()[0]
                if not exists:
                    continue
                frame = con.execute(f"select * from {table}").fetchdf()
                if {"candidate_id", "top_n_numeric", "rebalance_days_numeric"}.issubset(frame.columns):
                    for row in frame.itertuples(index=False):
                        seen.add((str(row.candidate_id), int(row.top_n_numeric), int(row.rebalance_days_numeric)))
                elif {"candidate_id", "持仓数量", "调仓周期"}.issubset(frame.columns):
                    for row in frame.itertuples(index=False):
                        period = str(getattr(row, "调仓周期")).replace("日", "")
                        if period.isdigit():
                            seen.add((str(row.candidate_id), int(getattr(row, "持仓数量")), int(period)))
        finally:
            con.close()
    for path in RESEARCH_DIR.glob("*candidates.csv"):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if {"candidate_id", "top_n", "rebalance_days"}.issubset(frame.columns):
            for _, row in frame.iterrows():
                seen.add(candidate_key(row))
    return seen


def structural_prior(prefix: str, names: set[str], top_n: int, rebalance_days: int) -> float:
    score = 0.0
    for preferred in PREFERRED_SETS:
        score += 1.8 * len(names & preferred) / len(preferred)
    score += 0.7 * len(names & RISK_STABILIZERS)
    score += 0.6 * len(names & FLOW_FACTORS)
    score += 0.8 * len(names & TREND_FACTORS)
    score += 0.8 * len(names & MOMENTUM_FACTORS)
    score += 0.9 * len(names & SHORT_PULLBACK_FACTORS)
    if "turnover_stability_20d" in names:
        score += 1.2
    if "px_to_ma60" in names:
        score += 1.0
    if {"ret_5d", "ret_120d"}.issubset(names) or {"ret_5d", "mom_252_21"}.issubset(names):
        score += 1.0
    if {"ret_skew_20d", "kurtosis_20d"}.issubset(names):
        score += 0.5
    if prefix in {"pulltrend", "microtrend"}:
        score += 1.2
    if prefix in {"balanced", "qmv"}:
        score += 0.4
    score += {5: 0.3, 7: 0.5, 10: 0.7, 20: 0.2}.get(top_n, 0.0)
    score += {5: 0.8, 10: 0.6, 20: 0.4}.get(rebalance_days, 0.0)
    return score


def generate_candidate_pool(panel: pd.DataFrame, limit: int, seen: set[tuple[str, int, int]]) -> pd.DataFrame:
    rebalance_choices = [5, 10, 20]
    top_choices = [5, 7, 10]
    ics = factory.precompute_factor_ics(panel, "2023-06-30", "2025-06-29", rebalance_choices)
    rows = []
    for candidate_id, factors in factory.candidate_hypotheses(limit):
        prefix = candidate_id.split("_", 1)[0]
        names = [factor.name for factor in factors]
        name_set = set(names)
        if len(name_set & TREND_FACTORS) == 0 or len(name_set & RISK_STABILIZERS) == 0:
            continue
        if len(name_set & (MOMENTUM_FACTORS | SHORT_PULLBACK_FACTORS)) < 2:
            continue
        for rebalance_days in rebalance_choices:
            weights = factory.ic_weights_from_values(factors, ics[rebalance_days])
            ic_score = sum(weights.get(name, 0.0) * ics[rebalance_days].get(name, 0.0) for name in names)
            for top_n in top_choices:
                key = (candidate_id[:180], top_n, rebalance_days)
                if key in seen:
                    continue
                prior = structural_prior(prefix, name_set, top_n, rebalance_days)
                rows.append(
                    {
                        "candidate_id": candidate_id[:180],
                        "factors": ";".join(names),
                        "weights": json.dumps(weights, sort_keys=True),
                        "max_factor_weight": max(weights.values()),
                        "effective_factor_count": 1.0 / sum(value * value for value in weights.values()),
                        "top_n": top_n,
                        "rebalance_days": rebalance_days,
                        "factory_prior_score": prior,
                        "factory_ic_score": ic_score,
                        "final_score": prior + ic_score * 100.0 - max(weights.values()) * 0.25,
                    }
                )
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(["final_score", "effective_factor_count"], ascending=[False, False]).reset_index(drop=True)
    return frame


def write_round_candidates(pool: pd.DataFrame, start_round: int, rounds: int, per_round: int) -> list[tuple[int, Path, str]]:
    out = []
    cursor = 0
    for round_no in range(start_round, start_round + rounds):
        chunk = pool.iloc[cursor : cursor + per_round].copy()
        if chunk.empty:
            break
        cursor += per_round
        label = f"round{round_no}-quality-stability"
        path = RESEARCH_DIR / f"{ARTIFACT_DATE}-{label}-candidates.csv"
        chunk.to_csv(path, index=False)
        out.append((round_no, path, label))
    return out


def run_rolling(panel: pd.DataFrame, context: factory.EvalContext, candidates_path: Path, out_dir: Path, top_k: int) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ["rolling_*", "curve_*.csv"]:
        for path in out_dir.glob(pattern):
            if path.is_file():
                path.unlink()
    candidates = pd.read_csv(candidates_path).head(top_k)
    summaries = []
    ic_cache: dict[tuple[int, str, str], dict[str, float]] = {}
    period_cache: dict[tuple[int, str, str], list[factory.PeriodSlice]] = {}
    for idx, candidate in candidates.iterrows():
        summary, curve = rolling.rolling_validate_candidate(
            panel,
            context,
            candidate,
            "2025-06-30",
            "2026-06-29",
            2,
            ic_cache=ic_cache,
            period_cache=period_cache,
        )
        summaries.append(summary)
        if not curve.empty:
            curve.to_csv(out_dir / f"curve_{idx:03d}_{str(candidate['candidate_id'])[:80]}.csv", index=False)
    summary_frame = pd.DataFrame(summaries).sort_values("ir", ascending=False)
    summary_frame.to_csv(out_dir / "rolling_summary.csv", index=False)
    return summary_frame


def run_null(context: factory.EvalContext, rolling_dir: Path, summary: pd.DataFrame, out_dir: Path, top_k: int, n_iter: int, seed: int) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for offset, (_, candidate) in enumerate(summary.head(top_k).iterrows()):
        rows.append(null_check.check_candidate(context, rolling_dir, candidate, n_iter, seed + offset))
    results = pd.DataFrame(rows)
    if "pvalue_ir" in results:
        results = results.sort_values(["pvalue_ir", "observed_ir"], ascending=[True, False])
    results.to_csv(out_dir / "null_overfit_summary.csv", index=False)
    return results


def promote_round(round_no: int, label: str, candidates_path: Path, rolling_path: Path, null_path: Path) -> dict:
    run_id = f"{MONITOR_RUN_DATE}-monitor-round{round_no}-quality-stability"
    rolling_summary = pd.read_csv(rolling_path)
    random_checks = pd.read_csv(null_path) if null_path.exists() else pd.DataFrame()
    candidates = pd.read_csv(candidates_path)
    strategies = us_live_pool.select_live_pool(
        rolling_summary,
        random_checks,
        top_n=None,
        min_ir=1.50,
        min_deflated_z=1.85,
        max_random_pvalue=0.04,
        allowed_holdings=(5, 7, 10, 20),
    )
    panel, _, _, _ = factory.load_panel(RAW_DIR, universe_mode="dynamic_liquidity")
    live_frame, signal_date, entry_date, valuation_date = us_live_pool.build_live_period(
        panel,
        signal_date=LIVE_SIGNAL_DATE,
        valuation_date=LIVE_VALUATION_DATE,
    )
    holdings, live_metrics = us_live_pool.build_signal_holdings_and_live_metrics(
        strategies=strategies,
        candidates=candidates,
        live_frame=live_frame,
        signal_date=signal_date,
        entry_date=entry_date,
        valuation_date=valuation_date,
    )
    strategies = us_live_pool.enrich_strategies_with_live_metrics(strategies, live_metrics)
    strategies, holdings = us_live_pool.filter_live_outperformers(strategies, holdings)
    review = us_live_pool.build_candidate_review_table(candidates, strategies, rolling_summary, random_checks)
    us_live_pool.write_live_pool(DB_PATH, run_id, strategies, holdings, review)
    report_dir = REPORT_DIR / f"round{round_no}"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{ARTIFACT_DATE}-{label}.md"
    us_live_pool.write_report(strategies, holdings, review, report_path)
    us_live_pool._validate_outputs(DB_PATH, run_id, report_path, strategies, holdings)
    return {
        "round": round_no,
        "run_id": run_id,
        "strategies": int(len(strategies)),
        "holdings": int(len(holdings)),
        "best_rolling_ir": float(pd.to_numeric(rolling_summary["ir"], errors="coerce").max()) if not rolling_summary.empty else 0.0,
        "best_rolling_mdd": float(pd.to_numeric(rolling_summary.sort_values("ir", ascending=False).head(1)["mdd"], errors="coerce").iloc[0])
        if not rolling_summary.empty
        else 0.0,
        "best_null_pvalue": float(pd.to_numeric(random_checks.get("pvalue_ir"), errors="coerce").min()) if not random_checks.empty else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-round", type=int, default=23)
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--candidate-limit", type=int, default=120000)
    parser.add_argument("--candidates-per-round", type=int, default=42)
    parser.add_argument("--rolling-top-k", type=int, default=20)
    parser.add_argument("--null-top-k", type=int, default=20)
    parser.add_argument("--null-iter", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=20260713)
    args = parser.parse_args()

    panel, _, panel_manifest, membership = factory.load_panel(RAW_DIR, universe_mode="dynamic_liquidity")
    context = factory.make_eval_context(panel)
    seen = load_seen_keys()
    pool = generate_candidate_pool(panel, args.candidate_limit, seen)
    round_files = write_round_candidates(pool, args.start_round, args.rounds, args.candidates_per_round)
    summary_rows = []
    for round_no, candidates_path, label in round_files:
        rolling_dir = RESEARCH_DIR / f"{ARTIFACT_DATE}-rolling-{label}"
        null_dir = RESEARCH_DIR / f"{ARTIFACT_DATE}-null-{label}"
        rolling_summary = run_rolling(panel, context, candidates_path, rolling_dir, args.rolling_top_k)
        null_summary = run_null(context, rolling_dir, rolling_summary, null_dir, args.null_top_k, args.null_iter, args.seed + round_no * 100)
        passed = null_summary[
            (pd.to_numeric(null_summary.get("pvalue_ir"), errors="coerce") <= 0.04)
            & (pd.to_numeric(null_summary.get("pvalue_excess"), errors="coerce") <= 0.04)
            & (pd.to_numeric(null_summary.get("deflated_ir_z"), errors="coerce") >= 1.85)
        ]
        promoted = {"round": round_no, "strategies": 0, "holdings": 0}
        if not passed.empty:
            promoted = promote_round(
                round_no,
                label,
                candidates_path,
                rolling_dir / "rolling_summary.csv",
                null_dir / "null_overfit_summary.csv",
            )
        best = rolling_summary.sort_values(["ir", "excess_return"], ascending=[False, False]).head(1)
        summary_rows.append(
            {
                "round": round_no,
                "candidates": str(candidates_path),
                "rolling_dir": str(rolling_dir),
                "null_dir": str(null_dir),
                "best_candidate": "" if best.empty else str(best.iloc[0]["candidate_id"]),
                "best_ir": 0.0 if best.empty else float(best.iloc[0]["ir"]),
                "best_mdd": 0.0 if best.empty else float(best.iloc[0]["mdd"]),
                "best_excess_return": 0.0 if best.empty else float(best.iloc[0]["excess_return"]),
                "null_passed": int(len(passed)),
                "promoted_strategies": int(promoted.get("strategies", 0)),
                "promoted_holdings": int(promoted.get("holdings", 0)),
            }
        )
        summary_path = RESEARCH_DIR / f"{ARTIFACT_DATE}-quality-stability-round{args.start_round}-{args.start_round + args.rounds - 1}-summary.csv"
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
        print(json.dumps(summary_rows[-1], ensure_ascii=False))

    manifest = {
        "panel": panel_manifest,
        "membership_rows": 0 if membership is None else int(len(membership)),
        "seen_keys": len(seen),
        "candidate_pool_rows": int(len(pool)),
        "rounds_written": len(round_files),
        "anti_overfit_gates": {
            "rolling": "monthly OOS 2025-06-30..2026-06-29 with monthly IC refit using prior 2 years only",
            "null": f"same dates random top_n baskets, pvalue <= 0.04, deflated z >= 1.85, iterations {args.null_iter}",
            "live": "2026-06-30 signal to latest valuation, live excess return must be positive",
        },
    }
    manifest_path = RESEARCH_DIR / f"{ARTIFACT_DATE}-quality-stability-round{args.start_round}-{args.start_round + args.rounds - 1}-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
