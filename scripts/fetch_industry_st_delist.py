#!/usr/bin/env python3
"""B2/B3 — fetch industry classification, current ST list, and delisted stocks (AkShare).

Outputs to data/akshare_meta/:
  industry.parquet   (stock_code, industry)         -- from Eastmoney industry boards
  st_current.parquet (stock_code, name, is_st)      -- CURRENT ST flag (see caveat)
  delisted.parquet   (stock_code, name, exchange)   -- delisted A-shares (survivorship)

CAVEAT (documented): the ST flag is CURRENT-only; akshare has no free full historical
ST timeline, so point-in-time ST is approximate. Industry is current classification.
Run AFTER the fundamentals fetch finishes to avoid network contention.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "akshare_meta"


def _norm(code) -> str:
    return str(code).zfill(6)


def fetch_industry() -> pd.DataFrame:
    boards = ak.stock_board_industry_name_em()
    rows = []
    names = boards["板块名称"].tolist()
    for i, name in enumerate(names):
        for attempt in range(3):
            try:
                cons = ak.stock_board_industry_cons_em(symbol=name)
                for code in cons["代码"].tolist():
                    rows.append({"stock_code": _norm(code), "industry": name})
                break
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        if (i + 1) % 20 == 0:
            print(f"  industry {i+1}/{len(names)} boards", flush=True)
    return pd.DataFrame(rows).drop_duplicates("stock_code")


def fetch_st() -> pd.DataFrame:
    spot = ak.stock_zh_a_spot_em()
    name_col = "名称" if "名称" in spot.columns else spot.columns[2]
    code_col = "代码" if "代码" in spot.columns else spot.columns[1]
    df = spot[[code_col, name_col]].rename(columns={code_col: "stock_code", name_col: "name"})
    df["stock_code"] = df["stock_code"].map(_norm)
    df["is_st"] = df["name"].str.contains("ST", case=False, na=False)
    return df


def fetch_delisted() -> pd.DataFrame:
    frames = []
    for fn, ex in [(ak.stock_info_sh_delist, "SH"), (ak.stock_info_sz_delist, "SZ")]:
        for attempt in range(3):
            try:
                d = fn()
                code_col = next((c for c in d.columns if "代码" in c), d.columns[0])
                name_col = next((c for c in d.columns if "简称" in c or "名称" in c), d.columns[1])
                frames.append(pd.DataFrame({
                    "stock_code": d[code_col].map(_norm),
                    "name": d[name_col], "exchange": ex,
                }))
                break
            except Exception as e:  # noqa: BLE001
                print(f"  delist {ex} retry: {str(e)[:60]}", flush=True)
                time.sleep(2.0 * (attempt + 1))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["stock_code", "name", "exchange"])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("[industry] fetching ...", flush=True)
    ind = fetch_industry()
    ind.to_parquet(OUT / "industry.parquet", index=False)
    print(f"[industry] {len(ind)} stocks mapped", flush=True)

    print("[st] fetching current ST ...", flush=True)
    st = fetch_st()
    st.to_parquet(OUT / "st_current.parquet", index=False)
    print(f"[st] {int(st['is_st'].sum())} ST of {len(st)} stocks", flush=True)

    print("[delisted] fetching ...", flush=True)
    de = fetch_delisted()
    de.to_parquet(OUT / "delisted.parquet", index=False)
    print(f"[delisted] {len(de)} delisted stocks", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
