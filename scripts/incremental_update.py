#!/usr/bin/env python3
"""增量数据更新 — 只拉取 DuckDB 中缺失的交易日数据。

用 Tushare pro.daily(trade_date=...) 按日批量拉取全市场行情（每天1次API调用），
用 AkShare 补指数数据，然后重建 factor_panel。

用法:
    python scripts/incremental_update.py              # 自动补齐到今天
    python scripts/incremental_update.py --dry-run    # 只看缺哪些天，不拉数据
    python scripts/incremental_update.py --end 20260701
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DB_PATH = str(ROOT / "quant.duckdb")


def get_missing_trade_dates(con: duckdb.DuckDBPyConnection, end_date: str) -> list[str]:
    """对比 trade_cal 和 market_daily，找出缺失的交易日。"""
    from quant_agent_team.tushare_client import get_pro, call

    max_date = con.execute("SELECT MAX(trade_date) FROM market_daily").fetchone()[0]
    if max_date is None:
        print("[error] market_daily 表为空，请先全量拉取")
        return []

    start = max_date + timedelta(days=1)
    start_str = start.strftime("%Y%m%d")
    print(f"[check] market_daily max_date={max_date},  need {start_str}..{end_date}")

    pro = get_pro()
    cal = call(pro.trade_cal, exchange="SSE", start_date=start_str, end_date=end_date)
    open_days = sorted(cal.loc[cal["is_open"] == 1, "cal_date"].tolist())
    print(f"[check] 交易日历中 {start_str}..{end_date} 共 {len(open_days)} 个交易日")
    return open_days


def fetch_daily_price(trade_date: str) -> pd.DataFrame:
    """用 Tushare 拉某一天全市场行情 + 换手率，返回 market_daily 格式的 DataFrame。"""
    from quant_agent_team.tushare_client import get_pro, call, ts_to_stock_code

    pro = get_pro()

    # 1) pro.daily: OHLCV (全市场一次调用)
    df = call(pro.daily, trade_date=trade_date)
    if df is None or df.empty:
        return pd.DataFrame()

    # 2) pro.daily_basic: turnover_rate (全市场一次调用)
    db = call(pro.daily_basic, trade_date=trade_date,
              fields="ts_code,trade_date,turnover_rate")
    if db is not None and not db.empty:
        df = df.merge(db[["ts_code", "turnover_rate"]], on="ts_code", how="left")
    else:
        df["turnover_rate"] = None

    # 3) 归一化列名 -> market_daily schema
    out = pd.DataFrame({
        "stock_code": df["ts_code"].map(ts_to_stock_code),
        "trade_date": pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date,
        "open": df["open"].astype(float),
        "high": df["high"].astype(float),
        "low": df["low"].astype(float),
        "close_adj": df["close"].astype(float),  # 未复权close (4天内无除权事件，等于qfq)
        "volume": df["vol"].astype(float),       # 手
        "amount": df["amount"].astype(float) * 1000.0,  # 千元 -> 元
        "amplitude": ((df["high"] - df["low"]) / df["pre_close"].replace(0, pd.NA) * 100.0),
        "pct_chg": df["pct_chg"].astype(float),
        "change": df["change"].astype(float),
        "turnover_rate": df["turnover_rate"].astype(float),
    })
    return out


def update_market_daily(con: duckdb.DuckDBPyConnection, dates: list[str]) -> int:
    """逐日拉取并 INSERT 到 market_daily（跳过已存在的 trade_date）。"""
    total_inserted = 0
    for d in dates:
        # d 是 YYYYMMDD 格式，转成 date 对象给 DuckDB
        d_obj = pd.to_datetime(d, format="%Y%m%d").date()
        # 检查是否已有该日数据
        existing = con.execute(
            "SELECT count(*) FROM market_daily WHERE trade_date = ?", [d_obj]
        ).fetchone()[0]
        if existing > 0:
            print(f"  [skip] {d} 已有 {existing} 行")
            continue

        df = fetch_daily_price(d)
        if df.empty:
            print(f"  [warn] {d} 无数据（可能非交易日或API异常）")
            continue

        con.execute("INSERT INTO market_daily SELECT * FROM df")
        total_inserted += len(df)
        print(f"  [ok] {d}: 插入 {len(df)} 行")

    return total_inserted


def update_index_daily(con: duckdb.DuckDBPyConnection, end_date: str) -> None:
    """用 AkShare 增量更新指数数据（只拉缺失的日期段）。"""
    from quant_agent_team.benchmark import INDEX_SINA, fetch_index_daily
    import akshare as ak

    max_idx = con.execute("SELECT MAX(trade_date) FROM index_daily").fetchone()[0]
    if max_idx is None:
        start = "20220101"
    else:
        start = (max_idx + timedelta(days=1)).strftime("%Y%m%d")

    print(f"\n[index] 需更新 {start}..{end_date}")

    for name, sina_sym in INDEX_SINA.items():
        try:
            df = fetch_index_daily(name, start=start, end=end_date)
            if df.empty:
                print(f"  [skip] {name}: 无新数据")
                continue
            # 删除已有日期再插入（幂等）
            for _, row in df.iterrows():
                td = row["trade_date"].date() if hasattr(row["trade_date"], "date") else pd.to_datetime(row["trade_date"]).date()
                con.execute("DELETE FROM index_daily WHERE index_name = ? AND trade_date = ?",
                           [name, td])
                con.execute("INSERT INTO index_daily VALUES (?, ?, ?)",
                           [name, td, float(row["close"])])
            print(f"  [ok] {name}: +{len(df)} 行")
        except Exception as e:
            print(f"  [warn] {name}: {e}")


def rebuild_factor_panel(con: duckdb.DuckDBPyConnection) -> None:
    """重建 factor_panel（从 market_daily 全量计算因子）。"""
    from quant_agent_team.factor_panel import build_factor_panel

    print("\n[panel] 重建 factor_panel ...")
    result = build_factor_panel(DB_PATH)
    print(f"  {result}")


def main() -> int:
    ap = argparse.ArgumentParser(description="增量数据更新")
    ap.add_argument("--end", default=date.today().strftime("%Y%m%d"),
                    help="截止日期 YYYYMMDD")
    ap.add_argument("--dry-run", action="store_true", help="只检查不拉取")
    ap.add_argument("--skip-index", action="store_true", help="跳过指数更新")
    ap.add_argument("--skip-panel", action="store_true", help="跳过因子面板重建")
    args = ap.parse_args()

    con = duckdb.connect(DB_PATH)

    # 1. 找出缺失的交易日
    missing = get_missing_trade_dates(con, args.end)
    if not missing:
        print("[done] market_daily 已是最新，无需更新")
    else:
        print(f"[plan] 需补充 {len(missing)} 个交易日: {missing[0]}..{missing[-1]}")

    if args.dry_run:
        con.close()
        return 0

    # 2. 增量更新 market_daily
    if missing:
        print("\n[price] 开始增量拉取行情 ...")
        n = update_market_daily(con, missing)
        print(f"[price] 共插入 {n} 行")

    # 3. 增量更新 index_daily
    if not args.skip_index:
        update_index_daily(con, args.end)

    # 4. 重建 factor_panel
    if not args.skip_panel:
        rebuild_factor_panel(con)

    # 5. 汇总
    print("\n" + "=" * 60)
    for t in ["market_daily", "index_daily", "factor_panel"]:
        n, mx = con.execute(f"SELECT count(*), max(trade_date) FROM {t}").fetchone()
        print(f"  {t}: {n:,} rows, max_date={mx}")
    con.close()
    print("=" * 60)
    print("[done] 增量更新完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
