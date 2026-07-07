from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.overfitting import OverfittingInputs, overfitting_score


class OverfittingScoreTest(unittest.TestCase):
    def _base(self, **kw) -> OverfittingInputs:
        params = dict(outer_iterations=1, total_trials=10, hp_dimensions=2, trade_count=100)
        params.update(kw)
        return OverfittingInputs(**params)

    def test_score_in_unit_interval(self) -> None:
        score = overfitting_score(self._base())
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_more_trials_is_riskier(self) -> None:
        low = overfitting_score(self._base(total_trials=10))
        high = overfitting_score(self._base(total_trials=1000))
        self.assertGreater(high, low)

    def test_fewer_trades_is_riskier(self) -> None:
        many = overfitting_score(self._base(trade_count=500))
        few = overfitting_score(self._base(trade_count=5))
        self.assertGreater(few, many)

    def test_degradation_increases_risk(self) -> None:
        none = overfitting_score(self._base())
        degraded = overfitting_score(self._base(dev_return=0.40, holdout_return=0.05))
        self.assertGreater(degraded, none)


if __name__ == "__main__":
    unittest.main()
