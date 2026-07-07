#!/usr/bin/env python3
"""Fetch A-share data from Tushare Pro (proxy plan) into resumable parquet.

Usage:
    python scripts/fetch_tushare.py --what constituents
    python scripts/fetch_tushare.py --what roe
    python scripts/fetch_tushare.py --what meta
    python scripts/fetch_tushare.py --what valuation [--start 20220101 --end 20260630]

Design (per the plan's config doc: 100 calls/min, "fetch as much as possible per
call, never loop per-stock-per-day"):
  - constituents : index_weight, per index per MONTH (single call caps at 7000 rows,
                   CSI1000 is ~2 snapshots x 1000/mo, so monthly stays safe).
  - valuation    : daily_basic, ONE call per trade day = whole market that day.
  - roe          : fina_indicator_vip, ONE call per quarter = whole market that quarter.
  - meta         : stock_basic L (industry/list) + D (delisted, survivorship fix).

All output is parquet under data/tushare/<what>/, resumable (existing files skipped),
tagged source="tushare". Ingest into duckdb is a separate step (ingest_tushare.py).
"""
from __future__ import annotations

import argparse
import calendar
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_agent_team.tushare_client import (  # noqa: E402
    SOURCE_TAG,
    call,
    get_pro,
    ts_to_stock_code,
)

OUT = ROOT / "data" / "tushare"

# universe name -> tushare index_code
INDEXES = {
    "hs300": "000300.SH",
    "zz500": "000905.SH",
    "zz1000": "000852.SH",
    "kc100": "000698.SH",
    "bj50": "899050.BJ",
}

DAILY_BASIC_FIELDS = (
    "ts_code,trade_date,pe,pe_ttm,pb,ps,ps_ttm,total_mv,circ_mv,"
    "turnover_rate,turnover_rate_f,dv_ratio,dv_ttm"
)
FINA_FIELDS = "ts_code,end_date,roe,roe_dt,roe_waa,netprofit_yoy,grossprofit_margin"


def _months(start: str, end: str):
    y, m = int(start[:4]), int(start[4:6])
    ey, em = int(end[:4]), int(end[4:6])
    while (y, m) <= (ey, em):
        last = calendar.monthrange(y, m)[1]
        yield f"{y}{m:02d}01", f"{y}{m:02d}{last:02d}"
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _quarter_ends(start: str, end: str):
    ends = ["0331", "0630", "0930", "1231"]
    for year in range(int(start[:4]), int(end[:4]) + 1):
        for e in ends:
            p = f"{year}{e}"
            if start <= p <= end:
                yield p


def fetch_constituents(start: str, end: str) -> None:
    out = OUT / "constituents"
    out.mkdir(parents=True, exist_ok=True)
    pro = get_pro()
    for uni, code in INDEXES.items():
        f = out / f"{uni}.parquet"
        if f.exists():
            print(f"[skip] {uni} ({f.name} exists)")
            continue
        frames = []
        for ms, me in _months(start, end):
            df = call(pro.index_weight, index_code=code, start_date=ms, end_date=me)
            if df is not None and not df.empty:
                frames.append(df)
        if not frames:
            print(f"[warn] {uni}: no data {start}-{end}")
            continue
        all_df = pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["con_code", "trade_date"]
        )
        all_df["universe"] = uni
        all_df["stock_code"] = all_df["con_code"].map(ts_to_stock_code)
        all_df["source"] = SOURCE_TAG
        all_df.to_parquet(f, index=False)
        ndates = all_df["trade_date"].nunique()
        print(f"[ok] {uni}: {len(all_df)} rows, {ndates} snapshots -> {f.name}")


def fetch_valuation(start: str, end: str) -> None:
    out = OUT / "valuation"
    out.mkdir(parents=True, exist_ok=True)
    pro = get_pro()
    cal = call(pro.trade_cal, exchange="SSE", start_date=start, end_date=end)
    days = sorted(cal.loc[cal["is_open"] == 1, "cal_date"].tolist())
    print(f"[valuation] {len(days)} trade days {start}-{end}")
    done = 0
    for i, day in enumerate(days):
        f = out / f"{day}.parquet"
        if f.exists():
            continue
        df = call(pro.daily_basic, trade_date=day, fields=DAILY_BASIC_FIELDS)
        if df is None or df.empty:
            continue
        df["stock_code"] = df["ts_code"].map(ts_to_stock_code)
        df["source"] = SOURCE_TAG
        df.to_parquet(f, index=False)
        done += 1
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(days)} days ({done} fetched this run)")
    print(f"[ok] valuation: {done} new day-files")


def fetch_roe(start: str, end: str) -> None:
    out = OUT / "roe"
    out.mkdir(parents=True, exist_ok=True)
    pro = get_pro()
    for p in _quarter_ends(start, end):
        f = out / f"{p}.parquet"
        if f.exists():
            print(f"[skip] roe {p}")
            continue
        df = call(pro.fina_indicator_vip, period=p, fields=FINA_FIELDS)
        if df is None or df.empty:
            print(f"[warn] roe {p}: empty")
            continue
        df["stock_code"] = df["ts_code"].map(ts_to_stock_code)
        df["report_date"] = df["end_date"]
        df["source"] = SOURCE_TAG
        df.to_parquet(f, index=False)
        print(f"[ok] roe {p}: {len(df)} rows")


def fetch_missing_prices(start: str, end: str) -> None:
    """Backfill qfq daily history for constituents missing from market_daily
    (delisted/dropped names -> closes survivorship bias). Reads the code list
    written by the verification query: data/tushare/missing_constituents.csv.

    pro_bar is a module-level fn -> must pass api=pro (proxy plan requirement).
    Unit fixes to match market_daily: amount 千元->元 (x1000); vol already 手.
    """
    import tushare as ts

    csv = ROOT / "data" / "tushare" / "missing_constituents.csv"
    if not csv.exists():
        print(f"[err] {csv} missing; run the verification query first")
        return
    miss = pd.read_csv(csv, dtype=str)
    out = OUT / "missing_prices"
    out.mkdir(parents=True, exist_ok=True)
    pro = get_pro()
    done = empty = 0
    for i, row in miss.iterrows():
        sc, tc = row["stock_code"], row["ts_code"]
        f = out / f"{sc}.parquet"
        if f.exists():
            continue
        df = call(ts.pro_bar, ts_code=tc, api=pro, adj="qfq",
                  start_date=start, end_date=end)
        if df is None or df.empty:
            f.write_bytes(b"")  # empty marker -> resumable, won't refetch
            empty += 1
            continue
        df = df.sort_values("trade_date")
        norm = pd.DataFrame({
            "stock_code": sc,
            "trade_date": df["trade_date"],
            "open": df["open"], "high": df["high"], "low": df["low"],
            "close_adj": df["close"],
            "volume": df["vol"],
            "amount": df["amount"] * 1000.0,
            "amplitude": (df["high"] - df["low"]) / df["pre_close"].replace(0, pd.NA) * 100.0,
            "pct_chg": df["pct_chg"], "change": df["change"],
            "turnover_rate": pd.NA,
            "source": SOURCE_TAG,
        })
        norm.to_parquet(f, index=False)
        done += 1
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(miss)} ({done} filled, {empty} empty)")
    print(f"[ok] missing_prices: {done} filled, {empty} empty-of {len(miss)}")


def fetch_meta() -> None:
    out = OUT / "meta"
    out.mkdir(parents=True, exist_ok=True)
    pro = get_pro()
    listed = call(
        pro.stock_basic, exchange="", list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    listed["stock_code"] = listed["ts_code"].map(ts_to_stock_code)
    listed["source"] = SOURCE_TAG
    listed.to_parquet(out / "stock_basic_L.parquet", index=False)
    print(f"[ok] meta listed: {len(listed)} rows")

    delisted = call(
        pro.stock_basic, exchange="", list_status="D",
        fields="ts_code,symbol,name,industry,market,list_date,delist_date",
    )
    delisted["stock_code"] = delisted["ts_code"].map(ts_to_stock_code)
    delisted["source"] = SOURCE_TAG
    delisted.to_parquet(out / "stock_basic_D.parquet", index=False)
    print(f"[ok] meta delisted: {len(delisted)} rows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--what", required=True,
        choices=["constituents", "valuation", "roe", "meta", "missing_prices"],
    )
    ap.add_argument("--start", default="20220101")
    ap.add_argument("--end", default="20260630")
    args = ap.parse_args()

    if args.what == "constituents":
        fetch_constituents(args.start, args.end)
    elif args.what == "valuation":
        fetch_valuation(args.start, args.end)
    elif args.what == "roe":
        fetch_roe(args.start, args.end)
    elif args.what == "missing_prices":
        fetch_missing_prices(args.start, args.end)
    elif args.what == "meta":
        fetch_meta()


if __name__ == "__main__":
    main()
