from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_rolling_validation import iter_month_windows, summarize_curve


class UsRollingValidationTest(unittest.TestCase):
    def test_iter_month_windows_clips_to_requested_range(self) -> None:
        windows = list(iter_month_windows("2026-01-15", "2026-03-10"))

        self.assertEqual(
            windows,
            [
                (pd.Timestamp("2026-01-15"), pd.Timestamp("2026-01-31")),
                (pd.Timestamp("2026-02-01"), pd.Timestamp("2026-02-28")),
                (pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-10")),
            ],
        )

    def test_summarize_curve_counts_negative_absolute_positive_excess_as_win(self) -> None:
        curve = pd.DataFrame(
            [
                {"strategy_ret": -0.02, "benchmark_ret": -0.05, "excess_ret": 0.03, "equity": 0.98, "benchmark_equity": 0.95},
                {"strategy_ret": 0.01, "benchmark_ret": -0.01, "excess_ret": 0.02, "equity": 0.9898, "benchmark_equity": 0.9405},
            ]
        )

        summary = summarize_curve(curve, periods_per_year=12.0)

        self.assertGreater(summary["excess_return"], 0)
        self.assertEqual(summary["win_excess"], 1.0)
        self.assertLess(summary["total_return"], 0)


if __name__ == "__main__":
    unittest.main()
