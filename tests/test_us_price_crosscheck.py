from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_price_crosscheck import compare_price_frames, stooq_symbol, yahoo_symbol


class UsPriceCrosscheckTest(unittest.TestCase):
    def test_stooq_symbol_normalizes_common_us_ticker(self) -> None:
        self.assertEqual(stooq_symbol("BRK.B"), "brk-b.us")
        self.assertEqual(stooq_symbol("NVDA"), "nvda.us")

    def test_yahoo_symbol_normalizes_dot_ticker(self) -> None:
        self.assertEqual(yahoo_symbol("BRK.B"), "BRK-B")
        self.assertEqual(yahoo_symbol("NVDA"), "NVDA")

    def test_compare_price_frames_flags_close_mismatch(self) -> None:
        local = pd.DataFrame(
            [
                {"trade_date": "2026-07-10", "close": 100.0, "open": 99.0},
                {"trade_date": "2026-07-09", "close": 98.0, "open": 97.0},
            ]
        )
        external = pd.DataFrame(
            [
                {"trade_date": "2026-07-10", "close": 110.0, "open": 99.0},
                {"trade_date": "2026-07-09", "close": 98.0, "open": 97.0},
            ]
        )

        result = compare_price_frames("NVDA", local, external, tolerance=0.03)

        self.assertEqual(result["status"], "mismatch")
        self.assertGreater(result["max_close_diff_pct"], 0.09)


if __name__ == "__main__":
    unittest.main()
