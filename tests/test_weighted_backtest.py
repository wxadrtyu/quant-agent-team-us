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
from quant_agent_team.weighted_backtest import run_weighted_backtest


def _hypothesis() -> FactorHypothesis:
    return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


def _next_open_frame() -> pd.DataFrame:
    rows = []
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    for d, open_price in zip(dates, [100.0, 50.0, 55.0]):
        rows.append(
            {
                "stock_code": "UP",
                "trade_date": d,
                "open_price": open_price,
                "close_price_adj": 100.0,
                "momentum_20d": 0.10,
            }
        )
        rows.append(
            {
                "stock_code": "DN",
                "trade_date": d,
                "open_price": 100.0,
                "close_price_adj": 100.0,
                "momentum_20d": -0.10,
            }
        )
    return pd.DataFrame(rows)


class WeightedBacktestExecutionTimingTest(unittest.TestCase):
    def test_executes_signal_on_next_session_open_not_same_day_close(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_weighted_backtest(
            _next_open_frame(),
            _hypothesis(),
            config,
            cost_model=CostModel(0.0, 0.0),
        )
        self.assertAlmostEqual(result.total_return, 0.10, places=6)
        self.assertEqual(result.trade_count, 1)


if __name__ == "__main__":
    unittest.main()
