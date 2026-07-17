from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_live_strength_strategy_exploration import (
    DRAG_SYMBOLS,
    candidate_quality_score,
    current_symbol_counts,
    diagnostic_support_metrics,
    holding_congestion_metrics,
    is_breadth_quality20_set,
    is_clean_momentum_continuation_set,
    is_defensive_quality_trend_set,
    is_event_volume_trend_hold_set,
    is_industry_low_congestion_relative_set,
    is_liquidity_quality_low_congestion_set,
    is_long_strength_close_position_set,
    is_micro_reversal_protected_momentum_set,
    is_portfolio20_specialized_set,
    is_relative_strength_diffusion_set,
    is_quality_trend_factor_set,
    is_volume_confirmed_low_vol_extension_set,
    passes_branch_structure,
    passes_factor_structure_screen,
    passes_live_strength_screen,
    sector_rotation_metrics,
    structural_prior,
    top_choices_for_branch,
)


class UsLiveStrengthStrategyExplorationTest(unittest.TestCase):
    def test_candidate_quality_prefers_clean_live_strength_over_drag_exposure(self) -> None:
        clean = {
            "live_excess_return": 0.04,
            "live_hit_rate": 0.80,
            "live_median_excess": 0.025,
            "max_current_signal_overlap": 0.10,
            "drag_symbol_hits": 0,
            "short_reversal_fail_rate": 0.10,
            "factory_prior_score": 2.0,
            "factory_ic_score": 0.01,
            "max_factor_weight": 0.40,
            "top_n": 7,
        }
        crowded = {
            "live_excess_return": 0.05,
            "live_hit_rate": 0.45,
            "live_median_excess": -0.005,
            "max_current_signal_overlap": 0.45,
            "drag_symbol_hits": 2,
            "short_reversal_fail_rate": 0.50,
            "factory_prior_score": 2.0,
            "factory_ic_score": 0.01,
            "max_factor_weight": 0.40,
            "top_n": 7,
        }

        self.assertGreater(candidate_quality_score(clean), candidate_quality_score(crowded))

    def test_screen_blocks_small_baskets_with_drag_or_weak_hit_rate(self) -> None:
        weak = pd.DataFrame(
            [
                {"symbol": next(iter(DRAG_SYMBOLS)), "asset_ret": 0.03},
                {"symbol": "MSFT", "asset_ret": -0.01},
                {"symbol": "AAPL", "asset_ret": -0.02},
                {"symbol": "JNJ", "asset_ret": 0.00},
                {"symbol": "PG", "asset_ret": 0.01},
            ]
        )
        strong = pd.DataFrame(
            [
                {"symbol": "MSFT", "asset_ret": 0.05},
                {"symbol": "AAPL", "asset_ret": 0.04},
                {"symbol": "JNJ", "asset_ret": 0.03},
                {"symbol": "PG", "asset_ret": 0.02},
                {"symbol": "COST", "asset_ret": 0.02},
            ]
        )

        self.assertFalse(passes_live_strength_screen(weak, benchmark_ret=0.01, top_n=5))
        self.assertTrue(passes_live_strength_screen(strong, benchmark_ret=0.01, top_n=5))

    def test_structural_prior_rewards_quality_trend_confirmation(self) -> None:
        quality_trend = {"ret_60d", "mom_252_21", "px_to_ma20", "turnover_stability_20d", "cmf_20"}
        old_pullback = {"ret_5d", "ret_120d", "px_to_ma60", "turnover_stability_20d", "vol_20d"}

        self.assertTrue(is_quality_trend_factor_set(quality_trend))
        self.assertFalse(is_quality_trend_factor_set(old_pullback))
        self.assertGreater(
            structural_prior("qmv", quality_trend, top_n=7, rebalance_days=10),
            structural_prior("balanced", old_pullback, top_n=7, rebalance_days=10),
        )

    def test_new_alpha_sets_identify_volume_confirmed_and_micro_protected_structures(self) -> None:
        volume_confirmed = {"ret_60d", "px_to_ma20", "cmf_20", "vol_20d", "turnover_stability_20d"}
        micro_protected = {"mom_252_21", "ret_20d", "overnight_gap_1d", "close_pos_20d", "atr_20d"}
        old_core = {"ret_5d", "ret_120d", "px_to_ma60", "turnover_stability_20d", "vol_20d"}

        self.assertTrue(is_volume_confirmed_low_vol_extension_set(volume_confirmed))
        self.assertTrue(is_micro_reversal_protected_momentum_set(micro_protected))
        self.assertFalse(is_volume_confirmed_low_vol_extension_set(old_core))
        self.assertFalse(is_micro_reversal_protected_momentum_set(old_core))
        self.assertGreater(
            structural_prior("qmv", volume_confirmed, top_n=7, rebalance_days=10),
            structural_prior("balanced", old_core, top_n=7, rebalance_days=10),
        )
        self.assertGreater(
            structural_prior("microtrend", micro_protected, top_n=5, rebalance_days=5),
            structural_prior("balanced", old_core, top_n=5, rebalance_days=5),
        )

    def test_candidate_quality_penalizes_crowded_current_holdings_and_rewards_clean_20(self) -> None:
        current = {
            "S1": {"AAA", "BBB", "CCC"},
            "S2": {"AAA", "DDD", "EEE"},
            "S3": {"AAA", "BBB", "FFF"},
        }
        counts = current_symbol_counts(current)
        crowded = holding_congestion_metrics(["AAA", "BBB", "CCC", "GGG", "HHH"], counts, top_n=5)
        clean = holding_congestion_metrics([f"S{i:02d}" for i in range(20)], counts, top_n=20)

        self.assertGreater(crowded["holding_congestion_score"], clean["holding_congestion_score"])
        self.assertGreater(clean["portfolio_breadth_bonus"], crowded["portfolio_breadth_bonus"])

        base = {
            "live_excess_return": 0.04,
            "live_hit_rate": 0.75,
            "live_median_excess": 0.02,
            "max_current_signal_overlap": 0.10,
            "drag_symbol_hits": 0,
            "short_reversal_fail_rate": 0.20,
            "factory_prior_score": 3.0,
            "factory_ic_score": 0.01,
            "max_factor_weight": 0.35,
        }
        crowded_row = {**base, **crowded, "top_n": 5}
        clean_row = {**base, **clean, "top_n": 20}

        self.assertGreater(candidate_quality_score(clean_row), candidate_quality_score(crowded_row))

    def test_candidate_quality_rewards_winner_support_and_penalizes_loser_exposure(self) -> None:
        exposure = {
            "AAA": {"winner_weight": 4.0, "loser_weight": 1.0},
            "BBB": {"winner_weight": 3.0, "loser_weight": 0.5},
            "CCC": {"winner_weight": 0.5, "loser_weight": 4.0},
            "DDD": {"winner_weight": 0.2, "loser_weight": 3.0},
        }
        supported = diagnostic_support_metrics(["AAA", "BBB"], exposure, top_n=20)
        dragged = diagnostic_support_metrics(["CCC", "DDD"], exposure, top_n=20)

        self.assertGreater(supported["winner_support_score"], dragged["winner_support_score"])
        self.assertLess(supported["loser_exposure_score"], dragged["loser_exposure_score"])

        base = {
            "live_excess_return": 0.025,
            "live_hit_rate": 0.70,
            "live_median_excess": 0.01,
            "max_current_signal_overlap": 0.10,
            "drag_symbol_hits": 0,
            "short_reversal_fail_rate": 0.20,
            "factory_prior_score": 3.0,
            "factory_ic_score": 0.01,
            "max_factor_weight": 0.35,
            "top_n": 20,
            "branch": "breadthquality20",
        }

        self.assertGreater(
            candidate_quality_score({**base, **supported}),
            candidate_quality_score({**base, **dragged}),
        )

    def test_portfolio20_specialized_set_requires_breadth_and_risk_balance(self) -> None:
        portfolio20 = {"ret_60d", "mom_252_21", "cmf_20", "vol_20d", "turnover_stability_20d"}
        narrow = {"ret_60d", "mom_252_21", "px_to_ma20", "macd_hist", "ret_20d"}

        self.assertTrue(is_portfolio20_specialized_set(portfolio20))
        self.assertFalse(is_portfolio20_specialized_set(narrow))
        self.assertGreater(
            structural_prior("qmv", portfolio20, top_n=20, rebalance_days=20),
            structural_prior("qmv", portfolio20, top_n=7, rebalance_days=20),
        )

    def test_portfolio20_structure_can_pass_without_two_strength_factors(self) -> None:
        portfolio20 = {"ret_60d", "cmf_20", "vol_20d", "turnover_stability_20d", "dollar_volume_20d"}
        weak_single_stock = {"ret_60d", "px_to_ma20", "vol_20d", "turnover_stability_20d", "dollar_volume_20d"}

        self.assertTrue(is_portfolio20_specialized_set(portfolio20))
        self.assertTrue(passes_factor_structure_screen(portfolio20, top_n=20))
        self.assertFalse(passes_factor_structure_screen(weak_single_stock, top_n=7))

    def test_sector_rotation_metrics_reward_strong_broad_sector_exposure(self) -> None:
        sector_map = {
            "AAA": "Technology",
            "BBB": "Industrials",
            "CCC": "Health Care",
            "DDD": "Technology",
            "EEE": "Technology",
        }
        sector_scores = {"Technology": 0.03, "Industrials": 0.02, "Health Care": 0.01}

        broad = sector_rotation_metrics(["AAA", "BBB", "CCC"], sector_map, sector_scores, top_n=20)
        concentrated = sector_rotation_metrics(["AAA", "DDD", "EEE"], sector_map, sector_scores, top_n=20)

        self.assertGreater(broad["sector_breadth_bonus"], concentrated["sector_breadth_bonus"])
        self.assertLess(broad["sector_concentration_penalty"], concentrated["sector_concentration_penalty"])
        self.assertGreater(
            candidate_quality_score({
                "live_excess_return": 0.03,
                "live_hit_rate": 0.70,
                "live_median_excess": 0.015,
                "max_current_signal_overlap": 0.10,
                "drag_symbol_hits": 0,
                "short_reversal_fail_rate": 0.20,
                "factory_prior_score": 3.0,
                "factory_ic_score": 0.01,
                "max_factor_weight": 0.35,
                "top_n": 20,
                **broad,
            }),
            candidate_quality_score({
                "live_excess_return": 0.03,
                "live_hit_rate": 0.70,
                "live_median_excess": 0.015,
                "max_current_signal_overlap": 0.10,
                "drag_symbol_hits": 0,
                "short_reversal_fail_rate": 0.20,
                "factory_prior_score": 3.0,
                "factory_ic_score": 0.01,
                "max_factor_weight": 0.35,
                "top_n": 20,
                **concentrated,
            }),
        )

    def test_branch_controls_keep_strong_and_portfolio20_candidate_spaces_separate(self) -> None:
        portfolio20 = {"ret_60d", "cmf_20", "vol_20d", "turnover_stability_20d", "dollar_volume_20d"}
        strong = {"ret_60d", "mom_252_21", "cmf_20", "vol_20d", "px_to_ma20"}

        self.assertEqual(top_choices_for_branch("strong"), [5, 7])
        self.assertEqual(top_choices_for_branch("portfolio20"), [20])
        self.assertEqual(top_choices_for_branch("mixed"), [5, 7, 10, 20])
        self.assertFalse(passes_branch_structure(portfolio20, top_n=7, branch="strong"))
        self.assertTrue(passes_branch_structure(strong, top_n=7, branch="strong"))
        self.assertFalse(passes_branch_structure(strong, top_n=20, branch="portfolio20"))
        self.assertTrue(passes_branch_structure(portfolio20, top_n=20, branch="portfolio20"))

    def test_new_liquidity_and_event_branches_are_separate_from_qmv_pullback_space(self) -> None:
        liquidity_quality = {"dollar_volume_20d", "turnover_stability_20d", "vol_20d", "ret_60d", "ma20_above_ma60"}
        event_volume = {"volume_ma_ratio_5_20", "obv_change_20", "ret_20d", "px_to_ma20", "range_pct_5d"}
        old_qmv = {"ret_60d", "px_to_ma20", "mfi_14", "ret_skew_20d", "turnover_stability_20d"}

        self.assertTrue(is_liquidity_quality_low_congestion_set(liquidity_quality))
        self.assertTrue(is_event_volume_trend_hold_set(event_volume))
        self.assertFalse(is_liquidity_quality_low_congestion_set(old_qmv))
        self.assertFalse(is_event_volume_trend_hold_set(old_qmv))
        self.assertTrue(passes_branch_structure(liquidity_quality, top_n=7, branch="liquidity"))
        self.assertTrue(passes_branch_structure(event_volume, top_n=5, branch="eventtrend"))
        self.assertFalse(passes_branch_structure(old_qmv, top_n=7, branch="liquidity"))
        self.assertFalse(passes_branch_structure(old_qmv, top_n=5, branch="eventtrend"))

    def test_liquidity_followup_subbranches_split_close_position_from_defensive_quality(self) -> None:
        close_position = {"close_pos_20d", "px_to_ma20", "ret_120d", "parkinson_vol_20d", "turnover_stability_20d"}
        defensive_quality = {"ret_120d", "vol_60d", "ret_skew_20d", "turnover_stability_20d", "px_to_ma20"}
        repeated_flow_qmv = {"ret_120d", "px_to_ma20", "mfi_14", "vol_60d", "turnover_stability_20d"}

        self.assertTrue(is_long_strength_close_position_set(close_position))
        self.assertTrue(is_defensive_quality_trend_set(defensive_quality))
        self.assertFalse(is_long_strength_close_position_set(repeated_flow_qmv))
        self.assertFalse(is_defensive_quality_trend_set(repeated_flow_qmv))
        self.assertTrue(passes_branch_structure(close_position, top_n=5, branch="closepos"))
        self.assertTrue(passes_branch_structure(defensive_quality, top_n=7, branch="defensivequality"))
        self.assertFalse(passes_branch_structure(repeated_flow_qmv, top_n=5, branch="closepos"))
        self.assertFalse(passes_branch_structure(repeated_flow_qmv, top_n=7, branch="defensivequality"))

    def test_low_correlation_branches_avoid_prior_ret120_px20_turnover_core(self) -> None:
        diffusion = {"ret_20d", "ret_60d", "mom_252_21", "volume_ma_ratio_5_20", "range_pct_5d"}
        industry_low_crowd = {"ma20_above_ma60", "vol_20d", "dollar_volume_20d", "close_pos_20d", "obv_change_20"}
        repeated_core = {"ret_120d", "px_to_ma20", "turnover_stability_20d", "parkinson_vol_20d", "close_pos_20d"}

        self.assertTrue(is_relative_strength_diffusion_set(diffusion))
        self.assertTrue(is_industry_low_congestion_relative_set(industry_low_crowd))
        self.assertFalse(is_relative_strength_diffusion_set(repeated_core))
        self.assertFalse(is_industry_low_congestion_relative_set(repeated_core))
        self.assertTrue(passes_branch_structure(diffusion, top_n=5, branch="diffusion"))
        self.assertTrue(passes_branch_structure(industry_low_crowd, top_n=7, branch="industrylowcrowd"))
        self.assertFalse(passes_branch_structure(repeated_core, top_n=5, branch="diffusion"))
        self.assertFalse(passes_branch_structure(repeated_core, top_n=7, branch="industrylowcrowd"))

    def test_clean_momentum_branch_requires_confirmation_and_rejects_weak_pullback_clusters(self) -> None:
        clean_momentum = {"ret_60d", "mom_252_21", "close_pos_20d", "volume_ma_ratio_5_20", "range_pct_5d"}
        factory_clean_momentum = {"ret_20d", "ma20_above_ma60", "cmf_20", "vol_20d", "dollar_volume_20d"}
        weak_pullback = {"ret_5d", "ret_120d", "px_to_ma60", "turnover_stability_20d", "ret_skew_20d"}
        no_failure_guard = {"ret_60d", "mom_252_21", "close_pos_20d", "volume_ma_ratio_5_20"}

        self.assertEqual(top_choices_for_branch("cleanmomentum"), [5, 7])
        self.assertTrue(is_clean_momentum_continuation_set(clean_momentum))
        self.assertTrue(is_clean_momentum_continuation_set(factory_clean_momentum))
        self.assertFalse(is_clean_momentum_continuation_set(weak_pullback))
        self.assertFalse(is_clean_momentum_continuation_set(no_failure_guard))
        self.assertTrue(passes_branch_structure(clean_momentum, top_n=7, branch="cleanmomentum"))
        self.assertFalse(passes_branch_structure(clean_momentum, top_n=20, branch="cleanmomentum"))
        self.assertFalse(passes_branch_structure(weak_pullback, top_n=5, branch="cleanmomentum"))
        self.assertTrue(passes_factor_structure_screen(clean_momentum, top_n=5))
        self.assertTrue(passes_factor_structure_screen(factory_clean_momentum, top_n=5))

    def test_breadth_quality20_branch_is_true_twenty_stock_stabilizer(self) -> None:
        breadth_quality = {
            "ret_60d",
            "ma20_above_ma60",
            "dollar_volume_20d",
            "turnover_stability_20d",
            "vol_20d",
            "obv_change_20",
        }
        weak_pullback = {"ret_5d", "ret_120d", "px_to_ma60", "turnover_stability_20d", "vol_20d"}
        narrow_strength = {"ret_60d", "ma20_above_ma60", "obv_change_20", "vol_20d"}

        self.assertEqual(top_choices_for_branch("breadthquality20"), [20])
        self.assertTrue(is_breadth_quality20_set(breadth_quality))
        self.assertFalse(is_breadth_quality20_set(weak_pullback))
        self.assertFalse(is_breadth_quality20_set(narrow_strength))
        self.assertTrue(passes_branch_structure(breadth_quality, top_n=20, branch="breadthquality20"))
        self.assertFalse(passes_branch_structure(breadth_quality, top_n=7, branch="breadthquality20"))
        self.assertTrue(passes_factor_structure_screen(breadth_quality, top_n=20))


if __name__ == "__main__":
    unittest.main()
