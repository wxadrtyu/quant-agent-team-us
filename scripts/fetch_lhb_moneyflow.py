#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""归档龙虎榜 + 个股资金流向 (Tushare) 到 E:\\量化数据_tushare。

数据源 (均按 trade_date 全市场批量拉取, 每天1次API调用):
  - 20_龙虎榜       : pro.top_list(trade_date=day)   每日龙虎榜明细
  - 21_龙虎榜机构   : pro.top_inst(trade_date=day)   每日龙虎榜机构成交明细
  - 06_资金流向     : pro.moneyflow(trade_date=day)  每日个股资金流向

权限: top_list / top_inst / moneyflow 均需 2000 积分, 当前代理 15000 积分足够。
反封禁: 复用 tushare_client.call (0.7s 节流, ~85/min, 低于 100/min 上限) + 退避重试。
续传: 已存在 parquet 或 .empty 标记则跳过, 可中断重启。

用法:
  python scripts/fetch_lhb_moneyflow.py                 # 全量 20220104..20260701
  python scripts/fetch_lhb_moneyflow.py --probe         # 仅探测1天, 确认权限+字段
  python scripts/fetch_lhb_moneyflow.py --start 20220104 --end 20260701
  python scripts/fetch_lhb_moneyflow.py --what 龙虎榜   # 只拉龙虎榜
"""
from __future__ import annotations

import argparse
import json
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

DEFAULT_OUT = r"E:/量化数据_tushare"
# 严格遵守项目规则: 数据截止 2026-07-01, 7月2日及之后保留做样本外验证
DEFAULT_START = "20220104"
DEFAULT_END = "20260701"

# 数据集定义: (中文文件夹, 接口名)
DATASETS = [
    ("20_龙虎榜", "top_list"),
    ("21_龙虎榜机构", "top_inst"),
    ("06_资金流向", "moneyflow"),
]


def _save(df: pd.DataFrame, path: Path) -> int:
    """加 source 标签 + stock_code (如有 ts_code), 写 parquet。返回行数。"""
    df = df.copy()
    if "ts_code" in df.columns and "stock_code" not in df.columns:
        df["stock_code"] = df["ts_code"].map(ts_to_stock_code)
    df["source"] = SOURCE_TAG
    df.to_parquet(path, index=False)
    return len(df)


def _trade_days(pro, start: str, end: str) -> list[str]:
    cal = call(pro.trade_cal, exchange="SSE", start_date=start, end_date=end)
    return sorted(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str).tolist())


def probe_one(pro, endpoint: str, day: str) -> tuple[bool, str, pd.DataFrame | None]:
    """探测1天, 返回 (ok, error, df)。"""
    fn = getattr(pro, endpoint)
    try:
        df = call(lambda: fn(trade_date=day))
        return True, "", df
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200], None


def run_dataset(pro, root: Path, folder: str, endpoint: str, days: list[str]) -> dict:
    out = root / folder
    out.mkdir(parents=True, exist_ok=True)
    fn = getattr(pro, endpoint)
    fetched = empty = skipped = 0
    for i, day in enumerate(days):
        f = out / f"{day}.parquet"
        marker = out / f"{day}.empty"
        if f.exists() or marker.exists():
            skipped += 1
            continue
        try:
            df = call(lambda day=day: fn(trade_date=day))
        except Exception as exc:  # noqa: BLE001
            print(f"  [err] {folder} {day}: {str(exc)[:80]}")
            continue
        if df is None or df.empty:
            marker.touch()
            empty += 1
        else:
            _save(df, f)
            fetched += 1
        if (i + 1) % 100 == 0:
            print(f"  {folder}: {i + 1}/{len(days)} "
                  f"(fetched={fetched} empty={empty} skip={skipped})", flush=True)
    print(f"[ok] {folder} ({endpoint}): fetched={fetched} empty={empty} skip={skipped}")
    return {"folder": folder, "endpoint": endpoint,
            "fetched": fetched, "empty": empty, "skipped": skipped}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--probe", action="store_true", help="仅探测1天, 打印字段")
    ap.add_argument("--what", default="all",
                    help="all / 龙虎榜 / 资金流向 (默认 all)")
    args = ap.parse_args()

    pro = get_pro()
    days = _trade_days(pro, args.start, args.end)
    print(f"[plan] {args.start}..{args.end} 共 {len(days)} 个交易日")

    if args.probe:
        day = days[-1]
        for folder, ep in DATASETS:
            ok, err, df = probe_one(pro, ep, day)
            if not ok:
                print(f"[probe] {folder} ({ep}): DENIED - {err}")
                continue
            print(f"[probe] {folder} ({ep}) {day}: {len(df)} rows")
            print(f"  columns: {list(df.columns)}")
            if len(df) > 0:
                print(f"  sample:\n{df.head(2).to_string()}")
        return 0

    sel = DATASETS
    if args.what == "龙虎榜":
        sel = [d for d in DATASETS if "龙虎榜" in d[0]]
    elif args.what == "资金流向":
        sel = [d for d in DATASETS if "资金流向" in d[0]]

    results = []
    for folder, ep in sel:
        # 先探测权限
        ok, err, _ = probe_one(pro, ep, days[-1])
        if not ok:
            print(f"[skip] {folder} ({ep}): {err}")
            results.append({"folder": folder, "status": "denied", "error": err})
            continue
        results.append(run_dataset(pro, Path(args.out), folder, ep, days))

    print("\n[summary]")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
