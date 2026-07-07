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
from quant_agent_team.hpo import HyperParamSpace
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis
from quant_agent_team.null_test import run_null_test


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


class NullTestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        self.space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])

    def test_impossible_bar_never_passes_on_noise(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=10.0, max_drawdown_limit=1.0, min_trade_count=1)
        result = run_null_test(
            _frame(), self.hyp, self.space, criteria, n_runs=3, base_seed=0, n_trials=3, cost_model=CostModel(0.0, 0.0)
        )
        self.assertEqual(result.n_runs, 3)
        self.assertEqual(result.passes, 0)
        self.assertEqual(result.pass_rate, 0.0)

    def test_pass_rate_is_consistent_with_counts(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.30, max_drawdown_limit=1.0, min_trade_count=1)
        result = run_null_test(
            _frame(), self.hyp, self.space, criteria, n_runs=4, base_seed=1, n_trials=3, cost_model=CostModel(0.0, 0.0)
        )
        self.assertGreaterEqual(result.pass_rate, 0.0)
        self.assertLessEqual(result.pass_rate, 1.0)
        self.assertAlmostEqual(result.pass_rate, result.passes / result.n_runs)


if __name__ == "__main__":
    unittest.main()
