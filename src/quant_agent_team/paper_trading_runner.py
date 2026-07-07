"""Paper Trading Runner v6.2

每日收盘后运行，用五个最佳策略（5个不同因子家族）生成交易信号。
用法:
    python -m quant_agent_team.paper_trading_runner           # 生成今日信号
    python -m quant_agent_team.paper_trading_runner --backtest # 回顾最近表现
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

import duckdb
import numpy as np
import pandas as pd

from .factor_library import build_hypothesis
from .factor_scoring import composite_scores, select_top_n
from .hypothesis import FactorDef, FactorHypothesis, FactorConfig
from .ic_weighting import (
    add_forward_return,
    compute_ic_panel,
    ic_adaptive_weights,
    weights_as_of,
)
from .pipeline_v51 import load_backtest_frame

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = str(ROOT / "quant.duckdb")
OUTPUT_DIR = ROOT / "reports" / "paper_trading_v6.1"


# ── Strategy definitions (v6.2: top 5 from 5 different factor families) ─────
# Diversified across RSV / turnover / volume-ratio / skewness / vol-price-corr
# Each family captures a distinct alpha dimension for portfolio diversification.

STRATEGIES = {
    "P-001": {
        "name": "rsv5_mom_2",
        "factors": ["rsv_5", "ret_20d"],
        "directions": {"rsv_5": "long_low", "ret_20d": "long_high"},
        "top_n": 30,
        "rebalance_days": 20,
        "ir": 1.074,
        "oos_return": 1.310,
        "max_drawdown": 0.123,
    },
    "I-012": {
        "name": "tochg_mom_2",
        "factors": ["turnover_change_5_20", "ret_20d"],
        "directions": {"turnover_change_5_20": "long_low", "ret_20d": "long_high"},
        "top_n": 30,
        "rebalance_days": 20,
        "ir": 0.967,
        "oos_return": 1.147,
        "max_drawdown": 0.146,
    },
    "I-004": {
        "name": "vol_mom_2",
        "factors": ["volume_ma_ratio_5_20", "ret_20d"],
        "directions": {"volume_ma_ratio_5_20": "long_low", "ret_20d": "long_high"},
        "top_n": 30,
        "rebalance_days": 20,
        "ir": 0.960,
        "oos_return": 1.215,
        "max_drawdown": 0.166,
    },
    "M-001": {
        "name": "skew_mom_2",
        "factors": ["ret_skew_20d", "ret_20d"],
        "directions": {"ret_skew_20d": "long_low", "ret_20d": "long_high"},
        "top_n": 30,
        "rebalance_days": 20,
        "ir": 0.611,
        "oos_return": 0.732,
        "max_drawdown": 0.150,
    },
    "I-007": {
        "name": "vp_corr_ret20",
        "factors": ["vol_price_corr_20d", "ret_20d"],
        "directions": {"vol_price_corr_20d": "long_low", "ret_20d": "long_high"},
        "top_n": 30,
        "rebalance_days": 20,
        "ir": 0.553,
        "oos_return": 0.654,
        "max_drawdown": 0.138,
    },
}


def _load_universe(con: duckdb.DuckDBPyConnection, universe: str = "hs300") -> List[str]:
    """Load latest universe constituents."""
    df = con.execute(
        """
        SELECT stock_code FROM index_constituents
        WHERE universe = ? AND trade_date = (
            SELECT MAX(trade_date) FROM index_constituents WHERE universe = ?
        )
        ORDER BY stock_code
        """,
        [universe, universe],
    ).fetchdf()
    return sorted(df["stock_code"].tolist())


def _load_benchmark(con: duckdb.DuckDBPyConnection, index_name: str = "csi300") -> pd.DataFrame:
    """Load benchmark daily close."""
    df = con.execute(
        "SELECT trade_date, close FROM index_daily WHERE index_name = ? ORDER BY trade_date",
        [index_name],
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def _compute_ic_weights(
    frame: pd.DataFrame,
    factors: List[str],
    as_of_date,
    forward_days: int = 20,
    lookback: int = 60,
) -> Dict[str, float]:
    """Compute IC-adaptive weights as of a given date."""
    price = frame[["stock_code", "trade_date", "close_price_adj"]].rename(
        columns={"close_price_adj": "close_adj"}
    )
    panel_with_fwd = add_forward_return(frame, price, forward_days=forward_days)
    ic_panel = compute_ic_panel(panel_with_fwd, factors)
    if ic_panel.empty:
        n = len(factors)
        return {f: 1.0 / n for f in factors}
    weights_df = ic_adaptive_weights(ic_panel, forward_days=forward_days, lookback=lookback)
    return weights_as_of(weights_df, as_of_date)


def _score_and_select(
    frame: pd.DataFrame,
    factors: List[str],
    directions: Dict[str, str],
    weights: Dict[str, float],
    top_n: int,
    as_of_date,
    stock_meta: Optional[pd.DataFrame] = None,
    latest_prices: Optional[dict] = None,
) -> List[dict]:
    """Score stocks and select top_n for a given date."""
    as_of_ts = pd.Timestamp(as_of_date)
    day_rows = frame.loc[frame["trade_date"] == as_of_ts].copy()
    if day_rows.empty:
        avail = frame.loc[frame["trade_date"] <= as_of_ts, "trade_date"].unique()
        if len(avail) == 0:
            return []
        latest = max(avail)
        day_rows = frame.loc[frame["trade_date"] == latest].copy()

    factor_defs = [
        FactorDef(name=f, source_field=f, direction=directions[f]) for f in factors
    ]
    scored = composite_scores(day_rows, factor_defs, weights)
    picks = select_top_n(scored, top_n)

    results = []
    for _, row in picks.iterrows():
        code = str(row["stock_code"])
        entry = {
            "stock_code": code,
            "composite_score": round(float(row["composite_score"]), 4),
        }
        # Add stock name and industry
        if stock_meta is not None and code in stock_meta:
            entry["stock_name"] = stock_meta[code].get("name", "")
            entry["industry"] = stock_meta[code].get("industry", "")
        # Add latest price
        if latest_prices is not None and code in latest_prices:
            entry["latest_price"] = latest_prices[code]
        results.append(entry)
    return results


def run_daily_signal(target_date: Optional[str] = None) -> dict:
    """Generate trading signals for all 3 strategies on a given date.

    Args:
        target_date: YYYY-MM-DD string. If None, uses the latest date in the database.

    Returns:
        Dict with signals for each strategy.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=True)

    # Determine signal date
    if target_date is None:
        latest = con.execute(
            "SELECT MAX(trade_date) FROM factor_panel"
        ).fetchone()[0]
        target_date = str(latest)
    signal_date = pd.Timestamp(target_date)

    # Load universe
    universe = _load_universe(con, "hs300")
    benchmark = _load_benchmark(con, "csi300")

    # Load stock metadata (name, industry)
    stock_meta_df = con.execute("SELECT stock_code, name, industry FROM stock_meta").fetchdf()
    stock_meta = {}
    for _, r in stock_meta_df.iterrows():
        stock_meta[str(r["stock_code"])] = {"name": r["name"], "industry": r["industry"]}

    # Load latest prices for all universe stocks
    latest_prices = {}
    price_rows = con.execute(
        """
        SELECT m.stock_code, m.close_adj, m.pct_chg, m.turnover_rate, m.volume
        FROM market_daily m
        WHERE m.trade_date = (SELECT MAX(trade_date) FROM market_daily)
          AND m.stock_code IN (SELECT unnest FROM unnest(?))
        """,
        [universe],
    ).fetchdf()
    for _, r in price_rows.iterrows():
        latest_prices[str(r["stock_code"])] = {
            "close": round(float(r["close_adj"]), 2),
            "pct_chg": round(float(r["pct_chg"]), 2),
            "turnover_rate": round(float(r["turnover_rate"]), 2),
            "volume": float(r["volume"]),
        }

    con.close()

    # Collect all unique factors across strategies
    all_factors = set()
    for s in STRATEGIES.values():
        all_factors.update(s["factors"])
    all_factors = sorted(all_factors)

    # Load backtest frame with all needed factors
    # Use 1 year of history for IC computation
    start_date = (signal_date - timedelta(days=400)).strftime("%Y-%m-%d")
    frame = load_backtest_frame(
        DB_PATH, factors=all_factors, universe=universe, start=start_date
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])

    # Generate signals for each strategy
    signals = {}
    for sid, sconf in STRATEGIES.items():
        factors = sconf["factors"]
        directions = sconf["directions"]
        top_n = sconf["top_n"]

        # IC-adaptive weights
        weights = _compute_ic_weights(frame, factors, signal_date)

        # Score and select
        picks = _score_and_select(frame, factors, directions, weights, top_n, signal_date,
                                   stock_meta=stock_meta, latest_prices=latest_prices)

        signals[sid] = {
            "strategy_name": sconf["name"],
            "signal_date": str(signal_date.date()),
            "factors": factors,
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "top_n": top_n,
            "rebalance_days": sconf["rebalance_days"],
            "picks": picks,
            "rolling_ir": sconf["ir"],
            "rolling_oos_return": sconf["oos_return"],
            "rolling_max_drawdown": sconf["max_drawdown"],
            "num_picks": len(picks),
        }

    # Combined portfolio (equal weight across 5 strategies)
    all_picks = set()
    for s in signals.values():
        for p in s["picks"]:
            all_picks.add(p["stock_code"])
    combined = sorted(all_picks)

    result = {
        "signal_date": str(signal_date.date()),
        "universe": "HS300",
        "benchmark": "CSI300",
        "total_unique_stocks": len(combined),
        "strategies": signals,
        "combined_portfolio": combined,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Save signal
    out_file = OUTPUT_DIR / f"signal_{signal_date.strftime('%Y%m%d')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    # Also save latest signal
    latest_file = OUTPUT_DIR / "latest_signal.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


def show_summary(result: dict) -> None:
    """Print a human-readable summary of the signals."""
    print("=" * 100)
    print(f"  虚拟盘信号 v6.1  |  信号日期: {result['signal_date']}  |  票池: HS300  |  基准: CSI300")
    print("=" * 100)

    for sid, s in result["strategies"].items():
        print(f"\n  [{sid}] {s['strategy_name']}  (滚动IR={s['rolling_ir']}, OOS收益={s['rolling_oos_return']:.1%}, 最大回撤={s['rolling_max_drawdown']:.1%})")
        print(f"  因子: {', '.join(s['factors'])}")
        print(f"  IC自适应权重: {', '.join(f'{k}={v:.3f}' for k, v in s['weights'].items())}")
        print(f"  选股数: {s['num_picks']} (top_n={s['top_n']}, 调仓周期={s['rebalance_days']}天)")
        if s["picks"]:
            print(f"  {'序号':<4} {'股票代码':<8} {'股票名称':<8} {'行业':<10} {'最新价':>8} {'当日涨跌%':>8} {'换手率%':>8} {'综合评分':>8}")
            print(f"  {'-'*4} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
            for i, p in enumerate(s["picks"][:10], 1):
                name = p.get("stock_name", "--")
                industry = p.get("industry", "--")
                price = p.get("latest_price", {})
                close = price.get("close", "--") if isinstance(price, dict) else "--"
                pct = price.get("pct_chg", "--") if isinstance(price, dict) else "--"
                turnover = price.get("turnover_rate", "--") if isinstance(price, dict) else "--"
                print(f"  {i:<4} {p['stock_code']:<8} {name:<8} {industry:<10} {close:>8} {pct:>8} {turnover:>8} {p['composite_score']:>8}")

    print(f"\n  合并组合: {result['total_unique_stocks']} 只唯一股票")
    print(f"  生成时间: {result['generated_at']}")
    print(f"  信号文件: {OUTPUT_DIR}/signal_{result['signal_date'].replace('-', '')}.json")
    print("=" * 100)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Paper Trading v6.1")
    parser.add_argument("--date", type=str, default=None, help="Signal date YYYY-MM-DD")
    parser.add_argument("--backtest", action="store_true", help="Show recent performance")
    args = parser.parse_args()

    if args.backtest:
        # TODO: implement backtest review
        print("Backtest review not yet implemented. Use --date for daily signal.")
        return

    result = run_daily_signal(target_date=args.date)
    show_summary(result)


if __name__ == "__main__":
    main()
