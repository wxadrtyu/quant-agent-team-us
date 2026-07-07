from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.walk_forward import Fold, purged_walk_forward, split_three_year_window


class WindowSplitTest(unittest.TestCase):
    def test_split_three_year_window_boundaries(self) -> None:
        split = split_three_year_window(date(2026, 6, 27))
        self.assertEqual(split.holdout_end, date(2026, 6, 27))
        self.assertEqual(split.holdout_start, date(2025, 6, 28))
        self.assertEqual(split.development_end, date(2025, 6, 27))
        self.assertEqual(split.development_start, date(2023, 6, 28))

    def test_split_handles_leap_day_end(self) -> None:
        split = split_three_year_window(date(2024, 2, 29))
        self.assertEqual(split.holdout_start, date(2023, 3, 1))


class PurgedWalkForwardTest(unittest.TestCase):
    def _dates(self, n: int) -> list:
        start = date(2025, 1, 1)
        return [start + timedelta(days=i) for i in range(n)]

    def test_two_folds_purge_embargo_bar(self) -> None:
        dates = self._dates(10)
        folds = purged_walk_forward(dates, n_folds=2, embargo=1)
        self.assertEqual(len(folds), 1)  # first block has no train side
        fold = folds[0]
        self.assertEqual(fold.test, dates[5:10])
        self.assertEqual(fold.train, dates[0:4])  # index 4 dropped as embargo
        self.assertNotIn(dates[4], fold.train)

    def test_no_train_overlaps_test(self) -> None:
        dates = self._dates(12)
        for fold in purged_walk_forward(dates, n_folds=3, embargo=1):
            self.assertTrue(max(fold.train) < min(fold.test))

    def test_unsorted_dates_rejected(self) -> None:
        with self.assertRaises(ValueError):
            purged_walk_forward(list(reversed(self._dates(6))), n_folds=2)


if __name__ == "__main__":
    unittest.main()
