from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_model_portfolio import aggregate_model_portfolio, cap_and_redistribute


class UsModelPortfolioTest(unittest.TestCase):
    def test_aggregate_uses_primary_strategies_and_combines_duplicate_symbols(self) -> None:
        strategies = pd.DataFrame(
            [
                {"sid": "S1", "role": "primary", "rolling_ir": 2.0, "status": "paper_live_ready_pending_human_review"},
                {"sid": "S2", "role": "primary", "rolling_ir": 1.5, "status": "paper_live_ready_pending_human_review"},
                {"sid": "S3", "role": "alternate", "rolling_ir": 3.0, "status": "paper_live_ready_pending_human_review"},
            ]
        )
        signals = pd.DataFrame(
            [
                {"sid": "S1", "symbol": "AAA", "weight": 0.5, "signal_date": "2026-07-10", "intended_entry": "next_open"},
                {"sid": "S1", "symbol": "BBB", "weight": 0.5, "signal_date": "2026-07-10", "intended_entry": "next_open"},
                {"sid": "S2", "symbol": "AAA", "weight": 1.0, "signal_date": "2026-07-10", "intended_entry": "next_open"},
                {"sid": "S3", "symbol": "ZZZ", "weight": 1.0, "signal_date": "2026-07-10", "intended_entry": "next_open"},
            ]
        )

        portfolio = aggregate_model_portfolio(strategies, signals, max_symbol_weight=1.0)

        weights = dict(zip(portfolio["symbol"], portfolio["target_weight"]))
        self.assertAlmostEqual(weights["AAA"], 0.75)
        self.assertAlmostEqual(weights["BBB"], 0.25)
        self.assertNotIn("ZZZ", weights)
        self.assertEqual(portfolio.loc[portfolio["symbol"].eq("AAA"), "contributing_sids"].iloc[0], "S1;S2")

    def test_cap_and_redistribute_limits_concentration_and_preserves_total_weight(self) -> None:
        weights = pd.Series({"AAA": 0.7, "BBB": 0.2, "CCC": 0.1}, dtype=float)

        capped = cap_and_redistribute(weights, cap=0.5)

        self.assertLessEqual(float(capped.max()), 0.5)
        self.assertAlmostEqual(float(capped.sum()), 1.0)
        self.assertGreater(float(capped["BBB"]), 0.2)
        self.assertGreater(float(capped["CCC"]), 0.1)


if __name__ == "__main__":
    unittest.main()
