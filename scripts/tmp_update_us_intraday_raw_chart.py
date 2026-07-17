from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import time

import pandas as pd
import requests


BASE = Path(r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
OUT = Path(r"E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart")
START_TS = int(datetime(2026, 7, 11, tzinfo=timezone.utc).timestamp())
END_TS = int(datetime(2026, 7, 17, tzinfo=timezone.utc).timestamp())
MAX_WORKERS = 18


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def fetch_one(symbol: str) -> tuple[str, pd.DataFrame | None, str | None]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(symbol)}"
    params = {
        "period1": START_TS,
        "period2": END_TS,
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")
            payload = resp.json()
            result = (payload.get("chart", {}).get("result") or [None])[0]
            if not result or not result.get("timestamp"):
                raise RuntimeError("empty result")
            timestamps = result["timestamp"]
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get(
                "adjclose", []
            )
            events = result.get("events", {})
            dividends = {}
            for item in events.get("dividends", {}).values():
                dividends[pd.to_datetime(item["date"], unit="s", utc=True).date().isoformat()] = item.get("amount", 0.0)
            splits = {}
            for item in events.get("splits", {}).values():
                splits[pd.to_datetime(item["date"], unit="s", utc=True).date().isoformat()] = item.get("splitRatio", 0.0)

            rows = []
            for i, ts in enumerate(timestamps):
                trade_date = pd.to_datetime(ts, unit="s", utc=True).date().isoformat()
                close = (quote.get("close") or [None] * len(timestamps))[i]
                if close is None:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "open": (quote.get("open") or [None] * len(timestamps))[i],
                        "high": (quote.get("high") or [None] * len(timestamps))[i],
                        "low": (quote.get("low") or [None] * len(timestamps))[i],
                        "close": close,
                        "adj_close": adj[i] if i < len(adj) and adj[i] is not None else close,
                        "volume": (quote.get("volume") or [None] * len(timestamps))[i],
                        "dividend": dividends.get(trade_date, 0.0),
                        "split_factor": splits.get(trade_date, 0.0),
                        "source": "yahoo_chart_intraday",
                    }
                )
            if not rows:
                raise RuntimeError("no valid close rows")
            return symbol, pd.DataFrame(rows), None
        except Exception as exc:
            if attempt == 2:
                return symbol, None, repr(exc)
            time.sleep(0.6 * (attempt + 1))
    return symbol, None, "unknown error"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in [
        "us_index_membership.parquet",
        "us_index_membership.csv",
        "us_stock_meta.parquet",
        "us_stock_meta.csv",
    ]:
        src = BASE / name
        if src.exists():
            shutil.copy2(src, OUT / name)

    prices = pd.read_parquet(BASE / "us_market_daily.parquet")
    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.date.astype(str)
    symbols = sorted(prices["symbol"].dropna().astype(str).unique())

    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {pool.submit(fetch_one, symbol): symbol for symbol in symbols}
        for future in as_completed(future_map):
            symbol, frame, error = future.result()
            done += 1
            if frame is not None:
                frames.append(frame)
            else:
                errors.append({"symbol": symbol, "error": error or "unknown"})
            if done % 50 == 0 or done == len(symbols):
                ok = len(frames)
                print(f"progress {done}/{len(symbols)} ok_symbols={ok} errors={len(errors)}", flush=True)

    inc = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if inc.empty:
        raise RuntimeError("No Yahoo chart rows fetched")
    inc["trade_date"] = pd.to_datetime(inc["trade_date"]).dt.date.astype(str)

    combined = pd.concat([prices, inc], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(["symbol", "trade_date"], keep="last")
    combined = combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    combined.to_parquet(OUT / "us_market_daily.parquet", index=False)
    combined.to_csv(OUT / "us_market_daily.csv", index=False, encoding="utf-8")

    coverage = combined.groupby("trade_date")["symbol"].nunique().tail(12).reset_index()
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_raw_dir": str(BASE),
        "source": "Yahoo Finance chart API incremental append",
        "symbols_requested": len(symbols),
        "incremental_rows": int(len(inc)),
        "incremental_symbols": int(inc["symbol"].nunique()),
        "combined_rows": int(len(combined)),
        "combined_symbols": int(combined["symbol"].nunique()),
        "max_trade_date": str(pd.to_datetime(combined["trade_date"]).dt.date.max()),
        "coverage_tail": coverage.to_dict(orient="records"),
        "errors": errors[:200],
        "error_count": len(errors),
        "note": "2026-07-16 rows may be intraday because the US session is not closed at Asia/Shanghai evening update time.",
    }
    (OUT / "manifest_intraday_update.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
