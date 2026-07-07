#!/usr/bin/env python3
"""Fetch full-market A-share fundamentals from AkShare for value/quality factors.

- Valuation (daily): PE-TTM, PB via stock_zh_valuation_baidu -> data/akshare_fundamental/valuation/<code>.parquet
- ROE (quarterly): 净资产收益率 via stock_financial_analysis_indicator -> data/akshare_fundamental/roe/<code>.parquet

Resumable (skip existing), retries, per-stock failure log. Run in background.

Usage:
    python scripts/fetch_akshare_fundamentals.py --workers 8 [--limit N] [--codes 600519]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def fetch_valuation(code: str, out_dir: Path, retries: int = 3):
    dest = out_dir / f"{code}.parquet"
    if dest.exists():
        return "skip"
    for attempt in range(retries):
        try:
            pe = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="全部")
            pb = ak.stock_zh_valuation_baidu(symbol=code, indicator="市净率", period="全部")
            if pe is None or len(pe) == 0:
                return "empty"
            pe = pe.rename(columns={"value": "pe_ttm"})
            pb = pb.rename(columns={"value": "pb"})
            df = pe.merge(pb, on="date", how="outer").sort_values("date")
            df["stock_code"] = code
            df = df.rename(columns={"date": "trade_date"})
            df = df[df["trade_date"] >= pd.Timestamp("2022-01-01").date()]
            df.to_parquet(dest, index=False)
            return "ok"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}:{e}"
            time.sleep(1.5 * (attempt + 1))
    return f"fail:{last[:100]}"


def fetch_roe(code: str, out_dir: Path, retries: int = 3):
    dest = out_dir / f"{code}.parquet"
    if dest.exists():
        return "skip"
    for attempt in range(retries):
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2021")
            if df is None or len(df) == 0:
                return "empty"
            roe_cols = [c for c in df.columns if "净资产收益率" in c]
            growth = [c for c in df.columns if "净利润" in c and "同比" in c]
            keep = ["日期"] + roe_cols + growth
            out = df[[c for c in keep if c in df.columns]].copy()
            rename = {"日期": "report_date"}
            for c in roe_cols:
                rename[c] = "roe_weighted" if "加权" in c else "roe"
            for c in growth:
                rename[c] = "netprofit_yoy"
            out = out.rename(columns=rename)
            out["stock_code"] = code
            out.to_parquet(dest, index=False)
            return "ok"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}:{e}"
            time.sleep(1.5 * (attempt + 1))
    return f"fail:{last[:100]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--codes", default="")
    ap.add_argument("--universe", default="data/universe.json")
    ap.add_argument("--out", default="data/akshare_fundamental")
    ap.add_argument("--skip-roe", action="store_true",
                    help="valuation only; ROE is sourced separately from THS (fetch_roe_ths.py)")
    args = ap.parse_args()

    val_dir = (ROOT / args.out / "valuation").resolve()
    roe_dir = (ROOT / args.out / "roe").resolve()
    val_dir.mkdir(parents=True, exist_ok=True)
    roe_dir.mkdir(parents=True, exist_ok=True)

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        uni = json.loads((ROOT / args.universe).read_text(encoding="utf-8"))
        codes = [row["code"] if isinstance(row, dict) else str(row) for row in uni]
    if args.limit:
        codes = codes[: args.limit]

    total = len(codes)
    print(f"[start] fundamentals for {total} codes, workers={args.workers}", flush=True)
    t0 = time.time()

    def work(code):
        rs = "skip" if args.skip_roe else fetch_roe(code, roe_dir)
        return code, fetch_valuation(code, val_dir), rs

    done = val_ok = roe_ok = 0
    val_fail, roe_fail = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(work, c) for c in codes]):
            code, vs, rs = fut.result()
            done += 1
            if vs == "ok":
                val_ok += 1
            elif vs.startswith("fail") or vs == "empty":
                val_fail.append(f"{code}\t{vs}")
            if rs == "ok":
                roe_ok += 1
            elif rs.startswith("fail") or rs == "empty":
                roe_fail.append(f"{code}\t{rs}")
            if done % 100 == 0 or done == total:
                el = time.time() - t0
                eta = (total - done) / (done / el) / 60 if done else 0
                print(f"[{done}/{total}] val_ok={val_ok} roe_ok={roe_ok} "
                      f"val_fail={len(val_fail)} roe_fail={len(roe_fail)} eta={eta:.1f}min", flush=True)

    if val_fail:
        (val_dir / "_failures.txt").write_text("\n".join(val_fail), encoding="utf-8")
    if roe_fail:
        (roe_dir / "_failures.txt").write_text("\n".join(roe_fail), encoding="utf-8")
    print(f"[done] val_ok={val_ok} roe_ok={roe_ok} val_fail={len(val_fail)} "
          f"roe_fail={len(roe_fail)} in {(time.time()-t0)/60:.1f}min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
