from __future__ import annotations

import argparse
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
NASDAQ100_API_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100?assetclass=stocks"
NASDAQ_HISTORICAL_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"
RUSSELL1000_URL = "https://en.wikipedia.org/wiki/Russell_1000_Index"
IWB_HOLDINGS_URL = (
    "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund"
)

DAILY_PRICE_COLUMNS = [
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_yahoo_symbol(symbol: str) -> str:
    return str(symbol).strip().replace(".", "-")


def normalize_membership_symbols(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["symbol"] = out["symbol"].astype("string").str.strip()
    valid = out["symbol"].notna() & out["symbol"].ne("") & out["symbol"].str.lower().ne("nan")
    out = out.loc[valid].copy()
    out["symbol"] = out["symbol"].astype(str)
    out["yahoo_symbol"] = out["symbol"].map(normalize_yahoo_symbol)
    return out.reset_index(drop=True)


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str:
    available = {str(c).strip(): c for c in columns}
    for candidate in candidates:
        if candidate in available:
            return available[candidate]
    raise ValueError(f"Missing expected columns {list(candidates)} in {list(columns)}")


def parse_wikipedia_constituents(
    table: pd.DataFrame,
    universe_name: str,
    as_of_date: str,
    source: str,
) -> pd.DataFrame:
    symbol_col = _first_existing(table.columns, ["Symbol", "Ticker"])
    name_col = _first_existing(table.columns, ["Security", "Company"])
    sector_col = next((c for c in ["GICS Sector", "Sector"] if c in table.columns), None)
    industry_col = next((c for c in ["GICS Sub-Industry", "Industry"] if c in table.columns), None)

    result = pd.DataFrame(
        {
            "universe_name": universe_name,
            "symbol": table[symbol_col].astype(str).str.strip(),
            "name": table[name_col].astype(str).str.strip(),
            "sector": table[sector_col].astype(str).str.strip() if sector_col else "",
            "industry": table[industry_col].astype(str).str.strip() if industry_col else "",
            "effective_date": as_of_date,
            "end_date": "",
            "membership_type": "current_snapshot",
            "source": source,
            "source_updated_at": utc_now_iso(),
        }
    )
    result = normalize_membership_symbols(result).drop_duplicates(["universe_name", "symbol"])
    return result.reset_index(drop=True)


def parse_ishares_holdings_csv(content: str, as_of_date: str) -> pd.DataFrame:
    lines = content.splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        cols = [part.strip().strip('"') for part in line.split(",")]
        if "Ticker" in cols and "Name" in cols:
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("iShares holdings CSV did not contain a Ticker/Name header")

    frame = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
    frame.columns = [str(c).strip() for c in frame.columns]
    ticker_col = _first_existing(frame.columns, ["Ticker"])
    name_col = _first_existing(frame.columns, ["Name"])
    sector_col = next((c for c in ["Sector"] if c in frame.columns), None)
    exchange_col = next((c for c in ["Exchange"] if c in frame.columns), None)
    currency_col = next((c for c in ["Currency", "Market Currency"] if c in frame.columns), None)

    frame[ticker_col] = frame[ticker_col].astype(str).str.strip()
    frame = frame.loc[
        frame[ticker_col].ne("")
        & frame[ticker_col].ne("-")
        & ~frame[ticker_col].str.contains(" ", regex=False)
    ].copy()
    if "Asset Class" in frame.columns:
        frame = frame.loc[frame["Asset Class"].astype(str).str.lower().eq("equity")]

    result = pd.DataFrame(
        {
            "universe_name": "russell1000",
            "symbol": frame[ticker_col].astype(str).str.strip(),
            "name": frame[name_col].astype(str).str.strip(),
            "sector": frame[sector_col].astype(str).str.strip() if sector_col else "",
            "industry": "",
            "exchange": frame[exchange_col].astype(str).str.strip() if exchange_col else "",
            "currency": frame[currency_col].astype(str).str.strip() if currency_col else "",
            "effective_date": as_of_date,
            "end_date": "",
            "membership_type": "current_snapshot",
            "source": "ishares_iwb_holdings",
            "source_updated_at": utc_now_iso(),
        }
    )
    result = normalize_membership_symbols(result)
    return result.drop_duplicates(["universe_name", "symbol"]).reset_index(drop=True)


def parse_nasdaq100_api(payload: dict, as_of_date: str) -> pd.DataFrame:
    rows = payload.get("data", {}).get("data", {}).get("rows", [])
    frame = pd.DataFrame(rows)
    if frame.empty or "symbol" not in frame.columns:
        raise ValueError("Nasdaq API response did not contain symbol rows")
    frame["symbol"] = frame["symbol"].astype("string").str.strip()
    frame = frame.loc[frame["symbol"].notna() & frame["symbol"].ne("") & frame["symbol"].str.lower().ne("nan")].copy()

    def parse_market_cap(value: object) -> object:
        text = str(value).replace(",", "").replace("$", "").strip()
        if not text:
            return pd.NA
        try:
            return int(float(text))
        except ValueError:
            return pd.NA

    def optional_text(column: str) -> pd.Series:
        if column in frame.columns:
            return frame[column].astype(str).str.strip()
        return pd.Series([""] * len(frame), index=frame.index)

    result = pd.DataFrame(
        {
                "universe_name": "nasdaq100",
                "symbol": frame["symbol"],
                "name": optional_text("companyName"),
                "sector": optional_text("sector"),
                "industry": "",
                "market_cap": frame["marketCap"].map(parse_market_cap) if "marketCap" in frame.columns else pd.NA,
            "effective_date": as_of_date,
            "end_date": "",
            "membership_type": "current_snapshot",
            "source": "nasdaq_api_nasdaq100",
            "source_updated_at": utc_now_iso(),
        }
    )
    result = normalize_membership_symbols(result)
    return result.drop_duplicates(["universe_name", "symbol"]).reset_index(drop=True)


def _parse_number(value: object) -> float:
    text = str(value).replace(",", "").replace("$", "").strip()
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return float("nan")
    return float(text)


def parse_nasdaq_historical_api(payload: dict | None, symbol: str) -> pd.DataFrame:
    data = (payload or {}).get("data") or {}
    rows = (data.get("tradesTable") or {}).get("rows", [])
    if not rows:
        return pd.DataFrame(columns=DAILY_PRICE_COLUMNS)

    frame = pd.DataFrame(rows)
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Nasdaq historical response missing columns: {sorted(missing)}")

    out = pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": pd.to_datetime(frame["date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d"),
            "open": frame["open"].map(_parse_number),
            "high": frame["high"].map(_parse_number),
            "low": frame["low"].map(_parse_number),
            "close": frame["close"].map(_parse_number),
            "volume": frame["volume"].map(_parse_number).astype("Int64"),
        }
    )
    out["adj_close"] = out["close"]
    out["dividend"] = 0.0
    out["split_factor"] = 0.0
    out["source"] = "nasdaq_api_historical"
    return out[DAILY_PRICE_COLUMNS].sort_values("trade_date").reset_index(drop=True)


def flatten_yfinance_history(frame: pd.DataFrame, yahoo_to_symbol: Dict[str, str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()

    records: List[pd.DataFrame] = []
    if isinstance(frame.columns, pd.MultiIndex):
        tickers = list(dict.fromkeys(frame.columns.get_level_values(1)))
        for yahoo_symbol in tickers:
            if yahoo_symbol not in yahoo_to_symbol:
                continue
            one = frame.xs(yahoo_symbol, axis=1, level=1, drop_level=True).copy()
            one["symbol"] = yahoo_to_symbol[yahoo_symbol]
            records.append(one)
    else:
        if len(yahoo_to_symbol) != 1:
            raise ValueError("Single-index yfinance data requires exactly one symbol mapping")
        one = frame.copy()
        one["symbol"] = next(iter(yahoo_to_symbol.values()))
        records.append(one)

    if not records:
        return pd.DataFrame()
    out = pd.concat(records)
    out = out.reset_index(names="trade_date")
    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.strftime("%Y-%m-%d")
    rename = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
        "Dividends": "dividend",
        "Stock Splits": "split_factor",
    }
    out = out.rename(columns=rename)
    for col in ["open", "high", "low", "close", "adj_close", "volume", "dividend", "split_factor"]:
        if col not in out.columns:
            out[col] = 0.0 if col in {"dividend", "split_factor"} else pd.NA
    out["source"] = "yahoo_yfinance"
    return out[
        [
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
    ].sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _read_html_tables(url: str) -> List[pd.DataFrame]:
    import requests

    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return pd.read_html(io.StringIO(response.text))


def fetch_wikipedia_universe(url: str, universe_name: str, as_of_date: str, source: str) -> pd.DataFrame:
    tables = _read_html_tables(url)
    for table in tables:
        cols = set(map(str, table.columns))
        if ({"Symbol", "Security"} <= cols) or ({"Ticker", "Company"} <= cols) or ({"Symbol", "Company"} <= cols):
            return parse_wikipedia_constituents(table, universe_name, as_of_date, source)
    raise ValueError(f"No constituent table found at {url}")


def fetch_ishares_iwb(as_of_date: str) -> pd.DataFrame:
    import requests

    response = requests.get(IWB_HOLDINGS_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return parse_ishares_holdings_csv(response.text, as_of_date)


def fetch_nasdaq100_api(as_of_date: str) -> pd.DataFrame:
    import requests

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/quotes/nasdaq-ndx-index",
    }
    response = requests.get(NASDAQ100_API_URL, headers=headers, timeout=30)
    response.raise_for_status()
    return parse_nasdaq100_api(response.json(), as_of_date)


def fetch_nasdaq_daily(
    symbols: List[str],
    start: str,
    end: str,
    max_workers: int,
    request_timeout: int,
) -> tuple[pd.DataFrame, List[dict]]:
    import requests

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/stocks/aapl/historical",
    }
    frames: List[pd.DataFrame] = []
    errors: List[dict] = []

    def fetch_one(symbol: str) -> tuple[str, pd.DataFrame | None, str | None]:
        session = requests.Session()
        session.headers.update(headers)
        url = NASDAQ_HISTORICAL_URL.format(symbol=symbol)
        params = {
            "assetclass": "stocks",
            "fromdate": start,
            "todate": end,
            "limit": "9999",
        }
        try:
            response = session.get(url, params=params, timeout=request_timeout)
            response.raise_for_status()
            parsed = parse_nasdaq_historical_api(response.json(), symbol)
            if parsed.empty:
                return symbol, None, "empty historical rows"
            return symbol, parsed, None
        except Exception as exc:
            return symbol, None, str(exc)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_one, symbol) for symbol in symbols]
        for completed in as_completed(futures):
            symbol, parsed, error = completed.result()
            if error:
                errors.append({"symbol": symbol, "error": error})
            elif parsed is not None:
                frames.append(parsed)

    if not frames:
        return pd.DataFrame(columns=DAILY_PRICE_COLUMNS), errors
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.loc[prices["symbol"].astype("string").str.strip().ne("")].copy()
    return prices.drop_duplicates(["symbol", "trade_date"]).reset_index(drop=True), errors


def fetch_yahoo_daily(symbols: List[str], start: str, end: str, batch_size: int) -> pd.DataFrame:
    import yfinance as yf

    frames: List[pd.DataFrame] = []
    for offset in range(0, len(symbols), batch_size):
        batch_symbols = symbols[offset : offset + batch_size]
        yahoo_to_symbol = {normalize_yahoo_symbol(symbol): symbol for symbol in batch_symbols}
        tickers = list(yahoo_to_symbol)
        data = yf.download(
            tickers=tickers,
            start=start,
            end=end,
            group_by="column",
            auto_adjust=False,
            actions=True,
            progress=False,
            threads=True,
        )
        flat = flatten_yfinance_history(data, yahoo_to_symbol)
        if not flat.empty:
            frames.append(flat)
    if not frames:
        return pd.DataFrame(columns=DAILY_PRICE_COLUMNS)
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.loc[prices["symbol"].astype("string").str.strip().ne("")].copy()
    return prices.drop_duplicates(["symbol", "trade_date"]).reset_index(drop=True)


def write_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False, encoding="utf-8")


def ensure_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch US large/mid-cap raw data snapshot.")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default=(date.today() + timedelta(days=1)).isoformat())
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--price-source", choices=["nasdaq", "yahoo"], default="nasdaq")
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--request-timeout", type=int, default=15)
    parser.add_argument("--skip-prices", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else Path("data") / "us" / "raw" / args.as_of
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "as_of": args.as_of,
        "start": args.start,
        "end": args.end,
        "created_at": utc_now_iso(),
        "sources": {},
        "warnings": [
            "Universe membership is current_snapshot and is survivorship-biased for historical backtests.",
            "Free web/API data is suitable for research bootstrap, not a production-grade audited feed.",
            "Nasdaq historical prices are raw OHLCV; adj_close is set equal to close until a split/dividend source is added.",
        ],
    }

    universes: List[pd.DataFrame] = []
    for universe_name, url, source in [
        ("sp500", SP500_URL, "wikipedia_sp500"),
        ("russell1000", RUSSELL1000_URL, "wikipedia_russell1000"),
    ]:
        try:
            frame = fetch_wikipedia_universe(url, universe_name, args.as_of, source)
            universes.append(frame)
            manifest["sources"][source] = {"status": "ok", "rows": int(len(frame)), "url": url}
        except Exception as exc:
            manifest["sources"][source] = {"status": "error", "error": str(exc), "url": url}

    try:
        frame = fetch_nasdaq100_api(args.as_of)
        universes.append(frame)
        manifest["sources"]["nasdaq_api_nasdaq100"] = {
            "status": "ok",
            "rows": int(len(frame)),
            "url": NASDAQ100_API_URL,
        }
    except Exception as exc:
        manifest["sources"]["nasdaq_api_nasdaq100"] = {
            "status": "error",
            "error": str(exc),
            "url": NASDAQ100_API_URL,
        }

    if not universes:
        raise RuntimeError("No universe sources were downloaded successfully.")

    membership = pd.concat(universes, ignore_index=True, sort=False)
    membership = normalize_membership_symbols(membership)
    membership = ensure_columns(
        membership,
        [
            "universe_name",
            "symbol",
            "yahoo_symbol",
            "name",
            "sector",
            "industry",
            "exchange",
            "currency",
            "effective_date",
            "end_date",
            "membership_type",
            "source",
            "source_updated_at",
        ],
    )
    all_members = membership.drop_duplicates(["symbol"]).copy()
    all_members["universe_name"] = "us_large_mid"
    membership = pd.concat([membership, all_members], ignore_index=True, sort=False)
    membership = membership.fillna("")
    if "market_cap" in membership.columns:
        membership["market_cap"] = pd.to_numeric(membership["market_cap"], errors="coerce")

    meta_cols = ["symbol", "yahoo_symbol", "name", "sector", "industry", "exchange", "currency", "market_cap", "source"]
    stock_meta = (
        membership.loc[membership["universe_name"].ne("us_large_mid"), meta_cols]
        .drop_duplicates(["symbol"])
        .sort_values("symbol")
        .reset_index(drop=True)
    )

    write_frame(membership, out_dir / "us_index_membership.csv")
    write_frame(stock_meta, out_dir / "us_stock_meta.csv")
    write_frame(membership, out_dir / "us_index_membership.parquet")
    write_frame(stock_meta, out_dir / "us_stock_meta.parquet")
    manifest["membership_rows"] = int(len(membership))
    manifest["stock_count"] = int(stock_meta["symbol"].nunique())

    if not args.skip_prices:
        symbols = sorted(stock_meta["symbol"].dropna().unique().tolist())
        if args.price_source == "nasdaq":
            prices, price_errors = fetch_nasdaq_daily(
                symbols,
                args.start,
                args.end,
                max_workers=args.max_workers,
                request_timeout=args.request_timeout,
            )
        else:
            prices = fetch_yahoo_daily(symbols, args.start, args.end, args.batch_size)
            price_errors = []
        write_frame(prices, out_dir / "us_market_daily.csv")
        write_frame(prices, out_dir / "us_market_daily.parquet")
        downloaded_symbols = set(prices["symbol"].unique()) if not prices.empty else set()
        missing_symbols = sorted(set(symbols) - downloaded_symbols)
        if price_errors:
            with (out_dir / "us_market_daily_errors.json").open("w", encoding="utf-8") as f:
                json.dump(price_errors, f, indent=2, ensure_ascii=False)
        manifest["price_source"] = args.price_source
        manifest["price_rows"] = int(len(prices))
        manifest["price_symbol_count"] = int(prices["symbol"].nunique()) if not prices.empty else 0
        manifest["price_missing_symbol_count"] = int(len(missing_symbols))
        manifest["price_error_count"] = int(len(price_errors))
        if not prices.empty:
            manifest["price_date_min"] = str(prices["trade_date"].min())
            manifest["price_date_max"] = str(prices["trade_date"].max())

    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
