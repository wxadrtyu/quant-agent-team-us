#!/usr/bin/env python3
"""ROE source — THS (同花顺) financial abstract. Backup/replacement for slow sina ROE.

Different provider (not baidu/eastmoney/sina), ~4s/stock, gives annual ROE history. Used
as the SINGLE source for the ROE/quality factor (no cross-source mixing).

Look-ahead safety: annual ROE for fiscal year Y is only published by ~Apr 30 of Y+1, so
the row's effective `report_date` is set to (Y+1)-04-30, NOT the fiscal year-end. Downstream
ASOF joins then never use an unpublished number.

Output: data/akshare_roe_ths/<code>.parquet (stock_code, report_date, roe, source='ths').
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

socket.setdefaulttimeout(30)

import akshare as ak  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "akshare_roe_ths"


def _effective_date(period: str):
    """Map a THS 报告期 to a publication-safe effective date (no look-ahead)."""
    s = str(period).strip()
    if len(s) == 4 and s.isdigit():       # annual, e.g. '2022' -> published by 2023-04-30
        return date(int(s) + 1, 4, 30)
    # fall back: parse YYYY-MM-DD-ish and add ~4 months as a safety lag
    try:
        d = pd.to_datetime(s).date()
        return (pd.Timestamp(d) + pd.DateOffset(months=4)).date()
    except Exception:
        return None


def fetch_one(code: str, retries: int = 4):
    dest = OUT / f"{code}.parquet"
    if dest.exists():
        return code, "skip"
    for attempt in range(retries):
        try:
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="主要指标")
            if df is None or len(df) == 0:
                return code, "empty"
            period_col = df.columns[0]
            roe_col = next((c for c in df.columns if c == "净资产收益率"), None)
            if roe_col is None:
                return code, "no_roe_col"
            rows = []
            for _, r in df.iterrows():
                eff = _effective_date(r[period_col])
                val = str(r[roe_col]).replace("%", "").strip()
                try:
                    roe = float(val)
                except ValueError:
                    continue
                if eff is not None:
                    rows.append({"stock_code": code, "report_date": eff, "roe": roe, "source": "ths"})
            if not rows:
                return code, "empty"
            pd.DataFrame(rows).to_parquet(dest, index=False)
            return code, "ok"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}"
            time.sleep(2.0 * (attempt + 1))
    return code, f"fail:{last}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--codes", default="")
    ap.add_argument("--universe", default="data/universe.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        uni = json.loads((ROOT / args.universe).read_text(encoding="utf-8"))
        codes = [row["code"] if isinstance(row, dict) else str(row) for row in uni]
    if args.limit:
        codes = codes[: args.limit]

    total = len(codes)
    print(f"[start] THS ROE for {total} codes, workers={args.workers}", flush=True)
    t0 = time.time()
    done = ok = 0
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(fetch_one, c) for c in codes]):
            code, status = fut.result()
            done += 1
            if status == "ok":
                ok += 1
            elif status.startswith("fail") or status in ("empty", "no_roe_col"):
                failures.append(f"{code}\t{status}")
            if done % 200 == 0 or done == total:
                el = time.time() - t0
                eta = (total - done) / (done / el) / 60 if done else 0
                print(f"[{done}/{total}] ok={ok} fail={len(failures)} eta={eta:.1f}min", flush=True)
    if failures:
        (OUT / "_failures.txt").write_text("\n".join(failures), encoding="utf-8")
    print(f"[done] ok={ok} fail={len(failures)} in {(time.time()-t0)/60:.1f}min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
