from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.hpo import HyperParamSpace, optimize
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis


def _frame(n_dates: int = 16) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class HpoOptimizeTest(unittest.TestCase):
    def test_optimize_returns_config_within_space_and_tracks_trials(self) -> None:
        hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])
        result = optimize(_frame(), hyp, space, n_trials=5, seed=0, n_folds=3, cost_model=CostModel(0.0, 0.0))
        self.assertEqual(result.n_trials, 5)
        self.assertIn(result.best_config.top_n, [1])
        self.assertIn(result.best_config.rebalance_days, [1, 2])
        self.assertIn("momentum_20d", result.best_config.weights)


if __name__ == "__main__":
    unittest.main()
