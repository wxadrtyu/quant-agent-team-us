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
    "CAR",
    "JEF",
    "CLF",
    "DUOL",
    "IBKR",
}
STRENGTH_FACTORS = {"ret_20d", "ret_60d", "ret_120d", "mom_252_21", "macd_hist", "px_to_ma20"}
QUALITY_FACTORS = {"turnover_stability_20d", "dollar_volume_20d", "vol_20d", "atr_20d", "parkinson_vol_20d"}
FLOW_FACTORS = {"cmf_10", "cmf_20", "mfi_7", "mfi_14", "obv_change_20", "volume_ma_ratio_5_20"}
REVERSAL_RISK_FACTORS = {"ret_5d", "ret_10d", "drawdown_5d", "drawdown_10d", "overnight_gap_1d"}
MICRO_PROTECTION_FACTORS = {"overnight_gap_1d", "intraday_ret_1d", "close_pos_20d", "range_pct_5d"}


def load_current_baskets() -> dict[str, set[str]]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        holdings = con.execute("select monitor_key, 股票代码 from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()
    return {str(key): set(group["股票代码"].astype(str)) for key, group in holdings.groupby("monitor_key", dropna=False)}


def load_pooled_strategy_keys() -> set[tuple[str, int, int]]:
    seen: set[tuple[str, int, int]] = set()
    if not DB_PATH.exists():
        return seen
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for table in ["us_live_pool_strategies", "us_live_monitoring_strategies_current"]:
            exists = con.execute("select count(*) from information_schema.tables where table_name = ?", [table]).fetchone()[0]
            if not exists:
                continue
            columns = set(con.execute(f"select * from {table} limit 0").fetchdf().columns)
            if {"candidate_id", "top_n_numeric", "rebalance_days_numeric"}.issubset(columns):
                frame = con.execute(f"select candidate_id, top_n_numeric, rebalance_days_numeric from {table}").fetchdf()
                for row in frame.itertuples(index=False):
                    seen.add((str(row.candidate_id), int(row.top_n_numeric), int(row.rebalance_days_numeric)))
    finally:
        con.close()
    return seen


def current_symbol_counts(current_baskets: dict[str, set[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for basket in current_baskets.values():
        for symbol in basket:
            counts[symbol] = counts.get(symbol, 0) + 1
    return counts


def load_current_symbol_exposure() -> dict[str, dict[str, float]]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
        strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
    finally:
        con.close()

    holdings_monitor_col = holdings.columns[1]
    symbol_col = holdings.columns[5]
    weight_col = holdings.columns[7]
    strategies_monitor_col = strategies.columns[31]
    winner_col = strategies.columns[37]
    frame = holdings[[holdings_monitor_col, symbol_col, weight_col]].merge(
        strategies[[strategies_monitor_col, winner_col]],
        left_on=holdings_monitor_col,
        right_on=strategies_monitor_col,
        how="left",
    )
    exposure: dict[str, dict[str, float]] = {}
    for row in frame.itertuples(index=False):
        symbol = str(getattr(row, symbol_col))
        values = exposure.setdefault(symbol, {"winner_weight": 0.0, "loser_weight": 0.0})
        weight = float(getattr(row, weight_col) or 0.0)
        if bool(getattr(row, winner_col)):
            values["winner_weight"] += weight
        else:
            values["loser_weight"] += weight
    return exposure


def diagnostic_support_metrics(symbols: list[str], exposure: dict[str, dict[str, float]], top_n: int) -> dict[str, float]:
    if not symbols:
        return {"winner_support_score": 0.0, "loser_exposure_score": 0.0, "net_support_score": 0.0}
    winner_weights = [float(exposure.get(symbol, {}).get("winner_weight", 0.0)) for symbol in symbols]
    loser_weights = [float(exposure.get(symbol, {}).get("loser_weight", 0.0)) for symbol in symbols]
    winner_support_score = sum(winner_weights) / len(symbols)
    loser_exposure_score = sum(loser_weights) / len(symbols)
    net_support_score = winner_support_score - loser_exposure_score
    if top_n == 20:
        net_support_score += min(1.0, sum(1 for value in winner_weights if value > 0) / 20.0) * 0.5
    return {
        "winner_support_score": float(winner_support_score),
        "loser_exposure_score": float(loser_exposure_score),
        "net_support_score": float(net_support_score),
    }


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def max_current_overlap(candidate_basket: set[str], current_baskets: dict[str, set[str]]) -> tuple[float, str]:
    best_key = ""
    best = 0.0
    for key, basket in current_baskets.items():
        overlap = jaccard(candidate_basket, basket)
        if overlap > best:
            best = overlap
            best_key = key
    return best, best_key


def holding_congestion_metrics(symbols: list[str], symbol_counts: dict[str, int], top_n: int) -> dict[str, float]:
    if not symbols:
        return {"holding_congestion_score": 0.0, "portfolio_breadth_bonus": 0.0}
    counts = [float(symbol_counts.get(symbol, 0)) for symbol in symbols]
    avg_count = sum(counts) / len(counts)
    max_count = max(counts)
    crowded_share = sum(1 for count in counts if count >= 3) / len(counts)
    unique_count = len(set(symbols))
    holding_congestion_score = avg_count * 0.18 + max_count * 0.08 + crowded_share * 0.90
    portfolio_breadth_bonus = 0.0
    if top_n == 20:
        portfolio_breadth_bonus = min(1.0, unique_count / 20.0) * 0.8
        if crowded_share == 0:
            portfolio_breadth_bonus += 0.4
    return {
        "holding_congestion_score": float(holding_congestion_score),
        "portfolio_breadth_bonus": float(portfolio_breadth_bonus),
    }


def load_sector_map() -> dict[str, str]:
    meta = pd.read_csv(RAW_DIR / "us_stock_meta.csv")
    return dict(zip(meta["symbol"].astype(str), meta["sector"].fillna("Unknown").astype(str)))


def sector_strength_scores(live_frame: pd.DataFrame, sector_map: dict[str, str], benchmark_ret: float) -> dict[str, float]:
    frame = live_frame[["symbol", "asset_ret"]].copy()
    frame["sector"] = frame["symbol"].astype(str).map(sector_map).fillna("Unknown")
    sector_returns = frame.groupby("sector")["asset_ret"].mean()
    return {str(sector): float(value - benchmark_ret) for sector, value in sector_returns.items()}


def sector_rotation_metrics(
    symbols: list[str],
    sector_map: dict[str, str],
    sector_scores: dict[str, float],
    top_n: int,
) -> dict[str, float]:
    if not symbols:
        return {
            "sector_rotation_score": 0.0,
            "sector_breadth_bonus": 0.0,
            "sector_concentration_penalty": 0.0,
        }
    sectors = [sector_map.get(symbol, "Unknown") for symbol in symbols]
    counts = pd.Series(sectors).value_counts()
    max_share = float(counts.iloc[0] / len(sectors))
    breadth = int(len(counts))
    sector_rotation_score = float(sum(sector_scores.get(sector, 0.0) for sector in sectors) / len(sectors))
    sector_breadth_bonus = 0.0
    if top_n == 20:
        sector_breadth_bonus = min(1.0, breadth / 6.0) * 0.8
        if max_share <= 0.35:
            sector_breadth_bonus += 0.3
    sector_concentration_penalty = max(0.0, max_share - (0.35 if top_n == 20 else 0.55)) * 2.0
    return {
        "sector_rotation_score": sector_rotation_score,
        "sector_breadth_bonus": float(sector_breadth_bonus),
        "sector_concentration_penalty": float(sector_concentration_penalty),
    }


def top_choices_for_branch(branch: str) -> list[int]:
    if branch in {
        "strong",
        "liquidity",
        "eventtrend",
        "closepos",
        "defensivequality",
        "diffusion",
        "industrylowcrowd",
        "cleanmomentum",
    }:
        return [5, 7]
    if branch in {"portfolio20", "breadthquality20"}:
        return [20]
    return [5, 7, 10, 20]


def passes_branch_structure(names: set[str], top_n: int, branch: str) -> bool:
    if branch == "portfolio20":
        return top_n == 20 and is_portfolio20_specialized_set(names)
    if branch == "strong":
        return top_n in {5, 7} and not is_portfolio20_specialized_set(names) and len(names & STRENGTH_FACTORS) >= 2
    if branch == "liquidity":
        return top_n in {5, 7} and is_liquidity_quality_low_congestion_set(names)
    if branch == "eventtrend":
        return top_n in {5, 7} and is_event_volume_trend_hold_set(names)
    if branch == "closepos":
        return top_n in {5, 7} and is_long_strength_close_position_set(names)
    if branch == "defensivequality":
        return top_n in {5, 7} and is_defensive_quality_trend_set(names)
    if branch == "diffusion":
        return top_n in {5, 7} and is_relative_strength_diffusion_set(names)
    if branch == "industrylowcrowd":
        return top_n in {5, 7} and is_industry_low_congestion_relative_set(names)
    if branch == "cleanmomentum":
        return top_n in {5, 7} and is_clean_momentum_continuation_set(names)
    if branch == "breadthquality20":
        return top_n == 20 and is_breadth_quality20_set(names)
    return True


def live_strength_metrics(picks: pd.DataFrame, benchmark_ret: float) -> dict[str, float]:
    excess = pd.to_numeric(picks["asset_ret"], errors="coerce").fillna(0.0) - benchmark_ret
    return {
        "live_hit_rate": float((excess > 0).mean()),
        "live_median_excess": float(excess.median()),
        "short_reversal_fail_rate": float((excess < 0).mean()),
    }


def passes_live_strength_screen(picks: pd.DataFrame, benchmark_ret: float, top_n: int) -> bool:
    symbols = set(picks["symbol"].astype(str))
    drag_hits = len(symbols & DRAG_SYMBOLS)
    metrics = live_strength_metrics(picks, benchmark_ret)
    if top_n <= 7 and drag_hits > 0:
        return False
    if top_n == 10 and drag_hits > 1:
        return False
    if top_n == 20 and drag_hits > 2:
        return False
    if metrics["live_hit_rate"] < (0.60 if top_n <= 7 else 0.55):
        return False
    if metrics["live_median_excess"] <= 0:
        return False
    return True


def is_quality_trend_factor_set(names: set[str]) -> bool:
    strength_count = len(names & {"ret_60d", "ret_120d", "mom_252_21", "macd_hist", "px_to_ma20"})
    has_stability = bool(names & {"turnover_stability_20d", "vol_20d", "atr_20d", "parkinson_vol_20d"})
    has_confirmation = bool(names & FLOW_FACTORS)
    old_pullback_core = {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
    return strength_count >= 2 and has_stability and has_confirmation and not old_pullback_core


def is_volume_confirmed_low_vol_extension_set(names: set[str]) -> bool:
    has_extension = bool(names & {"ret_20d", "ret_60d", "ret_120d", "mom_252_21", "px_to_ma20", "macd_hist"})
    has_volume_confirmation = bool(names & {"cmf_10", "cmf_20", "mfi_7", "mfi_14", "obv_change_20"})
    has_low_vol_or_stability = bool(names & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d", "turnover_stability_20d"})
    old_pullback_core = {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
    return has_extension and has_volume_confirmation and has_low_vol_or_stability and not old_pullback_core


def is_micro_reversal_protected_momentum_set(names: set[str]) -> bool:
    has_mid_momentum = len(names & {"ret_20d", "ret_60d", "mom_252_21", "macd_hist"}) >= 2
    has_micro_guard = bool(names & MICRO_PROTECTION_FACTORS)
    has_risk_guard = bool(names & {"vol_20d", "atr_20d", "parkinson_vol_20d", "ret_skew_20d", "kurtosis_20d"})
    old_pullback_core = {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
    return has_mid_momentum and has_micro_guard and has_risk_guard and not old_pullback_core


def is_portfolio20_specialized_set(names: set[str]) -> bool:
    has_medium_strength = bool(names & {"ret_60d", "ret_120d", "mom_252_21", "macd_hist"})
    has_flow_confirmation = bool(names & {"cmf_10", "cmf_20", "mfi_14", "obv_change_20", "volume_ma_ratio_5_20"})
    has_risk_balance = bool(names & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d"})
    has_liquidity_stability = bool(names & {"turnover_stability_20d", "dollar_volume_20d"})
    old_pullback_core = {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
    return has_medium_strength and has_flow_confirmation and has_risk_balance and has_liquidity_stability and not old_pullback_core


def is_liquidity_quality_low_congestion_set(names: set[str]) -> bool:
    has_liquidity_quality = bool(names & {"dollar_volume_20d", "turnover_stability_20d"})
    has_low_vol_balance = bool(names & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d"})
    has_durable_strength = bool(names & {"ret_120d", "mom_252_21", "ma20_above_ma60"})
    avoids_qmv_flow_core = not bool(names & {"mfi_7", "mfi_14", "cmf_10", "cmf_20"})
    old_pullback_core = {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
    return has_liquidity_quality and has_low_vol_balance and has_durable_strength and avoids_qmv_flow_core and not old_pullback_core


def is_event_volume_trend_hold_set(names: set[str]) -> bool:
    has_event_volume = bool(names & {"volume_ma_ratio_5_20", "obv_change_20"})
    has_trend_hold = bool(names & {"ret_20d", "ret_60d", "px_to_ma20", "ma20_above_ma60", "macd_hist"})
    has_failure_guard = bool(
        names & {"range_pct_5d", "close_pos_20d", "vol_20d", "atr_20d", "parkinson_vol_20d", "turnover_stability_20d"}
    )
    avoids_old_qmv_flow = not bool(names & {"mfi_7", "mfi_14", "cmf_10", "cmf_20"})
    old_pullback_core = {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
    return has_event_volume and has_trend_hold and has_failure_guard and avoids_old_qmv_flow and not old_pullback_core


def is_long_strength_close_position_set(names: set[str]) -> bool:
    has_close_position = "close_pos_20d" in names
    has_trend_position = "px_to_ma20" in names
    has_long_strength = bool(names & {"ret_120d", "mom_252_21"})
    has_risk_or_stability = bool(names & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d", "turnover_stability_20d"})
    avoids_flow_qmv = not bool(names & {"mfi_7", "mfi_14", "cmf_10", "cmf_20"})
    return has_close_position and has_trend_position and has_long_strength and has_risk_or_stability and avoids_flow_qmv


def is_defensive_quality_trend_set(names: set[str]) -> bool:
    has_long_strength = bool(names & {"ret_120d", "mom_252_21"})
    has_trend_position = bool(names & {"px_to_ma20", "ma20_above_ma60"})
    has_defensive_risk = bool(names & {"vol_60d", "parkinson_vol_20d", "atr_20d"})
    has_quality_stability = "turnover_stability_20d" in names
    has_tail_guard = bool(names & {"ret_skew_20d", "kurtosis_20d", "close_pos_20d"})
    avoids_flow_qmv = not bool(names & {"mfi_7", "mfi_14", "cmf_10", "cmf_20"})
    return has_long_strength and has_trend_position and has_defensive_risk and has_quality_stability and has_tail_guard and avoids_flow_qmv


def avoids_prior_round287_core(names: set[str]) -> bool:
    return not {"ret_120d", "px_to_ma20", "turnover_stability_20d"}.issubset(names)


def is_relative_strength_diffusion_set(names: set[str]) -> bool:
    has_multi_horizon_strength = len(names & {"ret_20d", "ret_60d", "mom_252_21", "macd_hist"}) >= 2
    has_confirmation = bool(names & {"volume_ma_ratio_5_20", "obv_change_20", "close_pos_20d"})
    has_failure_protection = bool(names & {"range_pct_5d", "vol_20d", "atr_20d", "parkinson_vol_20d"})
    avoids_old_flow_core = not bool(names & {"mfi_7", "mfi_14", "cmf_10", "cmf_20"})
    return has_multi_horizon_strength and has_confirmation and has_failure_protection and avoids_old_flow_core and avoids_prior_round287_core(names)


def is_industry_low_congestion_relative_set(names: set[str]) -> bool:
    has_relative_trend = bool(names & {"ma20_above_ma60", "macd_hist", "ret_60d", "mom_252_21"})
    has_liquidity_or_flow = bool(names & {"dollar_volume_20d", "obv_change_20", "volume_ma_ratio_5_20"})
    has_flow_confirmation = bool(names & {"obv_change_20", "volume_ma_ratio_5_20", "close_pos_20d"})
    has_risk_control = bool(names & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d", "range_pct_5d"})
    has_position_or_stability = bool(names & {"close_pos_20d", "turnover_stability_20d"})
    return (
        has_relative_trend
        and has_liquidity_or_flow
        and has_flow_confirmation
        and has_risk_control
        and has_position_or_stability
        and avoids_prior_round287_core(names)
    )


def is_clean_momentum_continuation_set(names: set[str]) -> bool:
    has_medium_trend = len(names & {"ret_20d", "ret_60d", "mom_252_21", "macd_hist", "ma20_above_ma60"}) >= 2
    has_current_confirmation = bool(names & {"close_pos_20d", "px_to_ma20", "ma20_above_ma60"})
    has_volume_confirmation = bool(names & {"volume_ma_ratio_5_20", "obv_change_20", "cmf_20"})
    has_failure_protection = bool(names & {"range_pct_5d", "vol_20d", "atr_20d", "parkinson_vol_20d"})
    weak_pullback_core = (
        {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
        or {"ret_120d", "ret_5d", "turnover_stability_20d"}.issubset(names)
        or {"ret_120d", "ret_5d", "ret_skew_20d"}.issubset(names)
        or {"ret_120d", "px_to_ma60", "turnover_stability_20d"}.issubset(names)
    )
    return has_medium_trend and has_current_confirmation and has_volume_confirmation and has_failure_protection and not weak_pullback_core


def is_breadth_quality20_set(names: set[str]) -> bool:
    has_medium_strength = bool(names & {"ret_20d", "ret_60d", "mom_252_21", "macd_hist", "ma20_above_ma60"})
    has_liquidity_quality = bool(names & {"dollar_volume_20d", "turnover_stability_20d"})
    has_risk_balance = bool(names & {"vol_20d", "vol_60d", "atr_20d", "parkinson_vol_20d"})
    has_confirmation = bool(names & {"obv_change_20", "volume_ma_ratio_5_20", "cmf_20", "close_pos_20d"})
    weak_pullback_core = (
        {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names)
        or {"ret_120d", "ret_5d", "turnover_stability_20d"}.issubset(names)
        or {"ret_120d", "px_to_ma60", "turnover_stability_20d"}.issubset(names)
    )
    return has_medium_strength and has_liquidity_quality and has_risk_balance and has_confirmation and not weak_pullback_core


def passes_factor_structure_screen(names: set[str], top_n: int) -> bool:
    if top_n == 20 and is_portfolio20_specialized_set(names):
        return True
    if top_n == 20 and is_breadth_quality20_set(names):
        return True
    if top_n in {5, 7} and is_clean_momentum_continuation_set(names):
        return True
    if len(names & STRENGTH_FACTORS) < 2:
        return False
    return (
        is_quality_trend_factor_set(names)
        or is_volume_confirmed_low_vol_extension_set(names)
        or is_micro_reversal_protected_momentum_set(names)
        or is_liquidity_quality_low_congestion_set(names)
        or is_event_volume_trend_hold_set(names)
        or is_long_strength_close_position_set(names)
        or is_defensive_quality_trend_set(names)
        or is_relative_strength_diffusion_set(names)
        or is_industry_low_congestion_relative_set(names)
        or is_clean_momentum_continuation_set(names)
        or (top_n == 20 and is_breadth_quality20_set(names))
        or (top_n == 20 and is_portfolio20_specialized_set(names))
    )


def structural_prior(prefix: str, names: set[str], top_n: int, rebalance_days: int) -> float:
    score = 0.0
    if len(names & STRENGTH_FACTORS) >= 2:
        score += 1.8
    if is_quality_trend_factor_set(names):
        score += 2.4
    if is_volume_confirmed_low_vol_extension_set(names):
        score += 2.0
    if is_micro_reversal_protected_momentum_set(names):
        score += 2.2
    if is_portfolio20_specialized_set(names):
        score += 2.4 if top_n == 20 else 0.4
    if is_liquidity_quality_low_congestion_set(names):
        score += 2.1
    if is_event_volume_trend_hold_set(names):
        score += 2.0
    if is_long_strength_close_position_set(names):
        score += 2.2
    if is_defensive_quality_trend_set(names):
        score += 2.1
    if is_relative_strength_diffusion_set(names):
        score += 2.2
    if is_industry_low_congestion_relative_set(names):
        score += 2.0
    if is_clean_momentum_continuation_set(names):
        score += 2.3
    if is_breadth_quality20_set(names):
        score += 2.5 if top_n == 20 else 0.3
    if names & FLOW_FACTORS:
        score += 0.8
    if names & QUALITY_FACTORS:
        score += 0.8
    if {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(names):
        score -= 1.1
    if prefix in {"balanced", "qmv", "qm", "defensive"}:
        score += 0.8
    if prefix in {"pulltrend", "microtrend"}:
        score -= 0.9
    score += {5: 1.1, 7: 1.2, 10: 0.5, 20: 0.4}.get(top_n, 0.0)
    score += {5: 0.6, 10: 0.5, 20: 0.3}.get(rebalance_days, 0.0)
    return score


def candidate_quality_score(row: dict[str, float | int | str]) -> float:
    top_n_bonus = {5: 0.8, 7: 0.9, 10: 0.3, 20: 0.1}.get(int(row["top_n"]), 0.0)
    branch = str(row.get("branch", "mixed"))
    branch_bonus = 0.0
    if branch == "strong" and int(row["top_n"]) in {5, 7}:
        branch_bonus = 0.6
    elif branch == "portfolio20" and int(row["top_n"]) == 20:
        branch_bonus = 0.8
    elif branch == "breadthquality20" and int(row["top_n"]) == 20:
        branch_bonus = 1.0
    elif branch in {
        "liquidity",
        "eventtrend",
        "closepos",
        "defensivequality",
        "diffusion",
        "industrylowcrowd",
        "cleanmomentum",
    } and int(row["top_n"]) in {5, 7}:
        branch_bonus = 0.9
    return (
        float(row["factory_prior_score"])
        + float(row["factory_ic_score"]) * 100.0
        + float(row["live_excess_return"]) * 220.0
        + float(row["live_median_excess"]) * 120.0
        + float(row["live_hit_rate"]) * 2.2
        + top_n_bonus
        - float(row["max_current_signal_overlap"]) * 2.4
        - float(row["drag_symbol_hits"]) * 1.8
        - float(row["short_reversal_fail_rate"]) * 2.0
        - float(row["max_factor_weight"]) * 0.30
        - float(row.get("holding_congestion_score", 0.0)) * 1.4
        + float(row.get("portfolio_breadth_bonus", 0.0))
        + float(row.get("winner_support_score", 0.0)) * 0.35
        + float(row.get("net_support_score", 0.0)) * 0.65
        - float(row.get("loser_exposure_score", 0.0)) * 0.55
        + float(row.get("sector_rotation_score", 0.0)) * 80.0
        + float(row.get("sector_breadth_bonus", 0.0))
        - float(row.get("sector_concentration_penalty", 0.0)) * 1.2
        + branch_bonus
    )


def generate_live_strength_pool(
    panel: pd.DataFrame,
    limit: int,
    seen: set[tuple[str, int, int]],
    current_baskets: dict[str, set[str]],
    max_signal_overlap: float,
    branch: str = "mixed",
) -> pd.DataFrame:
    live_frame, signal_date, _, _ = us_live_pool.build_live_period(
        panel, signal_date="2026-06-30", valuation_date="2026-07-16"
    )
    benchmark_ret = float(live_frame["asset_ret"].mean())
    rebalance_choices = [5, 10, 20]
    top_choices = top_choices_for_branch(branch)
    ics = factory.precompute_factor_ics(panel, "2023-06-30", "2025-06-29", rebalance_choices)
    rows: list[dict[str, object]] = []
    symbol_counts = current_symbol_counts(current_baskets)
    symbol_exposure = load_current_symbol_exposure()
    sector_map = load_sector_map()
    sector_scores = sector_strength_scores(live_frame, sector_map, benchmark_ret)

    for candidate_id, factors in factory.candidate_hypotheses(limit):
        prefix = candidate_id.split("_", 1)[0]
        names = [factor.name for factor in factors]
        name_set = set(names)
        if not (name_set & QUALITY_FACTORS):
            continue
        if "ret_5d" in name_set and len(name_set & FLOW_FACTORS) == 0:
            continue
        if {"ret_5d", "ret_120d", "px_to_ma60"}.issubset(name_set) and not is_quality_trend_factor_set(name_set):
            continue

        for rebalance_days in rebalance_choices:
            weights = factory.ic_weights_from_values(factors, ics[rebalance_days])
            scores = factory.score_panel(live_frame, weights)
            ic_score = sum(weights.get(name, 0.0) * ics[rebalance_days].get(name, 0.0) for name in names)

            for top_n in top_choices:
                key = (candidate_id[:180], top_n, rebalance_days)
                if key in seen:
                    continue
                if not passes_branch_structure(name_set, top_n, branch):
                    continue
                if not passes_factor_structure_screen(name_set, top_n):
                    continue
                picks = live_frame.loc[scores.nlargest(top_n).index].copy()
                if not passes_live_strength_screen(picks, benchmark_ret, top_n):
                    continue
                symbol_list = picks["symbol"].astype(str).tolist()
                symbols = set(symbol_list)
                overlap, overlap_key = max_current_overlap(symbols, current_baskets)
                if overlap > max_signal_overlap:
                    continue
                strategy_ret = float(picks["asset_ret"].mean())
                live_excess = (1.0 + strategy_ret) / (1.0 + benchmark_ret) - 1.0
                if live_excess <= 0:
                    continue
                metrics = live_strength_metrics(picks, benchmark_ret)
                congestion = holding_congestion_metrics(symbol_list, symbol_counts, top_n)
                diagnostics = diagnostic_support_metrics(symbol_list, symbol_exposure, top_n)
                sectors = sector_rotation_metrics(symbol_list, sector_map, sector_scores, top_n)
                row = {
                    "candidate_id": candidate_id[:180],
                    "factors": ";".join(names),
                    "weights": json.dumps(weights, sort_keys=True),
                    "max_factor_weight": max(weights.values()),
                    "effective_factor_count": 1.0 / sum(value * value for value in weights.values()),
                    "top_n": top_n,
                    "rebalance_days": rebalance_days,
                    "branch": branch,
                    "signal_date": signal_date,
                    "max_current_signal_overlap": overlap,
                    "nearest_current_monitor_key": overlap_key,
                    "drag_symbol_hits": len(symbols & DRAG_SYMBOLS),
                    "live_strategy_return": strategy_ret,
                    "live_benchmark_return": benchmark_ret,
                    "live_excess_return": live_excess,
                    "factory_prior_score": structural_prior(prefix, name_set, top_n, rebalance_days),
                    "factory_ic_score": ic_score,
                    **congestion,
                    **diagnostics,
                    **sectors,
                    **metrics,
                }
                row["final_score"] = candidate_quality_score(row)
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["final_score", "live_excess_return", "live_hit_rate", "max_current_signal_overlap"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def write_round_candidates(pool: pd.DataFrame, start_round: int, rounds_count: int, per_round: int) -> list[tuple[int, Path, str]]:
    out: list[tuple[int, Path, str]] = []
    cursor = 0
    for round_no in range(start_round, start_round + rounds_count):
        chunk = pool.iloc[cursor : cursor + per_round].copy()
        if chunk.empty:
            break
        cursor += per_round
        label = f"round{round_no}-live-strength"
        path = RESEARCH_DIR / f"2026-07-17-{label}-candidates.csv"
        chunk.to_csv(path, index=False)
        out.append((round_no, path, label))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-round", type=int, default=257)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--candidate-limit", type=int, default=50000)
    parser.add_argument("--candidates-per-round", type=int, default=36)
    parser.add_argument("--rolling-top-k", type=int, default=18)
    parser.add_argument("--null-top-k", type=int, default=18)
    parser.add_argument("--null-iter", type=int, default=700)
    parser.add_argument("--max-signal-overlap", type=float, default=0.70)
    parser.add_argument(
        "--branch",
        choices=[
            "mixed",
            "strong",
            "portfolio20",
            "liquidity",
            "eventtrend",
            "closepos",
            "defensivequality",
            "diffusion",
            "industrylowcrowd",
            "cleanmomentum",
            "breadthquality20",
        ],
        default="mixed",
    )
    parser.add_argument("--revisit-historical-candidates", action="store_true")
    parser.add_argument("--seed", type=int, default=20260717)
    args = parser.parse_args()

    panel, _, _, _ = factory.load_panel(RAW_DIR, universe_mode="dynamic_liquidity")
    context = factory.make_eval_context(panel)
    seen = load_pooled_strategy_keys() if args.revisit_historical_candidates else rounds.load_seen_keys()
    pool = generate_live_strength_pool(
        panel,
        args.candidate_limit,
        seen,
        load_current_baskets(),
        args.max_signal_overlap,
        args.branch,
    )
    pool_path = RESEARCH_DIR / f"2026-07-17-live-strength-pool-round{args.start_round}-{args.start_round + args.rounds - 1}.csv"
    pool.to_csv(pool_path, index=False)
    round_files = write_round_candidates(pool, args.start_round, args.rounds, args.candidates_per_round)

    summary_rows = []
    for round_no, candidates_path, label in round_files:
        rolling_dir = RESEARCH_DIR / f"2026-07-17-rolling-{label}"
        null_dir = RESEARCH_DIR / f"2026-07-17-null-{label}"
        rolling_summary = rounds.run_rolling(panel, context, candidates_path, rolling_dir, args.rolling_top_k)
        null_summary = rounds.run_null(
            context, rolling_dir, rolling_summary, null_dir, args.null_top_k, args.null_iter, args.seed + round_no * 100
        )
        promoted = {"round": round_no, "strategies": 0, "holdings": 0}
        if not rolling_summary.empty and not null_summary.empty:
            promoted = rounds.promote_round(
                round_no,
                label,
                candidates_path,
                rolling_dir / "rolling_summary.csv",
                null_dir / "null_overfit_summary.csv",
            )
        row = {
            "round": round_no,
            "candidates_path": str(candidates_path),
            "best_rolling_ir": float(pd.to_numeric(rolling_summary.get("ir"), errors="coerce").max()) if not rolling_summary.empty else 0.0,
            "best_random_pvalue": float(pd.to_numeric(null_summary.get("pvalue_ir"), errors="coerce").min()) if not null_summary.empty else None,
            "promoted_strategies": int(promoted.get("strategies", 0)),
            "promoted_holdings": int(promoted.get("holdings", 0)),
        }
        summary_rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    summary_path = RESEARCH_DIR / f"2026-07-17-live-strength-round{args.start_round}-{args.start_round + args.rounds - 1}-summary.csv"
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(json.dumps({"pool": str(pool_path), "summary": str(summary_path), "rounds": len(summary_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
