#!/usr/bin/env python3
"""Fetch full-market A-share daily history from AkShare (Eastmoney) into per-stock parquet.

Source of truth replacement for the dead Baostock service. Pulls hfq (后复权) adjusted
daily bars so stored prices are drift-stable and corporate-action gaps are removed.

Resumable: skips codes whose output parquet already exists. Failures are appended to
_failures.txt for a later retry pass.

Usage:
    python scripts/fetch_akshare_history.py --start 20220101 --end 20261231 \
        --out data/akshare_hfq --workers 8 [--limit N] [--codes 600519,000001]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import akshare as ak

ROOT = Path(__file__).resolve().parents[1]

COLMAP = {
    "日期": "trade_date",
    "股票代码": "stock_code",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_chg",
    "涨跌额": "change",
    "换手率": "turnover_rate",
}


def fetch_one(code: str, start: str, end: str, adjust: str, out_dir: Path, retries: int = 3):
    dest = out_dir / f"{code}.parquet"
    if dest.exists():
        return code, "skip", 0
    last_err = ""
    for attempt in range(retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start, end_date=end, adjust=adjust,
            )
            if df is None or len(df) == 0:
                return code, "empty", 0
            df = df.rename(columns=COLMAP)
            if "stock_code" not in df.columns:
                df.insert(1, "stock_code", code)
            df.to_parquet(dest, index=False)
            return code, "ok", len(df)
        except Exception as e:  # noqa: BLE001 - log and retry
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    return code, f"fail:{last_err[:120]}", 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20220101")
    ap.add_argument("--end", default="20261231")
    ap.add_argument("--adjust", default="hfq", choices=["hfq", "qfq", ""])
    ap.add_argument("--out", default="data/akshare_hfq")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--codes", default="")
    ap.add_argument("--universe", default="data/universe.json")
    args = ap.parse_args()

    out_dir = (ROOT / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        uni = json.loads((ROOT / args.universe).read_text(encoding="utf-8"))
        codes = [row["code"] if isinstance(row, dict) else str(row) for row in uni]
    if args.limit:
        codes = codes[: args.limit]

    total = len(codes)
    print(f"[start] {total} codes  range={args.start}..{args.end}  adjust={args.adjust}  "
          f"workers={args.workers}  out={out_dir}", flush=True)

    t0 = time.time()
    done = ok = skipped = empty = failed = rows = 0
    fail_log = out_dir / "_failures.txt"
    failures = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_one, c, args.start, args.end, args.adjust, out_dir): c for c in codes}
        for fut in as_completed(futs):
            code, status, n = fut.result()
            done += 1
            if status == "ok":
                ok += 1; rows += n
            elif status == "skip":
                skipped += 1
            elif status == "empty":
                empty += 1
            else:
                failed += 1
                failures.append(f"{code}\t{status}")
            if done % 100 == 0 or done == total:
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (total - done) / rate if rate else 0
                print(f"[{done}/{total}] ok={ok} skip={skipped} empty={empty} fail={failed} "
                      f"rows={rows:,} {rate:.1f}/s eta={eta/60:.1f}min", flush=True)

    if failures:
        fail_log.write_text("\n".join(failures), encoding="utf-8")
    print(f"[done] ok={ok} skip={skipped} empty={empty} fail={failed} rows={rows:,} "
          f"in {(time.time()-t0)/60:.1f}min  failures->{fail_log if failures else 'none'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
