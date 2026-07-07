from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.backtest_runner import _simulate_strategy
from quant_agent_team.cost_model import CostModel


def _two_day_entry_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_code": "000001", "trade_date": pd.Timestamp("2025-01-02"),
                "open_price": 10.0, "high_price": 10.1, "low_price": 9.9,
                "close_price": 10.0, "close_price_adj": 10.0, "volume": 1000.0,
                "turnover": 10000.0, "adj_factor": 1.0, "is_suspended": False,
                "is_st": False, "limit_up_price": None, "limit_down_price": None,
                "ret_1d": 0.0, "ranking_score": 1.0, "day_seq": 0,
                "next_trade_date": pd.Timestamp("2025-01-03"), "next_open_price": 10.0,
                "next_open_gap_pct": 0.0,
            },
            {
                "stock_code": "000001", "trade_date": pd.Timestamp("2025-01-03"),
                "open_price": 10.0, "high_price": 10.2, "low_price": 9.8,
                "close_price": 10.5, "close_price_adj": 10.5, "volume": 1000.0,
                "turnover": 10500.0, "adj_factor": 1.0, "is_suspended": False,
                "is_st": False, "limit_up_price": None, "limit_down_price": None,
                "ret_1d": 0.05, "ranking_score": 1.0, "day_seq": 1,
                "next_trade_date": pd.NaT, "next_open_price": float("nan"),
                "next_open_gap_pct": float("nan"),
            },
        ]
    )


def _spec() -> SimpleNamespace:
    return SimpleNamespace(
        spec_id="spec-test", strategy_id="demo",
        ranking_formula=SimpleNamespace(formula="1", sort_direction="desc"),
        position_rules=SimpleNamespace(max_positions=1, min_holding_days_before_exit=0, rebalance_frequency="daily"),
        filters=[],
        entry_rules=[SimpleNamespace(rule_id="buy", logic="AND", conditions=[{"field": "ret_1d", "operator": "between", "value": [-0.01, 0.01]}])],
        exit_rules=[],
    )


class BacktestCostTest(unittest.TestCase):
    def test_costs_reduce_return_without_changing_trade_structure(self) -> None:
        zero = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0, cost_model=CostModel(0.0, 0.0))
        default = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0)
        self.assertEqual(default.trade_count, zero.trade_count)
        self.assertEqual(default.trade_count, 1)
        self.assertLess(default.total_return, zero.total_return)

    def test_default_cost_model_is_non_zero(self) -> None:
        default = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0)
        frictionless = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0, cost_model=CostModel(0.0, 0.0))
        self.assertNotAlmostEqual(default.total_return, frictionless.total_return)


if __name__ == "__main__":
    unittest.main()
