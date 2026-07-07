from datetime import date
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
from quant_agent_team.orchestrator import run_pipeline
from quant_agent_team.refinement import ProposalContext


class _FixedProposer:
    def propose(self, context: ProposalContext) -> FactorHypothesis:
        return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


def _three_year_frame(end: date) -> pd.DataFrame:
    start = date(end.year - 3, end.month, 1)
    dates = pd.bdate_range(start, end)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.01
        dn *= 0.99
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class OrchestratorTest(unittest.TestCase):
    def test_full_pipeline_accepts_and_scores(self) -> None:
        end = date(2026, 6, 27)
        report = run_pipeline(
            _three_year_frame(end), _FixedProposer(),
            HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[5]),
            AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1),
            market="cn", return_target=0.0, available_factors=["momentum_20d"],
            end_date=end, max_iterations=2, n_trials=3, null_runs=2, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(report.refinement.stopped_reason, "accepted")
        self.assertIsNotNone(report.holdout)
        self.assertGreaterEqual(report.overfitting, 0.0)
        self.assertLessEqual(report.overfitting, 1.0)
        self.assertIsNotNone(report.deflated_holdout_return)
        self.assertGreaterEqual(report.null_pass_rate, 0.0)
        self.assertLessEqual(report.null_pass_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
