#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bulk-archive every accessible A-share Tushare dataset to E:\\量化数据_tushare.

Standalone from the duckdb pipeline (scripts/fetch_tushare.py). This writes a
self-describing raw archive: one Chinese-named folder per dataset, last 5 years
(default 2021-06-28 .. 2026-06-28), every parquet tagged source="tushare".

Anti-ban: there is NO IP faking here on purpose. Tushare throttles/bans by token
(积分), not client IP, and a spoofed source IP can't complete the HTTPS handshake
anyway. The real, sufficient mechanism is the shared throttle()/call() in
quant_agent_team.tushare_client (0.7s spacing -> ~85/min under the 100/min cap,
backoff retry) plus "fetch max per call" batching (one call = whole market for a
trade-date / quarter). See the approved plan for the full rationale.

Usage:
    python scripts/fetch_tushare_archive.py --what all
    python scripts/fetch_tushare_archive.py --what 03_日线行情
    python scripts/fetch_tushare_archive.py --what verify
    python scripts/fetch_tushare_archive.py --what all --start 20210628 --end 20260628 --out "E:/量化数据_tushare"

Resumable: existing non-empty parquet is skipped; a sibling ``<key>.empty`` marker
records a known-empty result so it is not refetched. Safe to stop/restart.
"""
from __future__ import annotations

import argparse
import calendar
import os
import sys
import traceback
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

DEFAULT_OUT = os.environ.get("TUSHARE_ARCHIVE_DIR", r"E:/量化数据_tushare")

# ---- dataset catalog -------------------------------------------------------
# Per-trade-date datasets: 1 call(trade_date=day) == whole market that day.
PER_DATE = [
    ("03_日线行情", "daily"),
    ("04_复权因子", "adj_factor"),
    ("05_每日指标", "daily_basic"),
    ("06_资金流向", "moneyflow"),
    ("07_停复牌", "suspend_d"),
    ("08_涨跌停价格", "stk_limit"),
]

# Per-quarter datasets: 1 call(period=YYYYMMDD) == whole market that quarter.
PER_PERIOD = [
    ("09_利润表", "income_vip"),
    ("10_资产负债表", "balancesheet_vip"),
    ("11_现金流量表", "cashflow_vip"),
    ("12_财务指标", "fina_indicator_vip"),
    ("13_业绩预告", "forecast_vip"),
    ("14_业绩快报", "express_vip"),
]

# index_daily targets: ts_code -> Chinese label (for manifest only)
INDEXES = {
    "000300.SH": "沪深300",
    "000905.SH": "中证500",
    "000852.SH": "中证1000",
    "000016.SH": "上证50",
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000688.SH": "科创50",
}
# index_weight universes (matches fetch_tushare.py INDEXES)
WEIGHT_INDEXES = {
    "hs300": "000300.SH",
    "zz500": "000905.SH",
    "zz1000": "000852.SH",
    "kc100": "000698.SH",
    "bj50": "899050.BJ",
}

ALL_KEYS = (
    ["01_股票列表", "02_交易日历"]
    + [f for f, _ in PER_DATE]
    + [f for f, _ in PER_PERIOD]
    + ["15_分红送股", "16_指数日线", "17_指数成分与权重", "18_股票曾用名", "19_上市公司基本信息"]
)


# ---- helpers ---------------------------------------------------------------
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
    for year in range(int(start[:4]), int(end[:4]) + 1):
        for e in ("0331", "0630", "0930", "1231"):
            p = f"{year}{e}"
            if start <= p <= end:
                yield p


def _save(df: pd.DataFrame, path: Path) -> int:
    """Tag source (+ stock_code if ts_code present) and write parquet. Returns rows."""
    df = df.copy()
    if "ts_code" in df.columns and "stock_code" not in df.columns:
        df["stock_code"] = df["ts_code"].map(ts_to_stock_code)
    df["source"] = SOURCE_TAG
    df.to_parquet(path, index=False)
    return len(df)


def _trade_days(pro, start: str, end: str) -> list[str]:
    cal = call(pro.trade_cal, exchange="SSE", start_date=start, end_date=end)
    return sorted(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str).tolist())


def _probe(pro, endpoint: str, **kwargs) -> tuple[bool, str]:
    """Probe one call to detect permission/availability before a long loop."""
    fn = getattr(pro, endpoint)
    try:
        call(lambda: fn(**kwargs), retries=1)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]


# ---- per-granularity runners ----------------------------------------------
def run_per_date(pro, root: Path, folder: str, endpoint: str, days: list[str]) -> dict:
    out = root / folder
    out.mkdir(parents=True, exist_ok=True)
    fn = getattr(pro, endpoint)
    ok, err = _probe(pro, endpoint, trade_date=days[-1])
    if not ok:
        print(f"[skip] {folder} ({endpoint}): {err}")
        return {"folder": folder, "endpoint": endpoint, "status": "denied", "error": err}
    fetched = empty = 0
    for i, day in enumerate(days):
        f = out / f"{day}.parquet"
        marker = out / f"{day}.empty"
        if f.exists() or marker.exists():
            continue
        try:
            df = call(lambda day=day: fn(trade_date=day))
        except Exception as exc:  # noqa: BLE001 - log and continue, resumable
            print(f"  [err] {folder} {day}: {str(exc)[:80]}")
            continue
        if df is None or df.empty:
            marker.touch()
            empty += 1
        else:
            _save(df, f)
            fetched += 1
        if (i + 1) % 100 == 0:
            print(f"  {folder}: {i + 1}/{len(days)} ({fetched} fetched, {empty} empty this run)")
    print(f"[ok] {folder} ({endpoint}): {fetched} new files, {empty} empty")
    return {"folder": folder, "endpoint": endpoint, "status": "ok",
            "new_files": fetched, "empty": empty}


def run_per_period(pro, root: Path, folder: str, endpoint: str,
                   start: str, end: str) -> dict:
    out = root / folder
    out.mkdir(parents=True, exist_ok=True)
    periods = list(_quarter_ends(start, end))
    fn = getattr(pro, endpoint)
    ok, err = _probe(pro, endpoint, period=periods[-1])
    if not ok:
        print(f"[skip] {folder} ({endpoint}): {err}")
        return {"folder": folder, "endpoint": endpoint, "status": "denied", "error": err}
    fetched = empty = 0
    for p in periods:
        f = out / f"{p}.parquet"
        marker = out / f"{p}.empty"
        if f.exists() or marker.exists():
            continue
        try:
            df = call(lambda p=p: fn(period=p))
        except Exception as exc:  # noqa: BLE001
            print(f"  [err] {folder} {p}: {str(exc)[:80]}")
            continue
        if df is None or df.empty:
            marker.touch()
            empty += 1
        else:
            n = _save(df, f)
            fetched += 1
            print(f"  [ok] {folder} {p}: {n} rows")
    print(f"[ok] {folder} ({endpoint}): {fetched} periods, {empty} empty")
    return {"folder": folder, "endpoint": endpoint, "status": "ok",
            "new_files": fetched, "empty": empty}


# ---- one-shot datasets -----------------------------------------------------
def run_stock_list(pro, root: Path) -> dict:
    out = root / "01_股票列表"
    out.mkdir(parents=True, exist_ok=True)
    specs = {
        "L_上市.parquet": dict(list_status="L",
            fields="ts_code,symbol,name,area,industry,fullname,market,exchange,curr_type,list_status,list_date,is_hs"),
        "D_退市.parquet": dict(list_status="D",
            fields="ts_code,symbol,name,area,industry,market,exchange,list_date,delist_date"),
        "P_暂停上市.parquet": dict(list_status="P",
            fields="ts_code,symbol,name,area,industry,market,exchange,list_date"),
    }
    counts = {}
    for fname, kw in specs.items():
        df = call(pro.stock_basic, exchange="", **kw)
        counts[fname] = _save(df, out / fname) if df is not None and not df.empty else 0
        print(f"[ok] 01_股票列表/{fname}: {counts[fname]} rows")
    return {"folder": "01_股票列表", "endpoint": "stock_basic", "status": "ok", **counts}


def run_trade_cal(pro, root: Path, start: str, end: str) -> dict:
    out = root / "02_交易日历"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for ex in ("SSE", "SZSE"):
        df = call(pro.trade_cal, exchange=ex, start_date=start, end_date=end)
        if df is not None and not df.empty:
            n += _save(df, out / f"{ex}.parquet")
    print(f"[ok] 02_交易日历: {n} rows (SSE+SZSE)")
    return {"folder": "02_交易日历", "endpoint": "trade_cal", "status": "ok", "rows": n}


def run_dividend(pro, root: Path, days: list[str]) -> dict:
    out = root / "15_分红送股"
    out.mkdir(parents=True, exist_ok=True)
    ok, err = _probe(pro, "dividend", ann_date=days[-1])
    if not ok:
        print(f"[skip] 15_分红送股 (dividend): {err}")
        return {"folder": "15_分红送股", "endpoint": "dividend", "status": "denied", "error": err}
    fetched = empty = 0
    for i, day in enumerate(days):
        f = out / f"{day}.parquet"
        marker = out / f"{day}.empty"
        if f.exists() or marker.exists():
            continue
        try:
            df = call(lambda day=day: pro.dividend(ann_date=day))
        except Exception as exc:  # noqa: BLE001
            print(f"  [err] dividend {day}: {str(exc)[:80]}")
            continue
        if df is None or df.empty:
            marker.touch()
            empty += 1
        else:
            _save(df, f)
            fetched += 1
        if (i + 1) % 100 == 0:
            print(f"  15_分红送股: {i + 1}/{len(days)} ({fetched} fetched)")
    print(f"[ok] 15_分红送股 (dividend, by ann_date): {fetched} files, {empty} empty")
    return {"folder": "15_分红送股", "endpoint": "dividend", "status": "ok",
            "new_files": fetched, "empty": empty}


def run_index_daily(pro, root: Path, start: str, end: str) -> dict:
    out = root / "16_指数日线"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for code, label in INDEXES.items():
        f = out / f"{code.replace('.', '_')}_{label}.parquet"
        if f.exists():
            continue
        try:
            df = call(pro.index_daily, ts_code=code, start_date=start, end_date=end)
        except Exception as exc:  # noqa: BLE001
            print(f"  [err] index_daily {code}: {str(exc)[:80]}")
            continue
        if df is not None and not df.empty:
            n += _save(df, f)
            print(f"[ok] 16_指数日线/{f.name}: {len(df)} rows")
    return {"folder": "16_指数日线", "endpoint": "index_daily", "status": "ok", "rows": n}


def run_index_weight(pro, root: Path, start: str, end: str) -> dict:
    out = root / "17_指数成分与权重"
    out.mkdir(parents=True, exist_ok=True)
    # index_basic catalog (one-shot per market)
    cat_frames = []
    for mkt in ("SSE", "SZSE", "CSI"):
        try:
            df = call(pro.index_basic, market=mkt)
            if df is not None and not df.empty:
                cat_frames.append(df)
        except Exception:  # noqa: BLE001
            pass
    if cat_frames:
        _save(pd.concat(cat_frames, ignore_index=True), out / "_指数基本信息.parquet")
    # per-index monthly weights
    total = 0
    for uni, code in WEIGHT_INDEXES.items():
        f = out / f"{uni}_{code.replace('.', '_')}.parquet"
        if f.exists():
            print(f"[skip] 17_指数成分与权重/{uni}")
            continue
        frames = []
        for ms, me in _months(start, end):
            try:
                df = call(pro.index_weight, index_code=code, start_date=ms, end_date=me)
            except Exception as exc:  # noqa: BLE001
                print(f"  [err] index_weight {uni} {ms}: {str(exc)[:60]}")
                continue
            if df is not None and not df.empty:
                frames.append(df)
        if not frames:
            print(f"[warn] 17_指数成分与权重/{uni}: no data")
            continue
        allw = pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["con_code", "trade_date"])
        allw["universe"] = uni
        allw["stock_code"] = allw["con_code"].map(ts_to_stock_code)
        total += _save(allw, f)
        print(f"[ok] 17_指数成分与权重/{uni}: {len(allw)} rows")
    return {"folder": "17_指数成分与权重", "endpoint": "index_weight+index_basic",
            "status": "ok", "rows": total}


def run_namechange(pro, root: Path, start: str, end: str) -> dict:
    out = root / "18_股票曾用名"
    out.mkdir(parents=True, exist_ok=True)
    df = call(pro.namechange, start_date=start, end_date=end,
              fields="ts_code,name,start_date,end_date,ann_date,change_reason")
    n = _save(df, out / "namechange.parquet") if df is not None and not df.empty else 0
    print(f"[ok] 18_股票曾用名: {n} rows")
    return {"folder": "18_股票曾用名", "endpoint": "namechange", "status": "ok", "rows": n}


def run_stock_company(pro, root: Path) -> dict:
    out = root / "19_上市公司基本信息"
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for ex in ("SSE", "SZSE", "BSE"):
        try:
            df = call(pro.stock_company, exchange=ex)
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            print(f"  [err] stock_company {ex}: {str(exc)[:60]}")
    n = _save(pd.concat(frames, ignore_index=True), out / "stock_company.parquet") if frames else 0
    print(f"[ok] 19_上市公司基本信息: {n} rows")
    return {"folder": "19_上市公司基本信息", "endpoint": "stock_company", "status": "ok", "rows": n}


# ---- manifest --------------------------------------------------------------
MANIFEST_ROWS = [
    ("01_股票列表", "stock_basic", "上市/退市/暂停 三张表 (含退市→survivorship)"),
    ("02_交易日历", "trade_cal", "SSE+SZSE 交易日历"),
    ("03_日线行情", "daily", "每日全市场未复权行情 (每个交易日一个文件)"),
    ("04_复权因子", "adj_factor", "每日复权因子 (前/后复权用)"),
    ("05_每日指标", "daily_basic", "每日 PE/PB/PS/换手率/市值 等"),
    ("06_资金流向", "moneyflow", "每日个股资金流向"),
    ("07_停复牌", "suspend_d", "每日停复牌"),
    ("08_涨跌停价格", "stk_limit", "每日涨跌停价"),
    ("09_利润表", "income_vip", "全市场利润表 (按季度)"),
    ("10_资产负债表", "balancesheet_vip", "全市场资产负债表 (按季度)"),
    ("11_现金流量表", "cashflow_vip", "全市场现金流量表 (按季度)"),
    ("12_财务指标", "fina_indicator_vip", "全市场财务指标 ROE等 (按季度)"),
    ("13_业绩预告", "forecast_vip", "全市场业绩预告 (按季度)"),
    ("14_业绩快报", "express_vip", "全市场业绩快报 (按季度)"),
    ("15_分红送股", "dividend", "分红送股 (按公告日)"),
    ("16_指数日线", "index_daily", "主要指数日线 (沪深300/中证500/1000/上证50/上证/深成/创业板/科创50)"),
    ("17_指数成分与权重", "index_weight + index_basic", "指数月度成分权重 + 指数基本信息"),
    ("18_股票曾用名", "namechange", "股票曾用名变更"),
    ("19_上市公司基本信息", "stock_company", "上市公司基本信息 (SSE/SZSE/BSE)"),
]


def write_manifest(root: Path, start: str, end: str) -> None:
    today = end  # archive 'as of' end date; full run stamps last-updated below
    lines = [
        "# 量化数据归档 (Tushare) 说明",
        "",
        f"数据源: Tushare Pro (代理计划, source 标签=`tushare`)",
        f"时间范围: {start} ~ {end} (最近5年)",
        f"生成/更新日期: {today}  ·  最后更新: {today}",
        "",
        "> 反封禁说明: 本归档**未使用伪造IP**。Tushare 按 token(积分) 限流, 与客户端IP无关,",
        "> 且伪造源IP无法完成 HTTPS 握手。真正生效的是节流 (0.7s/次, ~85次/分, 低于100/分上限)",
        "> + 退避重试 + 单次调用拉全市场。详见 scripts/fetch_tushare_archive.py 头部说明。",
        "",
        "## 文件夹清单",
        "",
        "| 文件夹 | Tushare接口 | 内容 |",
        "| --- | --- | --- |",
    ]
    for folder, ep, desc in MANIFEST_ROWS:
        lines.append(f"| `{folder}` | `{ep}` | {desc} |")
    lines += [
        "",
        "## 命名与结构",
        "- 按交易日切分的数据集: 每个交易日一个 `YYYYMMDD.parquet`; `YYYYMMDD.empty` 为该日无数据的标记 (可续传)。",
        "- 按季度切分的财务数据集: 每季度一个 `YYYYMMDD.parquet` (季末日期)。",
        "- 每个 parquet 含 `source='tushare'` 列; 个股表含 `stock_code` (6位) 列。",
        "",
        "## 未包含 (及原因)",
        "- 港股 hk_daily: 当前 token 无权限 (单独付费接口)。",
        "- 期货/期权/美股/数字货币: 需单独权限 / 与A股量化无关。",
        "- 周线/月线: 可由 `03_日线行情` 派生。",
        "- 龙虎榜/大宗交易: 价值较低, 需要时可加。",
        "",
        "重新拉取/续传: `python scripts/fetch_tushare_archive.py --what all`",
        "校验: `python scripts/fetch_tushare_archive.py --what verify`",
    ]
    (root / "说明.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] manifest -> {root / '说明.md'}")


# ---- verify ----------------------------------------------------------------
def verify(root: Path) -> None:
    import pyarrow.parquet as pq

    print(f"\n=== 归档校验: {root} ===")
    print(f"{'文件夹':<22} {'文件数':>6} {'空标记':>6} {'总行数':>12}  日期范围")
    print("-" * 78)
    for folder in ALL_KEYS:
        d = root / folder
        if not d.exists():
            print(f"{folder:<22} {'缺失':>6}")
            continue
        files = sorted(d.glob("*.parquet"))
        empties = list(d.glob("*.empty"))
        total = 0
        for f in files:
            try:
                total += pq.ParquetFile(f).metadata.num_rows
            except Exception:  # noqa: BLE001
                pass
        dates = sorted(f.stem for f in files if f.stem.isdigit() and len(f.stem) == 8)
        rng = f"{dates[0]}~{dates[-1]}" if dates else "-"
        flag = "  ⚠ 空" if not files else ""
        print(f"{folder:<22} {len(files):>6} {len(empties):>6} {total:>12,}  {rng}{flag}")
    man = root / "说明.md"
    print("-" * 78)
    print(f"说明.md: {'存在' if man.exists() else '缺失 ⚠'}")


# ---- driver ----------------------------------------------------------------
def run_all(pro, root: Path, start: str, end: str) -> list[dict]:
    days = _trade_days(pro, start, end)
    print(f"[info] {len(days)} 交易日 {start}~{end}")
    results: list[dict] = []
    results.append(run_stock_list(pro, root))
    results.append(run_trade_cal(pro, root, start, end))
    for folder, ep in PER_DATE:
        results.append(run_per_date(pro, root, folder, ep, days))
    for folder, ep in PER_PERIOD:
        results.append(run_per_period(pro, root, folder, ep, start, end))
    results.append(run_dividend(pro, root, days))
    results.append(run_index_daily(pro, root, start, end))
    results.append(run_index_weight(pro, root, start, end))
    results.append(run_namechange(pro, root, start, end))
    results.append(run_stock_company(pro, root))
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", default="all",
                    help="all | verify | <folder key e.g. 03_日线行情>")
    ap.add_argument("--start", default="20210628")
    ap.add_argument("--end", default="20260628")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    if args.what == "verify":
        verify(root)
        return

    pro = get_pro()

    if args.what == "all":
        run_all(pro, root, args.start, args.end)
        write_manifest(root, args.start, args.end)
        verify(root)
        return

    # single dataset by folder key
    key = args.what
    days = None
    per_date = dict(PER_DATE)
    per_period = dict(PER_PERIOD)
    if key in per_date:
        days = _trade_days(pro, args.start, args.end)
        run_per_date(pro, root, key, per_date[key], days)
    elif key in per_period:
        run_per_period(pro, root, key, per_period[key], args.start, args.end)
    elif key == "01_股票列表":
        run_stock_list(pro, root)
    elif key == "02_交易日历":
        run_trade_cal(pro, root, args.start, args.end)
    elif key == "15_分红送股":
        run_dividend(pro, root, _trade_days(pro, args.start, args.end))
    elif key == "16_指数日线":
        run_index_daily(pro, root, args.start, args.end)
    elif key == "17_指数成分与权重":
        run_index_weight(pro, root, args.start, args.end)
    elif key == "18_股票曾用名":
        run_namechange(pro, root, args.start, args.end)
    elif key == "19_上市公司基本信息":
        run_stock_company(pro, root)
    else:
        print(f"[err] unknown --what '{key}'. Valid: all, verify, or one of:\n  " +
              "\n  ".join(ALL_KEYS))
        sys.exit(2)
    write_manifest(root, args.start, args.end)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[interrupted] 已写入的文件可续传, 重跑 --what all 即可。")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
