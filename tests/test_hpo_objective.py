from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.hpo import PENALTY, walk_forward_objective
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


def _frame(n_dates: int = 12) -> pd.DataFrame:
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


class HpoObjectiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        self.config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)

    def test_positive_score_for_profitable_oos(self) -> None:
        score = walk_forward_objective(_frame(), self.hyp, self.config, n_folds=3, cost_model=CostModel(0.0, 0.0))
        self.assertGreater(score, 0.0)

    def test_penalty_when_min_trade_count_not_met(self) -> None:
        score = walk_forward_objective(
            _frame(), self.hyp, self.config, n_folds=3, min_trade_count=10_000, cost_model=CostModel(0.0, 0.0)
        )
        self.assertEqual(score, PENALTY)


if __name__ == "__main__":
    unittest.main()
