from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .market_fetch import DailyBar


def normalize_us_bars(symbol: str, rows: List[dict]) -> List[DailyBar]:
    bars: List[DailyBar] = []
    for row in rows:
        close = float(row["close"])
        volume = float(row["volume"])
        bars.append(
            DailyBar(
                stock_code=symbol,
                trade_date=str(row["date"]),
                close_price=close,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                volume=volume,
                turnover=close * volume,  # US feeds lack turnover; dollar-volume proxy
            )
        )
    return bars


@dataclass
class USEquityProvider:
    fetch: Optional[Callable[[str, Optional[str], Optional[str]], List[dict]]] = None
    name: str = "us_yfinance"

    def _run_fetch(self, symbol: str, start: Optional[str], end: Optional[str]) -> List[dict]:
        if self.fetch is not None:
            return self.fetch(symbol, start, end)
        import yfinance  # lazy import; only needed for live fetches

        data = yfinance.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
        rows: List[dict] = []
        for index, record in data.iterrows():
            rows.append(
                {
                    "date": index.strftime("%Y-%m-%d"),
                    "open": record["Open"],
                    "high": record["High"],
                    "low": record["Low"],
                    "close": record["Close"],
                    "volume": record["Volume"],
                }
            )
        return rows

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[DailyBar]:
        rows = self._run_fetch(stock_code, start_date, end_date)
        return normalize_us_bars(stock_code, rows)
