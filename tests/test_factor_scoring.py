from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.factor_scoring import composite_scores, select_top_n
from quant_agent_team.hypothesis import FactorDef


class FactorScoringTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "stock_code": ["A", "B", "C"],
                "momentum_20d": [0.10, 0.00, -0.10],
                "volatility_20d": [0.30, 0.20, 0.10],
            }
        )

    def test_long_high_factor_ranks_higher_value_first(self) -> None:
        factors = [FactorDef("momentum_20d", "momentum_20d", "long_high")]
        scored = composite_scores(self._frame(), factors, {"momentum_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "A")

    def test_long_low_factor_inverts_ranking(self) -> None:
        factors = [FactorDef("volatility_20d", "volatility_20d", "long_low")]
        scored = composite_scores(self._frame(), factors, {"volatility_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "C")  # lowest volatility wins

    def test_zero_variance_factor_contributes_zero(self) -> None:
        frame = pd.DataFrame({"stock_code": ["A", "B"], "f": [5.0, 5.0]})
        factors = [FactorDef("f", "f", "long_high")]
        scored = composite_scores(frame, factors, {"f": 1.0})
        self.assertEqual(scored["composite_score"].tolist(), [0.0, 0.0])

    def test_weights_combine_multiple_factors(self) -> None:
        frame = pd.DataFrame(
            {
                "stock_code": ["A", "B", "C"],
                "momentum_20d": [0.20, 0.00, -0.05],
                "volatility_20d": [0.10, 0.20, 0.30],
            }
        )
        factors = [
            FactorDef("momentum_20d", "momentum_20d", "long_high"),
            FactorDef("volatility_20d", "volatility_20d", "long_low"),
        ]
        scored = composite_scores(frame, factors, {"momentum_20d": 1.0, "volatility_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "A")  # high momentum and low volatility


if __name__ == "__main__":
    unittest.main()
