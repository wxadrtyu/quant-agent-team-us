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
from quant_agent_team.refinement import (
    InvalidHypothesisError,
    ProposalContext,
    run_refinement,
)


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


class _FixedProposer:
    def __init__(self) -> None:
        self.calls = 0

    def propose(self, context: ProposalContext) -> FactorHypothesis:
        self.calls += 1
        return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


class _RaisingProposer:
    def propose(self, context: ProposalContext) -> FactorHypothesis:
        raise InvalidHypothesisError("bad output")


class RefinementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])

    def test_stops_on_acceptance(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1)
        proposer = _FixedProposer()
        result = run_refinement(
            _frame(), proposer, self.space, criteria, market="cn", return_target=0.0,
            available_factors=["momentum_20d"], max_iterations=10, n_trials=5, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(result.stopped_reason, "accepted")
        self.assertEqual(proposer.calls, 1)
        self.assertIsNotNone(result.accepted)

    def test_budget_exhausted_when_never_passing(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=10_000)
        result = run_refinement(
            _frame(), _FixedProposer(), self.space, criteria, market="cn", return_target=10.0,
            available_factors=["momentum_20d"], max_iterations=3, n_trials=3, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(result.stopped_reason, "budget_exhausted")
        self.assertEqual(len(result.iterations), 3)
        self.assertIsNone(result.accepted)

    def test_invalid_hypothesis_consumes_iteration(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1)
        result = run_refinement(
            _frame(), _RaisingProposer(), self.space, criteria, market="cn", return_target=0.0,
            available_factors=["momentum_20d"], max_iterations=2, n_trials=3, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(result.stopped_reason, "budget_exhausted")
        self.assertEqual(len(result.iterations), 2)
        self.assertFalse(result.iterations[0].passed)


if __name__ == "__main__":
    unittest.main()
