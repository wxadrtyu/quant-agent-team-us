from __future__ import annotations

import argparse
import io
import json
from datetime import timezone
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&d1={start}&d2={end}&i=d"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={period1}&period2={period2}&interval=1d&events=history"


def stooq_symbol(symbol: str) -> str:
    return f"{str(symbol).strip().lower().replace('.', '-')}.us"


def yahoo_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def normalize_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    rename = {c: str(c).strip().lower() for c in out.columns}
    out = out.rename(columns=rename)
    if "date" in out.columns and "trade_date" not in out.columns:
        out = out.rename(columns={"date": "trade_date"})
    required = ["trade_date", "open", "close"]
    missing = [col for col in required if col not in out.columns]
    if missing:
        return pd.DataFrame(columns=required)
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.normalize()
    out["open"] = pd.to_numeric(out["open"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=required)
    return out[required].drop_duplicates("trade_date").sort_values("trade_date")


def compare_price_frames(symbol: str, local: pd.DataFrame, external: pd.DataFrame, tolerance: float = 0.03) -> dict:
    local_norm = normalize_price_frame(local)
    external_norm = normalize_price_frame(external)
    if external_norm.empty:
        return {
            "symbol": symbol,
            "status": "missing_external",
            "overlap_days": 0,
            "max_open_diff_pct": np.nan,
            "max_close_diff_pct": np.nan,
        }
    merged = local_norm.merge(external_norm, on="trade_date", suffixes=("_local", "_external"))
    if merged.empty:
        return {
            "symbol": symbol,
            "status": "no_overlap",
            "overlap_days": 0,
            "max_open_diff_pct": np.nan,
            "max_close_diff_pct": np.nan,
        }
    open_diff = ((merged["open_local"] - merged["open_external"]).abs() / merged["open_external"].replace(0, np.nan)).max()
    close_diff = ((merged["close_local"] - merged["close_external"]).abs() / merged["close_external"].replace(0, np.nan)).max()
    max_open = float(open_diff) if np.isfinite(open_diff) else np.nan
    max_close = float(close_diff) if np.isfinite(close_diff) else np.nan
    status = "ok" if max(max_open, max_close) <= tolerance else "mismatch"
    return {
        "symbol": symbol,
        "status": status,
        "overlap_days": int(len(merged)),
        "first_overlap": merged["trade_date"].min().date().isoformat(),
        "last_overlap": merged["trade_date"].max().date().isoformat(),
        "max_open_diff_pct": max_open,
        "max_close_diff_pct": max_close,
    }


def fetch_stooq_prices(symbol: str, start: str, end: str, timeout: int = 20) -> pd.DataFrame:
    url = STOOQ_URL.format(symbol=stooq_symbol(symbol), start=start.replace("-", ""), end=end.replace("-", ""))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read().decode("utf-8", errors="replace")
    except Exception:
        return pd.DataFrame()
    if not content.strip() or content.strip().lower() == "no data":
        return pd.DataFrame()
    try:
        frame = pd.read_csv(io.StringIO(content))
    except Exception:
        return pd.DataFrame()
    return normalize_price_frame(frame)


def fetch_yahoo_prices(symbol: str, start: str, end: str, timeout: int = 20) -> pd.DataFrame:
    start_ts = int(pd.Timestamp(start).tz_localize(timezone.utc).timestamp())
    end_ts = int((pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize(timezone.utc).timestamp())
    url = YAHOO_CHART_URL.format(symbol=yahoo_symbol(symbol), period1=start_ts, period2=end_ts)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return pd.DataFrame()
    result = payload.get("chart", {}).get("result") or []
    if not result:
        return pd.DataFrame()
    timestamps = result[0].get("timestamp") or []
    quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    if not timestamps or not quote:
        return pd.DataFrame()
    frame = pd.DataFrame(
        {
            "trade_date": [pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York").date().isoformat() for ts in timestamps],
            "open": quote.get("open", []),
            "close": quote.get("close", []),
        }
    )
    return normalize_price_frame(frame)


def load_local_prices(raw_dir: Path, symbols: list[str], start: str, end: str) -> pd.DataFrame:
    path = raw_dir / "us_market_daily.parquet"
    frame = pd.read_parquet(path, columns=["symbol", "trade_date", "open", "close"])
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return frame[
        frame["symbol"].isin(symbols)
        & (frame["trade_date"] >= start_ts)
        & (frame["trade_date"] <= end_ts)
    ].copy()


def symbols_from_signals(path: Path) -> list[str]:
    signals = pd.read_csv(path)
    return sorted(signals["symbol"].dropna().astype(str).unique())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
    parser.add_argument("--signals", default=r"G:\quant-agent-team-us\reports\us\export\paper_live_pool_latest_signals_20260712.csv")
    parser.add_argument("--out-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-price-crosscheck")
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-07-10")
    parser.add_argument("--tolerance", type=float, default=0.03)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--source", choices=["yahoo", "stooq"], default="yahoo")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = symbols_from_signals(Path(args.signals))
    local = load_local_prices(Path(args.raw_dir), symbols, args.start, args.end)
    rows = []
    for symbol in symbols:
        local_symbol = local[local["symbol"] == symbol]
        if args.source == "yahoo":
            external = fetch_yahoo_prices(symbol, args.start, args.end, timeout=args.timeout)
        else:
            external = fetch_stooq_prices(symbol, args.start, args.end, timeout=args.timeout)
        rows.append(compare_price_frames(symbol, local_symbol, external, tolerance=args.tolerance))
    results = pd.DataFrame(rows).sort_values(["status", "symbol"])
    results.to_csv(out_dir / "price_crosscheck_summary.csv", index=False)
    status_counts = results["status"].value_counts().to_dict() if not results.empty else {}
    manifest = {
        "raw_dir": args.raw_dir,
        "signals": args.signals,
        "source": args.source,
        "start": args.start,
        "end": args.end,
        "tolerance": args.tolerance,
        "symbols": len(symbols),
        "status_counts": status_counts,
        "note": "ok means local Nasdaq OHLC agrees with the selected external source within tolerance on overlapping dates; missing/no_overlap blocks active monitoring promotion but does not invalidate strategy research.",
    }
    (out_dir / "price_crosscheck_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(results.head(80).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
