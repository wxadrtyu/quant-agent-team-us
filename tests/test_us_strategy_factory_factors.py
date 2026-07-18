from pathlib import Path
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pandas as pd

from us_strategy_factory_loop import FACTOR_LIBRARY, candidate_hypotheses, load_panel


class UsStrategyFactoryFactorsTest(unittest.TestCase):
    def test_microstructure_factor_specs_are_registered(self) -> None:
        names = {factor.name for factor in FACTOR_LIBRARY}

        self.assertIn("overnight_gap_1d", names)
        self.assertIn("intraday_ret_1d", names)
        self.assertIn("close_pos_20d", names)

    def test_candidate_generation_round_robins_templates(self) -> None:
        prefixes = [candidate_id.split("_", 1)[0] for candidate_id, _ in candidate_hypotheses(6)]

        self.assertGreaterEqual(len(set(prefixes)), 4)

    def test_load_panel_adds_sector_relative_strength_scores(self) -> None:
        with self.subTest("sector relative factors are registered"):
            names = {factor.name for factor in FACTOR_LIBRARY}
            self.assertIn("sector_rel_ret_20d", names)
            self.assertIn("sector_rel_ret_60d", names)
            self.assertIn("sector_rel_drawdown_20d", names)

    def test_candidate_generation_includes_relative_leader_template(self) -> None:
        candidates = candidate_hypotheses(200)
        relative_candidates = [
            (candidate_id, factors)
            for candidate_id, factors in candidates
            if candidate_id.startswith("relativeleader_")
        ]

        self.assertTrue(relative_candidates)
        self.assertTrue(any(any(factor.category == "relative_strength" for factor in factors) for _, factors in relative_candidates))

    def test_candidate_generation_includes_relative_repair_template(self) -> None:
        candidates = candidate_hypotheses(250)
        repair_candidates = [
            (candidate_id, factors)
            for candidate_id, factors in candidates
            if candidate_id.startswith("relativerepair_")
        ]

        self.assertTrue(repair_candidates)
        self.assertTrue(any(any(factor.category == "relative_reversal" for factor in factors) for _, factors in repair_candidates))

    def test_sector_relative_strength_is_stock_return_minus_sector_average(self) -> None:
        with self.subTest("relative strength uses same-day sector peer average"):
            raw_dir = self._write_minimal_raw_dir()
            panel, *_ = load_panel(raw_dir, universe_mode="current_snapshot")
            latest = panel[panel["trade_date"] == panel["trade_date"].max()].set_index("symbol")

            self.assertGreater(float(latest.loc["AAA", "score_sector_rel_ret_20d"]), 0.0)
            self.assertLess(float(latest.loc["BBB", "score_sector_rel_ret_20d"]), 0.0)

    def _write_minimal_raw_dir(self) -> Path:
        import tempfile

        raw_dir = Path(tempfile.mkdtemp())
        rows = []
        dates = pd.bdate_range("2022-01-03", periods=330)
        configs = {
            "AAA": ("Technology", 100.0, 0.004),
            "BBB": ("Technology", 100.0, 0.000),
            "CCC": ("Health Care", 100.0, 0.002),
            "DDD": ("Health Care", 100.0, 0.001),
        }
        for symbol_index, (symbol, (_, start_price, daily_drift)) in enumerate(configs.items()):
            price = start_price
            for i, date in enumerate(dates):
                daily_ret = daily_drift + 0.012 * math.sin(i * 0.47 + symbol_index)
                price *= 1.0 + daily_ret
                volume = 1_000_000 + 50_000 * ((i + symbol_index) % 7)
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": date.date().isoformat(),
                        "open": price * (1.0 - 0.002 * math.cos(i)),
                        "high": price * 1.01,
                        "low": price * 0.99,
                        "close": price,
                        "adj_close": price,
                        "volume": volume,
                        "dividend": 0.0,
                        "split_factor": 0.0,
                        "source": "test",
                    }
                )
        pd.DataFrame(rows).to_parquet(raw_dir / "us_market_daily.parquet", index=False)
        pd.DataFrame(
            [
                {"symbol": "AAA", "sector": "Technology", "industry": "Software", "name": "AAA"},
                {"symbol": "BBB", "sector": "Technology", "industry": "Hardware", "name": "BBB"},
                {"symbol": "CCC", "sector": "Health Care", "industry": "Tools", "name": "CCC"},
                {"symbol": "DDD", "sector": "Health Care", "industry": "Equipment", "name": "DDD"},
            ]
        ).to_parquet(raw_dir / "us_stock_meta.parquet", index=False)
        return raw_dir


if __name__ == "__main__":
    unittest.main()
