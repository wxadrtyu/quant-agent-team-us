#!/usr/bin/env python3
"""Backup valuation source — Eastmoney bulk spot snapshot (current PE/PB, full market).

Different provider from baidu (which throttles after ~1800 per-stock calls), and bulk:
each board returns ALL its stocks' current PE/PB in one (paginated) call, so it cannot
be per-stock throttled. CURRENT-only (one snapshot) — used as a guaranteed full-market
valuation floor so the value factor is never blocked by a single source's rate limit.

Output: data/akshare_meta/valuation_snapshot.parquet (stock_code, pe_ttm, pb, snapshot_source).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "akshare_meta"

BOARDS = {
    "sh": ak.stock_sh_a_spot_em,
    "sz": ak.stock_sz_a_spot_em,
    "cy": ak.stock_cy_a_spot_em,
    "kc": ak.stock_kc_a_spot_em,
    "bj": ak.stock_bj_a_spot_em,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, fn in BOARDS.items():
        for attempt in range(3):
            try:
                t = time.time()
                df = fn()
                code_col = next(c for c in df.columns if c == "代码")
                pe_col = next((c for c in df.columns if "市盈" in c), None)
                pb_col = next((c for c in df.columns if "市净" in c), None)
                sub = pd.DataFrame({
                    "stock_code": df[code_col].astype(str).str.zfill(6),
                    "pe_ttm": pd.to_numeric(df[pe_col], errors="coerce") if pe_col else None,
                    "pb": pd.to_numeric(df[pb_col], errors="coerce") if pb_col else None,
                })
                frames.append(sub)
                print(f"[{name}] {len(sub)} stocks in {time.time()-t:.1f}s", flush=True)
                break
            except Exception as e:  # noqa: BLE001
                print(f"[{name}] retry: {str(e)[:60]}", flush=True)
                time.sleep(3.0 * (attempt + 1))
    if not frames:
        print("[error] no boards fetched", flush=True)
        return 1
    out = pd.concat(frames, ignore_index=True).drop_duplicates("stock_code")
    out["snapshot_source"] = "eastmoney_spot"
    out.to_parquet(OUT / "valuation_snapshot.parquet", index=False)
    print(f"[done] {len(out)} stocks -> valuation_snapshot.parquet", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
