from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.factor_backtest import run_factor_backtest
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


def _trending_frame() -> pd.DataFrame:
    rows = []
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
    up_prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    dn_prices = [10.0, 9.0, 8.0, 7.0, 6.0]
    for d, pu, pd_ in zip(dates, up_prices, dn_prices):
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": pu, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": pd_, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


def _hypothesis() -> FactorHypothesis:
    return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


class FactorBacktestTest(unittest.TestCase):
    def test_picks_uptrending_stock_and_makes_money_frictionless(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_factor_backtest(_trending_frame(), _hypothesis(), config, cost_model=CostModel(0.0, 0.0))
        self.assertGreater(result.total_return, 0.0)
        self.assertGreater(result.trade_count, 0)

    def test_costs_reduce_return(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        frictionless = run_factor_backtest(_trending_frame(), _hypothesis(), config, cost_model=CostModel(0.0, 0.0))
        with_costs = run_factor_backtest(_trending_frame(), _hypothesis(), config)
        self.assertLess(with_costs.total_return, frictionless.total_return)

    def test_drawdown_is_non_negative_fraction(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_factor_backtest(_trending_frame(), _hypothesis(), config, cost_model=CostModel(0.0, 0.0))
        self.assertGreaterEqual(result.max_drawdown, 0.0)


if __name__ == "__main__":
    unittest.main()
