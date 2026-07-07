from __future__ import annotations

import contextlib
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import io
import os
from pathlib import Path
from typing import Iterable, List, Protocol

PYTDX_SERVERS = [
    ("39.108.28.83", 7709),
    ("119.147.212.81", 7709),
    ("119.147.212.83", 7709),
]
NOISY_FALLBACK_PROVIDERS = {"pytdx", "mootdx", "yfinance"}


@dataclass(frozen=True)
class DailyBar:
    stock_code: str
    trade_date: str
    close_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: float
    turnover: float

    def to_csv_row(self) -> dict[str, str]:
        return {
            "股票代码": self.stock_code,
            "交易日期": self.trade_date,
            "收盘价": _format_number(self.close_price),
            "开盘价": _format_number(self.open_price),
            "最高价": _format_number(self.high_price),
            "最低价": _format_number(self.low_price),
            "成交量": _format_number(self.volume),
            "成交额": _format_number(self.turnover),
        }


class MarketDataProvider(Protocol):
    name: str

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        ...


class AkshareDailyProvider:
    name = "akshare"

    def __init__(self) -> None:
        import akshare as ak  # type: ignore

        self._ak = ak

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        with _without_proxy_env():
            frame = self._ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=_compact_date(start_date),
                end_date=_compact_date(end_date),
                adjust="",
            )
        return [_from_row(stock_code, row) for _, row in frame.iterrows()]


class EFinanceDailyProvider:
    name = "efinance"

    def __init__(self) -> None:
        import efinance as ef  # type: ignore

        self._ef = ef

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        with _without_proxy_env():
            frame = self._ef.stock.get_quote_history(
                stock_code,
                beg=_compact_date(start_date),
                end=_compact_date(end_date),
                klt=101,
                fqt=0,
            )
        return [_from_row(stock_code, row) for _, row in frame.iterrows()]


class BaostockDailyProvider:
    name = "baostock"

    def __init__(self) -> None:
        import baostock as bs  # type: ignore

        self._bs = bs

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        login = self._bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise RuntimeError(f"baostock login failed: {login.error_msg}")
        try:
            code = _baostock_code(stock_code)
            result = self._bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume,amount",
                start_date=start_date or "",
                end_date=end_date or "",
                frequency="d",
                adjustflag="3",
            )
            rows: List[DailyBar] = []
            while result.next():
                date, open_price, high_price, low_price, close_price, volume, turnover = result.get_row_data()
                rows.append(
                    DailyBar(
                        stock_code=stock_code,
                        trade_date=date,
                        close_price=float(close_price),
                        open_price=float(open_price),
                        high_price=float(high_price),
                        low_price=float(low_price),
                        volume=float(volume),
                        turnover=float(turnover),
                    )
                )
            return rows
        finally:
            self._bs.logout()


class PytdxDailyProvider:
    name = "pytdx"

    def __init__(self) -> None:
        from pytdx.hq import TDXParams  # type: ignore

        self._daily_type = TDXParams.KLINE_TYPE_DAILY

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        from pytdx.hq import TdxHq_API  # type: ignore

        market = _pytdx_market(stock_code)
        rows = None
        for host, port in PYTDX_SERVERS:
            api = TdxHq_API()
            connected = False
            try:
                connected = bool(api.connect(host, port, time_out=0.7))
                if connected:
                    rows = self._fetch_all_bars(api, market, stock_code)
                    if rows:
                        break
            finally:
                with contextlib.suppress(Exception):
                    if connected:
                        api.disconnect()
        if not rows:
            return []

        filtered: list[DailyBar] = []
        for row in rows:
            trade_date = str(row["datetime"]).split(" ", 1)[0]
            if start_date and trade_date < start_date:
                continue
            if end_date and trade_date > end_date:
                continue
            filtered.append(
                DailyBar(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    close_price=float(row["close"]),
                    open_price=float(row["open"]),
                    high_price=float(row["high"]),
                    low_price=float(row["low"]),
                    volume=float(row["vol"]),
                    turnover=float(row["amount"]),
                )
            )
        return filtered

    def _fetch_all_bars(self, api: object, market: int, stock_code: str) -> list[dict[str, object]]:
        collected: list[dict[str, object]] = []
        offset = 0
        while True:
            batch = api.get_security_bars(self._daily_type, market, stock_code, offset, 800)
            if not batch:
                break
            collected.extend(batch)
            if len(batch) < 800:
                break
            offset += 800
        deduped: dict[str, dict[str, object]] = {}
        for row in collected:
            trade_date = str(row["datetime"]).split(" ", 1)[0]
            deduped[trade_date] = row
        return [deduped[trade_date] for trade_date in sorted(deduped)]


class MootdxDailyProvider:
    name = "mootdx"

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        from mootdx.quotes import StdQuotes  # type: ignore

        rows = None
        for host, port in PYTDX_SERVERS:
            client = None
            try:
                client = StdQuotes(
                    server=(host, port),
                    timeout=0.7,
                    heartbeat=False,
                    auto_retry=False,
                    raise_exception=True,
                )
                rows = self._fetch_all_bars(client, stock_code)
            except Exception:
                rows = None
            finally:
                if client is not None:
                    with contextlib.suppress(Exception):
                        client.close()
            if rows:
                break

        if not rows:
            return []

        filtered: list[DailyBar] = []
        for row in rows:
            trade_date = row["datetime"].split(" ", 1)[0]
            if start_date and trade_date < start_date:
                continue
            if end_date and trade_date > end_date:
                continue
            filtered.append(
                DailyBar(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    close_price=float(row["close"]),
                    open_price=float(row["open"]),
                    high_price=float(row["high"]),
                    low_price=float(row["low"]),
                    volume=float(row["vol"]) * 100.0,
                    turnover=float(row["amount"]),
                )
            )
        return filtered

    def _fetch_all_bars(self, client: object, stock_code: str) -> list[dict[str, object]]:
        collected: list[dict[str, object]] = []
        start = 0
        while True:
            frame = client.bars(symbol=stock_code, frequency=9, start=start, offset=800)
            if frame is None or frame.empty:
                break
            records = frame.to_dict("records")
            collected.extend(records)
            if len(records) < 800:
                break
            start += 800
        deduped: dict[str, dict[str, object]] = {}
        for row in collected:
            trade_date = row["datetime"].split(" ", 1)[0]
            deduped[trade_date] = row
        return [deduped[trade_date] for trade_date in sorted(deduped)]


class YahooFinanceDailyProvider:
    name = "yfinance"

    def __init__(self) -> None:
        import yfinance as yf  # type: ignore

        self._yf = yf

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[DailyBar]:
        ticker = _yahoo_symbol(stock_code)
        with _without_proxy_env():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                frame = self._yf.download(
                    ticker,
                    start=start_date,
                    end=_next_date(end_date),
                    auto_adjust=False,
                    progress=False,
                )
        if frame is None or frame.empty:
            return []

        if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
            frame.columns = frame.columns.get_level_values(0)

        rows: list[DailyBar] = []
        for trade_date, row in frame.iterrows():
            close_price = float(row["Close"])
            open_price = float(row["Open"])
            high_price = float(row["High"])
            low_price = float(row["Low"])
            volume = float(row["Volume"])
            # Yahoo does not expose成交额 for A-shares; use cash proxy as the last-resort fallback.
            turnover = close_price * volume
            rows.append(
                DailyBar(
                    stock_code=stock_code,
                    trade_date=trade_date.date().isoformat(),
                    close_price=close_price,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    volume=volume,
                    turnover=turnover,
                )
            )
        return rows


def get_market_data_providers() -> List[MarketDataProvider]:
    providers: List[MarketDataProvider] = []
    for provider_cls in (
        AkshareDailyProvider,
        EFinanceDailyProvider,
        BaostockDailyProvider,
        YahooFinanceDailyProvider,
        PytdxDailyProvider,
        MootdxDailyProvider,
    ):
        try:
            providers.append(provider_cls())
        except Exception:
            continue
    return providers


def fetch_daily_bars_with_fallback(
    stock_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    providers: Iterable[MarketDataProvider] | None = None,
    max_attempts: int = 3,
) -> tuple[List[DailyBar], str]:
    attempted = list(providers or get_market_data_providers())
    errors: List[str] = []
    for provider in attempted:
        last_exc: Exception | None = None
        attempt_limit = min(max_attempts, _provider_attempt_limit(provider))
        for attempt in range(1, attempt_limit + 1):
            try:
                rows = provider.fetch_daily_bars(stock_code, start_date=start_date, end_date=end_date)
                if rows:
                    normalized_rows = [_normalize_daily_bar_units(row) for row in rows]
                    return sorted(normalized_rows, key=lambda item: item.trade_date, reverse=True), provider.name
                last_exc = RuntimeError("provider returned no rows")
            except Exception as exc:
                last_exc = exc
        if last_exc is not None:
            errors.append(f"{provider.name}: {last_exc}")
    raise RuntimeError(f"failed to fetch {stock_code}; " + "; ".join(errors or ["no providers available"]))


def _provider_attempt_limit(provider: MarketDataProvider) -> int:
    return 1 if getattr(provider, "name", "") in NOISY_FALLBACK_PROVIDERS else 3


def load_stock_history_rows(path: Path) -> List[DailyBar]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            DailyBar(
                stock_code=(row.get("股票代码") or path.stem).strip(),
                trade_date=row["交易日期"],
                close_price=float(row["收盘价"]),
                open_price=float(row["开盘价"]),
                high_price=float(row["最高价"]),
                low_price=float(row["最低价"]),
                volume=float(row["成交量"]),
                turnover=float(row["成交额"]),
            )
            for row in reader
        ]
    return sorted(rows, key=lambda item: item.trade_date, reverse=True)


def merge_market_rows(existing_rows: Iterable[DailyBar], incoming_rows: Iterable[DailyBar]) -> List[DailyBar]:
    by_date: dict[str, DailyBar] = {row.trade_date: row for row in existing_rows}
    for row in incoming_rows:
        by_date[row.trade_date] = row
    return sorted(by_date.values(), key=lambda item: item.trade_date, reverse=True)


def write_stock_history_rows(path: Path, rows: Iterable[DailyBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["股票代码", "交易日期", "收盘价", "开盘价", "最高价", "最低价", "成交量", "成交额"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def update_stock_history_file(
    source_dir: Path,
    stock_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    providers: Iterable[MarketDataProvider] | None = None,
) -> dict[str, object]:
    target = source_dir / f"{stock_code}.csv"
    existing_rows = load_stock_history_rows(target)
    effective_start_date = resolve_stock_fetch_start_date(existing_rows, explicit_start_date=start_date)
    incoming_rows, provider_name = fetch_daily_bars_with_fallback(
        stock_code,
        start_date=effective_start_date,
        end_date=end_date,
        providers=providers,
    )
    merged = merge_market_rows(existing_rows, incoming_rows)
    inserted_dates = sorted(
        {row.trade_date for row in incoming_rows} - {row.trade_date for row in existing_rows},
        reverse=True,
    )
    write_stock_history_rows(target, merged)
    return {
        "stock_code": stock_code,
        "provider": provider_name,
        "start_date_used": effective_start_date,
        "rows_fetched": len(incoming_rows),
        "new_dates": inserted_dates,
        "total_rows": len(merged),
        "path": str(target),
    }


def resolve_stock_fetch_start_date(
    existing_rows: Iterable[DailyBar],
    explicit_start_date: str | None = None,
) -> str | None:
    if explicit_start_date:
        return explicit_start_date
    rows = list(existing_rows)
    if not rows:
        return None
    latest_trade_date = max(row.trade_date for row in rows)
    return (
        datetime.strptime(latest_trade_date, "%Y-%m-%d").date() + timedelta(days=1)
    ).isoformat()


def _compact_date(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("-", "")


def _baostock_code(stock_code: str) -> str:
    if stock_code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return f"sh.{stock_code}"
    return f"sz.{stock_code}"


def _pytdx_market(stock_code: str) -> int:
    if stock_code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return 1
    return 0


def _yahoo_symbol(stock_code: str) -> str:
    if stock_code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return f"{stock_code}.SS"
    return f"{stock_code}.SZ"


def _next_date(value: str | None) -> str | None:
    if not value:
        return None
    return (datetime.strptime(value, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()


def _from_row(stock_code: str, row: object) -> DailyBar:
    def get_value(*names: str) -> object:
        for name in names:
            if hasattr(row, "get") and row.get(name) is not None:
                return row.get(name)
            if hasattr(row, "__getitem__"):
                try:
                    return row[name]  # type: ignore[index]
                except Exception:
                    continue
        raise KeyError(names[0])

    return DailyBar(
        stock_code=stock_code,
        trade_date=str(get_value("日期", "交易日期", "date")),
        close_price=float(get_value("收盘", "收盘价", "close")),
        open_price=float(get_value("开盘", "开盘价", "open")),
        high_price=float(get_value("最高", "最高价", "high")),
        low_price=float(get_value("最低", "最低价", "low")),
        volume=float(get_value("成交量", "volume")),
        turnover=float(get_value("成交额", "amount", "turnover")),
    )


def _normalize_daily_bar_units(row: DailyBar) -> DailyBar:
    if row.volume <= 0 or row.turnover <= 0:
        return row

    price_candidates = [
        value
        for value in (row.open_price, row.high_price, row.low_price, row.close_price)
        if value > 0
    ]
    if not price_candidates:
        return row

    price_proxy = sum(price_candidates) / len(price_candidates)
    implied_share_volume = row.turnover / price_proxy
    if implied_share_volume <= 0:
        return row

    ratio = implied_share_volume / row.volume
    if 80.0 <= ratio <= 120.0:
        return DailyBar(
            stock_code=row.stock_code,
            trade_date=row.trade_date,
            close_price=row.close_price,
            open_price=row.open_price,
            high_price=row.high_price,
            low_price=row.low_price,
            volume=row.volume * 100.0,
            turnover=row.turnover,
        )
    return row


@contextlib.contextmanager
def _without_proxy_env() -> Iterable[None]:
    proxy_keys = (
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    )
    original = {key: os.environ.get(key) for key in proxy_keys}
    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _format_number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"
