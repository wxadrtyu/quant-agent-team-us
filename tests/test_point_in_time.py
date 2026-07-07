from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.point_in_time import LookAheadError, as_of, assert_no_lookahead


class PointInTimeTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"trade_date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]), "x": [1, 2, 3]}
        )

    def test_as_of_excludes_future_rows(self) -> None:
        sliced = as_of(self._frame(), "2025-01-02")
        self.assertEqual(sliced["x"].tolist(), [1, 2])

    def test_assert_no_lookahead_passes_for_clean_frame(self) -> None:
        assert_no_lookahead(as_of(self._frame(), "2025-01-02"), "2025-01-02")

    def test_assert_no_lookahead_raises_on_future_row(self) -> None:
        with self.assertRaises(LookAheadError):
            assert_no_lookahead(self._frame(), "2025-01-02")


if __name__ == "__main__":
    unittest.main()
