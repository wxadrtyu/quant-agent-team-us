from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_universe import build_dynamic_liquidity_membership, filter_panel_by_pit, normalize_pit_membership


class UsUniverseTest(unittest.TestCase):
    def test_filter_panel_by_pit_keeps_only_active_membership_dates(self) -> None:
        panel = pd.DataFrame(
            [
                {"symbol": "AAA", "trade_date": "2024-01-02", "score_x": 1.0},
                {"symbol": "AAA", "trade_date": "2024-02-01", "score_x": 2.0},
                {"symbol": "BBB", "trade_date": "2024-02-01", "score_x": 3.0},
            ]
        )
        membership = normalize_pit_membership(
            pd.DataFrame(
                [
                    {"symbol": "AAA", "universe_name": "TEST", "start_date": "2024-01-15", "end_date": "2024-12-31"},
                    {"symbol": "BBB", "universe_name": "OTHER", "start_date": "2024-01-01", "end_date": ""},
                ]
            ),
            source="unit",
            as_of_date="2026-07-12",
        )

        filtered = filter_panel_by_pit(panel, membership, universe_names=["TEST"])

        self.assertEqual(filtered["symbol"].tolist(), ["AAA"])
        self.assertEqual(pd.Timestamp(filtered["trade_date"].iloc[0]), pd.Timestamp("2024-02-01"))

    def test_dynamic_liquidity_membership_uses_daily_price_and_adv_filters(self) -> None:
        prices = pd.DataFrame(
            [
                {"symbol": "AAA", "trade_date": "2024-01-01", "close": 10.0, "dollar_volume_20d": 20_000_000},
                {"symbol": "BBB", "trade_date": "2024-01-01", "close": 4.0, "dollar_volume_20d": 20_000_000},
                {"symbol": "CCC", "trade_date": "2024-01-01", "close": 12.0, "dollar_volume_20d": 5_000_000},
            ]
        )

        membership = build_dynamic_liquidity_membership(prices, min_price=5.0, min_dollar_volume_20d=10_000_000)

        self.assertEqual(membership["symbol"].tolist(), ["AAA"])
        self.assertEqual(membership["membership_type"].iloc[0], "daily_dynamic_liquidity")
        self.assertEqual(membership["universe_name"].iloc[0], "dynamic_liquidity")


if __name__ == "__main__":
    unittest.main()
