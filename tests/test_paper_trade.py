from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis
from quant_agent_team.paper_trade import run_paper_trade


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=10)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class PaperTradeTest(unittest.TestCase):
    def test_latest_signal_picks_top_factor_and_runs_backtest(self) -> None:
        hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_paper_trade(_frame(), hyp, config, cost_model=CostModel(0.0, 0.0))
        self.assertEqual(result.latest_signal, ["UP"])
        self.assertGreater(result.backtest.trade_count, 0)


if __name__ == "__main__":
    unittest.main()
