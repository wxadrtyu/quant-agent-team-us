from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_strategy_factory_loop import FACTOR_LIBRARY, candidate_hypotheses


class UsStrategyFactoryFactorsTest(unittest.TestCase):
    def test_microstructure_factor_specs_are_registered(self) -> None:
        names = {factor.name for factor in FACTOR_LIBRARY}

        self.assertIn("overnight_gap_1d", names)
        self.assertIn("intraday_ret_1d", names)
        self.assertIn("close_pos_20d", names)

    def test_candidate_generation_round_robins_templates(self) -> None:
        prefixes = [candidate_id.split("_", 1)[0] for candidate_id, _ in candidate_hypotheses(6)]

        self.assertGreaterEqual(len(set(prefixes)), 4)


if __name__ == "__main__":
    unittest.main()
