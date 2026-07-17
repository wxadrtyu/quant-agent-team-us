from __future__ import annotations

import argparse
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def fetch_one(symbol: str, start_ts: int, end_ts: int, timeout: int) -> tuple[str, pd.DataFrame | None, str | None]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(symbol)}"
    params = {
        "period1": start_ts,
        "period2": end_ts,
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")
            payload = resp.json()
            result = (payload.get("chart", {}).get("result") or [None])[0]
            if not result or not result.get("timestamp"):
                raise RuntimeError("empty result")
            timestamps = result["timestamp"]
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose", [])
            events = result.get("events", {})
            dividends = {
                pd.to_datetime(item["date"], unit="s", utc=True).date().isoformat(): item.get("amount", 0.0)
                for item in events.get("dividends", {}).values()
            }
            splits = {
                pd.to_datetime(item["date"], unit="s", utc=True).date().isoformat(): item.get("splitRatio", 0.0)
                for item in events.get("splits", {}).values()
            }

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


def copy_static_files(base: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in [
        "us_index_membership.parquet",
        "us_index_membership.csv",
        "us_stock_meta.parquet",
        "us_stock_meta.csv",
    ]:
        src = base / name
        if src.exists():
            shutil.copy2(src, out / name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--start-date", default="2026-07-11")
    parser.add_argument("--end-date", required=True, help="Exclusive UTC end date, e.g. 2026-07-19 to include 2026-07-18 if available.")
    parser.add_argument("--max-workers", type=int, default=18)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    base = Path(args.base_dir)
    out = Path(args.out_dir)
    copy_static_files(base, out)

    prices = pd.read_parquet(base / "us_market_daily.parquet")
    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.date.astype(str)
    symbols = sorted(prices["symbol"].dropna().astype(str).unique())
    start_ts = int(datetime.fromisoformat(args.start_date).replace(tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.fromisoformat(args.end_date).replace(tzinfo=timezone.utc).timestamp())

    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        future_map = {pool.submit(fetch_one, symbol, start_ts, end_ts, args.timeout): symbol for symbol in symbols}
        for future in as_completed(future_map):
            symbol, frame, error = future.result()
            done += 1
            if frame is not None:
                frames.append(frame)
            else:
                errors.append({"symbol": symbol, "error": error or "unknown"})
            if done % 50 == 0 or done == len(symbols):
                print(f"progress {done}/{len(symbols)} ok_symbols={len(frames)} errors={len(errors)}", flush=True)

    inc = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if inc.empty:
        raise RuntimeError("No Yahoo chart rows fetched")
    inc["trade_date"] = pd.to_datetime(inc["trade_date"]).dt.date.astype(str)

    combined = pd.concat([prices, inc], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(["symbol", "trade_date"], keep="last")
    combined = combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    combined.to_parquet(out / "us_market_daily.parquet", index=False)
    combined.to_csv(out / "us_market_daily.csv", index=False, encoding="utf-8")

    coverage = combined.groupby("trade_date")["symbol"].nunique().tail(12).reset_index()
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_raw_dir": str(base),
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
        "note": "Latest row can be intraday when updated before the US session close.",
    }
    (out / "manifest_intraday_update.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
