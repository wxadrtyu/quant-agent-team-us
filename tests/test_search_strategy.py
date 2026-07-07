from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.evaluation import AcceptanceCriteria
from quant_agent_team.hpo import HyperParamSpace, search_strategy
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


class SearchStrategyTest(unittest.TestCase):
    def test_search_returns_hpo_result_and_evaluation(self) -> None:
        hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1)
        result = search_strategy(_frame(), hyp, space, criteria, n_trials=5, seed=0, cost_model=CostModel(0.0, 0.0))
        self.assertEqual(result.hpo.n_trials, 5)
        self.assertTrue(result.evaluation.passed)
        self.assertGreater(result.development_result.trade_count, 0)


if __name__ == "__main__":
    unittest.main()
