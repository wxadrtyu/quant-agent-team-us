from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.us_market import USEquityProvider, normalize_us_bars


class UsMarketTest(unittest.TestCase):
    def test_normalize_builds_dailybar_with_turnover_proxy(self) -> None:
        rows = [{"date": "2026-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 1000.0}]
        bars = normalize_us_bars("AAPL", rows)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].stock_code, "AAPL")
        self.assertEqual(bars[0].trade_date, "2026-01-02")
        self.assertEqual(bars[0].close_price, 104.0)
        self.assertEqual(bars[0].turnover, 104.0 * 1000.0)

    def test_provider_uses_injected_fetch(self) -> None:
        captured = {}

        def fake_fetch(symbol, start, end):
            captured["args"] = (symbol, start, end)
            return [{"date": "2026-01-02", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0}]

        provider = USEquityProvider(fetch=fake_fetch)
        bars = provider.fetch_daily_bars("MSFT", start_date="2026-01-01", end_date="2026-01-31")
        self.assertEqual(provider.name, "us_yfinance")
        self.assertEqual(captured["args"], ("MSFT", "2026-01-01", "2026-01-31"))
        self.assertEqual(bars[0].stock_code, "MSFT")
        self.assertEqual(bars[0].turnover, 1.5 * 10.0)


if __name__ == "__main__":
    unittest.main()
