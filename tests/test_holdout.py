from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.holdout import HoldoutAlreadyUsedError, HoldoutVault
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range("2025-06-28", periods=20)  # all inside the holdout window below
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


def _hyp() -> FactorHypothesis:
    return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


def _config() -> FactorConfig:
    return FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)


class HoldoutVaultTest(unittest.TestCase):
    def test_evaluate_returns_result_and_increments_touches(self) -> None:
        vault = HoldoutVault("2025-06-28", "2026-06-27", cost_model=CostModel(0.0, 0.0))
        result = vault.evaluate("s1", _frame(), _hyp(), _config())
        self.assertEqual(result.strategy_id, "s1")
        self.assertEqual(result.touches, 1)
        self.assertGreater(result.backtest.trade_count, 0)
        self.assertFalse(result.degraded)

    def test_second_evaluation_of_same_strategy_raises(self) -> None:
        vault = HoldoutVault("2025-06-28", "2026-06-27", cost_model=CostModel(0.0, 0.0))
        vault.evaluate("s1", _frame(), _hyp(), _config())
        with self.assertRaises(HoldoutAlreadyUsedError):
            vault.evaluate("s1", _frame(), _hyp(), _config())

    def test_degraded_flag_after_budget_exceeded(self) -> None:
        vault = HoldoutVault("2025-06-28", "2026-06-27", touch_budget=1, cost_model=CostModel(0.0, 0.0))
        first = vault.evaluate("s1", _frame(), _hyp(), _config())
        second = vault.evaluate("s2", _frame(), _hyp(), _config())
        self.assertFalse(first.degraded)
        self.assertTrue(second.degraded)


if __name__ == "__main__":
    unittest.main()
