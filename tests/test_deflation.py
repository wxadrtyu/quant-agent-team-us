from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.overfitting import deflate_return


class DeflationTest(unittest.TestCase):
    def test_single_trial_is_unchanged(self) -> None:
        self.assertAlmostEqual(deflate_return(0.40, 1), 0.40)

    def test_more_trials_shrinks_more(self) -> None:
        few = deflate_return(0.40, 10)
        many = deflate_return(0.40, 1000)
        self.assertLess(many, few)
        self.assertLess(few, 0.40)

    def test_deflation_preserves_sign(self) -> None:
        self.assertLess(deflate_return(-0.20, 100), 0.0)


if __name__ == "__main__":
    unittest.main()
