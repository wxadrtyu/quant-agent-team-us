from __future__ import annotations

import pandas as pd

from scripts.fetch_us_large_mid_data import (
    build_arg_parser,
    flatten_yfinance_history,
    normalize_yahoo_symbol,
    normalize_membership_symbols,
    parse_nasdaq_historical_api,
    parse_nasdaq100_api,
    parse_ishares_holdings_csv,
    parse_wikipedia_constituents,
)


def test_normalize_yahoo_symbol_converts_dot_share_classes() -> None:
    assert normalize_yahoo_symbol("BRK.B") == "BRK-B"
    assert normalize_yahoo_symbol(" BF.B ") == "BF-B"
    assert normalize_yahoo_symbol("AAPL") == "AAPL"


def test_build_arg_parser_defaults_to_nasdaq_with_parallel_workers() -> None:
    args = build_arg_parser().parse_args([])

    assert args.price_source == "nasdaq"
    assert args.max_workers == 16


def test_parse_wikipedia_constituents_marks_current_snapshot() -> None:
    table = pd.DataFrame(
        {
            "Symbol": ["AAPL", "BRK.B"],
            "Security": ["Apple Inc.", "Berkshire Hathaway"],
            "GICS Sector": ["Information Technology", "Financials"],
            "GICS Sub-Industry": ["Technology Hardware", "Multi-Sector Holdings"],
        }
    )

    result = parse_wikipedia_constituents(
        table,
        universe_name="sp500",
        as_of_date="2026-07-11",
        source="wikipedia_sp500",
    )

    assert list(result["symbol"]) == ["AAPL", "BRK.B"]
    assert list(result["yahoo_symbol"]) == ["AAPL", "BRK-B"]
    assert set(result["membership_type"]) == {"current_snapshot"}
    assert set(result["effective_date"]) == {"2026-07-11"}


def test_parse_ishares_holdings_csv_skips_disclaimer_rows() -> None:
    content = """iShares Russell 1000 ETF
Fund Holdings as of,Jul 10, 2026

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date
AAPL,APPLE INC,Information Technology,Equity,100,6.1,100,10,10,United States,NASDAQ,USD,1,USD,-
BRK.B,BERKSHIRE HATHAWAY INC CLASS B,Financials,Equity,50,1.0,50,5,10,United States,New York Stock Exchange Inc.,USD,1,USD,-
- ,USD CASH,Cash and/or Derivatives,Cash,1,0.0,1,1,1,United States,-,USD,1,USD,-
"""

    result = parse_ishares_holdings_csv(content, as_of_date="2026-07-11")

    assert list(result["symbol"]) == ["AAPL", "BRK.B"]
    assert list(result["yahoo_symbol"]) == ["AAPL", "BRK-B"]
    assert set(result["universe_name"]) == {"russell1000"}


def test_parse_nasdaq100_api_marks_current_snapshot() -> None:
    payload = {
        "data": {
            "date": "Jul 10, 2026 12:43 PM",
            "data": {
                "rows": [
                    {
                        "symbol": "AAPL",
                        "companyName": "Apple Inc. Common Stock",
                        "marketCap": "4,619,687,519,460",
                    },
                    {
                        "symbol": "GOOG",
                        "companyName": "Alphabet Inc. Class C Capital Stock",
                        "marketCap": "4,277,069,160,000",
                    },
                ]
            },
        }
    }

    result = parse_nasdaq100_api(payload, as_of_date="2026-07-11")

    assert list(result["symbol"]) == ["AAPL", "GOOG"]
    assert set(result["universe_name"]) == {"nasdaq100"}
    assert result.loc[result["symbol"] == "AAPL", "market_cap"].iloc[0] == 4619687519460


def test_normalize_membership_symbols_drops_blank_and_nan_symbols() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["AAPL", "", None, "nan", "BRK.B"],
            "name": ["Apple", "Blank", "Missing", "Text NaN", "Berkshire"],
        }
    )

    result = normalize_membership_symbols(frame)

    assert list(result["symbol"]) == ["AAPL", "BRK.B"]
    assert list(result["yahoo_symbol"]) == ["AAPL", "BRK-B"]


def test_parse_nasdaq_historical_api_cleans_price_and_volume_strings() -> None:
    payload = {
        "data": {
            "symbol": "AAPL",
            "tradesTable": {
                "rows": [
                    {
                        "date": "07/09/2026",
                        "close": "$316.22",
                        "volume": "48,124,490",
                        "open": "$310.51",
                        "high": "$316.53",
                        "low": "$308.16",
                    }
                ]
            },
        }
    }

    result = parse_nasdaq_historical_api(payload, "AAPL")

    assert list(result["symbol"]) == ["AAPL"]
    assert result.loc[0, "trade_date"] == "2026-07-09"
    assert result.loc[0, "close"] == 316.22
    assert result.loc[0, "volume"] == 48124490
    assert result.loc[0, "adj_close"] == 316.22
    assert result.loc[0, "source"] == "nasdaq_api_historical"


def test_parse_nasdaq_historical_api_returns_empty_when_data_is_null() -> None:
    result = parse_nasdaq_historical_api({"data": None}, "BF.B")

    assert result.empty
    assert list(result.columns) == [
        "symbol",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "dividend",
        "split_factor",
        "source",
    ]


def test_parse_nasdaq_historical_api_returns_empty_when_payload_is_null() -> None:
    result = parse_nasdaq_historical_api(None, "BF.B")

    assert result.empty


def test_parse_nasdaq_historical_api_returns_empty_when_trades_table_is_null() -> None:
    result = parse_nasdaq_historical_api({"data": {"tradesTable": None}}, "BF.B")

    assert result.empty


def test_flatten_yfinance_history_handles_multiindex_columns() -> None:
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["AAPL", "MSFT"]]
    )
    frame = pd.DataFrame(
        [[1.0, 10.0, 2.0, 11.0, 0.5, 9.0, 1.5, 10.5, 1.4, 10.2, 100, 200]],
        index=pd.to_datetime(["2026-07-10"]),
        columns=columns,
    )

    result = flatten_yfinance_history(frame, {"AAPL": "AAPL", "MSFT": "MSFT"})

    assert set(result["symbol"]) == {"AAPL", "MSFT"}
    aapl = result.loc[result["symbol"] == "AAPL"].iloc[0]
    assert aapl["trade_date"] == "2026-07-10"
    assert aapl["open"] == 1.0
    assert aapl["adj_close"] == 1.4
