from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


class HypothesisTest(unittest.TestCase):
    def test_factor_def_validates_direction(self) -> None:
        FactorDef(name="momentum_20d", source_field="momentum_20d", direction="long_high")
        with self.assertRaises(ValueError):
            FactorDef(name="x", source_field="x", direction="sideways")

    def test_hypothesis_validates_market_and_factor_count(self) -> None:
        factors = [FactorDef("momentum_20d", "momentum_20d", "long_high")]
        h = FactorHypothesis(market="cn", factors=factors)
        self.assertEqual(h.combination, "linear_zscore")
        with self.assertRaises(ValueError):
            FactorHypothesis(market="jp", factors=factors)
        with self.assertRaises(ValueError):
            FactorHypothesis(market="cn", factors=[])

    def test_hypothesis_enforces_parsimony_cap(self) -> None:
        too_many = [FactorDef(f"f{i}", f"f{i}", "long_high") for i in range(9)]
        with self.assertRaises(ValueError):
            FactorHypothesis(market="cn", factors=too_many)

    def test_factor_config_holds_resolved_params(self) -> None:
        cfg = FactorConfig(weights={"momentum_20d": 1.0}, top_n=10, rebalance_days=5)
        self.assertEqual(cfg.top_n, 10)
        self.assertEqual(cfg.rebalance_days, 5)


if __name__ == "__main__":
    unittest.main()
