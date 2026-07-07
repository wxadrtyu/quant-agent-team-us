from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.cost_model import CostModel


class CostModelTest(unittest.TestCase):
    def test_entry_fill_is_worse_than_reference(self) -> None:
        model = CostModel(commission_bps=5.0, slippage_bps=10.0)
        self.assertAlmostEqual(model.entry_fill_price(100.0), 100.1)

    def test_exit_fill_is_worse_than_reference(self) -> None:
        model = CostModel(commission_bps=5.0, slippage_bps=10.0)
        self.assertAlmostEqual(model.exit_fill_price(100.0), 99.9)

    def test_commission_scales_with_notional(self) -> None:
        model = CostModel(commission_bps=5.0, slippage_bps=10.0)
        self.assertAlmostEqual(model.commission(1_000_000.0), 500.0)

    def test_zero_model_is_frictionless(self) -> None:
        model = CostModel(commission_bps=0.0, slippage_bps=0.0)
        self.assertEqual(model.entry_fill_price(100.0), 100.0)
        self.assertEqual(model.exit_fill_price(100.0), 100.0)
        self.assertEqual(model.commission(1_000_000.0), 0.0)

    def test_for_market_presets_are_non_zero(self) -> None:
        cn = CostModel.for_market("cn")
        us = CostModel.for_market("us")
        self.assertGreater(cn.commission_bps + cn.slippage_bps, 0.0)
        self.assertGreater(us.commission_bps + us.slippage_bps, 0.0)
        with self.assertRaises(ValueError):
            CostModel.for_market("jp")


if __name__ == "__main__":
    unittest.main()
