"""Portfolio Tracker for Paper Trading v6.1

记录虚拟持仓、计算盈亏、对比基准。
每日运行时自动记录调仓、更新净值。

持仓表结构 (portfolio_holdings):
  stock_code, strategy_id, buy_date, buy_price, shares, weight,
  current_price, current_value, pnl_pct, hold_days

净值表结构 (portfolio_nav):
  date, strategy_id, nav, daily_return, benchmark_return, excess_return,
  cum_excess, max_drawdown, beat_benchmark
"""
from __future__ import annotations

import json
import os
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

import duckdb
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = str(ROOT / "quant.duckdb")
TRACKER_DIR = ROOT / "reports" / "paper_trading_v6.1" / "tracker"
INITIAL_CAPITAL = 300000.0
MAX_STOCKS_PER_STRATEGY = 10  # 每策略最多实际建仓10只（不改变策略top_n，只是实际持仓数）


def _ensure_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create tracker tables if not exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_holdings (
            stock_code     VARCHAR,
            stock_name     VARCHAR,
            strategy_id    VARCHAR,
            buy_date       DATE,
            buy_price      DOUBLE,
            shares         DOUBLE,
            weight         DOUBLE,
            current_price  DOUBLE,
            current_value  DOUBLE,
            pnl_pct        DOUBLE,
            hold_days      INTEGER,
            updated_at     TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_nav (
            date            DATE,
            strategy_id     VARCHAR,
            nav             DOUBLE,
            daily_return    DOUBLE,
            benchmark_return DOUBLE,
            excess_return   DOUBLE,
            cum_excess      DOUBLE,
            max_drawdown    DOUBLE,
            beat_benchmark  BOOLEAN,
            total_value     DOUBLE,
            num_holdings    INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_trades (
            trade_date      DATE,
            strategy_id     VARCHAR,
            stock_code      VARCHAR,
            stock_name      VARCHAR,
            action          VARCHAR,
            price           DOUBLE,
            shares          DOUBLE,
            value           DOUBLE,
            pnl_pct         DOUBLE,
            reason          VARCHAR
        )
    """)


def _get_stock_names(con: duckdb.DuckDBPyConnection, codes: List[str]) -> Dict[str, str]:
    """Get stock names for a list of codes."""
    if not codes:
        return {}
    placeholders = ", ".join(["?"] * len(codes))
    df = con.execute(
        f"SELECT stock_code, name FROM stock_meta WHERE stock_code IN ({placeholders})",
        codes,
    ).fetchdf()
    return dict(zip(df["stock_code"], df["name"]))


def _get_latest_prices(con: duckdb.DuckDBPyConnection, codes: List[str], as_of_date: str) -> Dict[str, dict]:
    """Get latest prices for a list of codes on or before as_of_date."""
    if not codes:
        return {}
    placeholders = ", ".join(["?"] * len(codes))
    df = con.execute(
        f"""
        SELECT stock_code, close_adj, pct_chg, turnover_rate, volume, trade_date
        FROM market_daily
        WHERE stock_code IN ({placeholders})
          AND trade_date <= ?
          AND trade_date = (
            SELECT MAX(trade_date) FROM market_daily WHERE trade_date <= ?
          )
        """,
        codes + [as_of_date, as_of_date],
    ).fetchdf()
    result = {}
    for _, r in df.iterrows():
        result[str(r["stock_code"])] = {
            "close": round(float(r["close_adj"]), 4),
            "pct_chg": round(float(r["pct_chg"]), 2),
            "turnover_rate": round(float(r["turnover_rate"]), 2),
            "volume": float(r["volume"]),
            "trade_date": str(r["trade_date"]),
        }
    return result


def _get_benchmark_return(con: duckdb.DuckDBPyConnection, as_of_date: str) -> float:
    """Get CSI300 daily return on as_of_date."""
    df = con.execute(
        """
        SELECT close FROM index_daily
        WHERE index_name = 'csi300' AND trade_date <= ?
        ORDER BY trade_date DESC LIMIT 2
        """,
        [as_of_date],
    ).fetchdf()
    if len(df) < 2:
        return 0.0
    return round(float((df["close"].iloc[0] / df["close"].iloc[1] - 1)), 6)


def _get_benchmark_cum_return(con: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> float:
    """Get CSI300 cumulative return between two dates."""
    df = con.execute(
        """
        SELECT close FROM index_daily
        WHERE index_name = 'csi300' AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
        """,
        [start_date, end_date],
    ).fetchdf()
    if len(df) < 2:
        return 0.0
    return round(float((df["close"].iloc[-1] / df["close"].iloc[0] - 1)), 6)


def update_holdings(
    signal_date: str,
    signals: dict,
) -> dict:
    """Update holdings based on new signals.

    For each strategy:
    1. Compare new picks with current holdings
    2. Sell stocks that are no longer in picks (record PnL)
    3. Buy new stocks that weren't in holdings
    4. Update current prices and PnL for remaining holdings
    5. Record NAV

    Args:
        signal_date: Date of the signal (YYYY-MM-DD)
        signals: Signal dict from paper_trading_runner

    Returns:
        Portfolio summary dict
    """
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH)
    _ensure_tables(con)

    # Get benchmark return for the day
    bench_ret = _get_benchmark_return(con, signal_date)

    # All stock codes across strategies
    all_codes = set()
    for s in signals.get("strategies", {}).values():
        for p in s["picks"]:
            all_codes.add(p["stock_code"])
    all_codes = sorted(all_codes)

    # Get names and prices
    names = _get_stock_names(con, all_codes)
    prices = _get_latest_prices(con, all_codes, signal_date)

    summary = {
        "signal_date": signal_date,
        "benchmark_daily_return": bench_ret,
        "initial_capital": INITIAL_CAPITAL,
        "strategies": {},
    }

    num_strategies = len(signals.get("strategies", {}))
    per_strategy_capital = INITIAL_CAPITAL / num_strategies if num_strategies > 0 else INITIAL_CAPITAL

    for sid, sconf in signals.get("strategies", {}).items():
        top_n = sconf["top_n"]
        picks = {p["stock_code"]: p for p in sconf["picks"]}

        # Load current holdings for this strategy
        current = con.execute(
            "SELECT * FROM portfolio_holdings WHERE strategy_id = ? ORDER BY buy_date",
            [sid],
        ).fetchdf()

        # Determine buys and sells
        current_codes = set(current["stock_code"].tolist()) if not current.empty else set()
        new_codes = set(picks.keys())
        sell_codes = current_codes - new_codes
        buy_codes = new_codes - current_codes
        hold_codes = current_codes & new_codes

        # === 移动止损扫描 ===
        # 对当前持仓逐只判断是否触发两层移动止损
        stop_sells = []  # [(code, reason), ...]
        if not current.empty:
            from quant_agent_team.risk_overlay import default_live_overlay
            risk = default_live_overlay()

            for code in list(current_codes):
                row = current[current["stock_code"] == code].iloc[0]
                buy_price = float(row["buy_price"])
                curr_price = prices.get(code, {}).get("close", buy_price)
                if buy_price <= 0:
                    continue

                # 查持仓期历史最高价 (从buy_date到signal_date)
                try:
                    peak_row = con.execute("""
                        SELECT MAX(close_adj) as peak FROM market_daily
                        WHERE stock_code = ? AND trade_date >= ? AND trade_date <= ?
                    """, [code, str(row["buy_date"]), signal_date]).fetchone()
                    peak_price = float(peak_row[0]) if peak_row and peak_row[0] else buy_price
                except Exception:
                    peak_price = max(buy_price, curr_price)

                gain = curr_price / buy_price - 1.0
                peak_gain = peak_price / buy_price - 1.0

                # Tier2: +30%后从峰值回撤10%
                if peak_gain >= risk.tier2_trigger:
                    stop_level = peak_price * (1.0 - risk.tier2_pullback)
                    if curr_price <= stop_level:
                        stop_sells.append((code, "stop_tier2"))
                        continue

                # Tier1: +15%后锁定+5%底线
                if peak_gain >= risk.tier1_trigger:
                    stop_level = buy_price * (1.0 + risk.tier1_floor)
                    if curr_price <= stop_level:
                        stop_sells.append((code, "stop_tier1"))
                        continue

        # 止损卖出合并到sell_codes
        for code, reason in stop_sells:
            if code not in sell_codes:
                sell_codes.add(code)
                # 如果该股票仍在new_codes中, 也需要先卖出再重新买入
            elif code in hold_codes:
                # 持有的股票触发止损, 需要从hold移到sell再重新买
                hold_codes.discard(code)
                buy_codes.add(code)

        # Record sells
        trades = []
        stop_reason_map = {code: reason for code, reason in stop_sells}
        for code in sell_codes:
            row = current[current["stock_code"] == code].iloc[0]
            buy_price = float(row["buy_price"])
            curr_price = prices.get(code, {}).get("close", buy_price)
            pnl = round((curr_price / buy_price - 1), 4)
            con.execute(
                "DELETE FROM portfolio_holdings WHERE strategy_id = ? AND stock_code = ?",
                [sid, code],
            )
            sell_reason = stop_reason_map.get(code, "跌出top_n")
            con.execute(
                """INSERT INTO portfolio_trades VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [signal_date, sid, code, names.get(code, ""), "SELL",
                 curr_price, float(row["shares"]), float(row["shares"]) * curr_price, pnl, sell_reason],
            )
            trades.append({"action": "SELL", "code": code, "name": names.get(code, ""),
                          "pnl_pct": pnl, "buy_price": buy_price, "sell_price": curr_price,
                          "reason": sell_reason})

        # Record buys
        for code in buy_codes:
            price = prices.get(code, {}).get("close", 0)
            if price <= 0:
                continue
            weight = 1.0 / top_n  # 保持策略原始权重，不改
            shares = (per_strategy_capital * weight) / price
            con.execute(
                """INSERT INTO portfolio_holdings
                   (stock_code, stock_name, strategy_id, buy_date, buy_price, shares, weight,
                    current_price, current_value, pnl_pct, hold_days, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                [code, names.get(code, ""), sid, signal_date, price, shares, weight,
                 price, shares * price, 0.0, 0, datetime.now()],
            )
            # 也写入交易记录表
            con.execute(
                """INSERT INTO portfolio_trades
                   (trade_date, strategy_id, stock_code, stock_name, action,
                    price, shares, value, pnl_pct, reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [signal_date, sid, code, names.get(code, ""), "BUY",
                 price, shares, shares * price, 0.0, "新入选top_n"],
            )
            trades.append({"action": "BUY", "code": code, "name": names.get(code, ""),
                          "buy_price": price, "shares": shares, "value": shares * price})

        # Update current prices for held stocks
        for code in hold_codes:
            price = prices.get(code, {}).get("close", 0)
            if price <= 0:
                continue
            row = current[current["stock_code"] == code].iloc[0]
            buy_price = float(row["buy_price"])
            pnl = round((price / buy_price - 1), 4)
            hold_days = (pd.Timestamp(signal_date) - pd.Timestamp(row["buy_date"])).days
            con.execute(
                """UPDATE portfolio_holdings
                   SET current_price = ?, current_value = shares * ?, pnl_pct = ?,
                       hold_days = ?, updated_at = ?
                   WHERE strategy_id = ? AND stock_code = ?""",
                [price, price, pnl, hold_days, datetime.now(), sid, code],
            )

        # Calculate strategy NAV
        holdings = con.execute(
            "SELECT * FROM portfolio_holdings WHERE strategy_id = ?",
            [sid],
        ).fetchdf()

        if not holdings.empty:
            total_value = float((holdings["current_value"]).sum())
            # Get previous NAV
            prev_nav = con.execute(
                "SELECT nav FROM portfolio_nav WHERE strategy_id = ? ORDER BY date DESC LIMIT 1",
                [sid],
            ).fetchone()
            prev_nav_val = float(prev_nav[0]) if prev_nav else 1.0

            # Calculate daily return: only for stocks held BEFORE today (hold_days > 0).
            # Stocks bought today (hold_days == 0) were purchased at close, so today's
            # pct_chg does NOT count as portfolio return.
            daily_ret = 0.0
            if not holdings.empty:
                weighted_rets = []
                for _, h in holdings.iterrows():
                    if int(h["hold_days"]) == 0:
                        continue  # 今天刚买入，不计入当日收益
                    code = h["stock_code"]
                    pct = prices.get(code, {}).get("pct_chg", 0)
                    weighted_rets.append(pct / 100 * float(h["weight"]))
                daily_ret = round(sum(weighted_rets), 6)

            nav = prev_nav_val * (1 + daily_ret)
            excess = round(daily_ret - bench_ret, 6)

            # Cumulative excess
            first_nav = con.execute(
                "SELECT nav FROM portfolio_nav WHERE strategy_id = ? ORDER BY date ASC LIMIT 1",
                [sid],
            ).fetchone()
            if first_nav:
                cum_nav = nav / float(first_nav[0]) - 1
                # Benchmark cum return since first trade date
                first_date = con.execute(
                    "SELECT date FROM portfolio_nav WHERE strategy_id = ? ORDER BY date ASC LIMIT 1",
                    [sid],
                ).fetchone()
                if first_date:
                    bench_cum = _get_benchmark_cum_return(con, str(first_date[0]), signal_date)
                    cum_excess = round(cum_nav - bench_cum, 6)
                else:
                    cum_excess = cum_nav
            else:
                cum_excess = 0.0

            # Max drawdown
            nav_history = con.execute(
                "SELECT nav FROM portfolio_nav WHERE strategy_id = ? ORDER BY date",
                [sid],
            ).fetchdf()
            if not nav_history.empty:
                all_navs = list(nav_history["nav"]) + [nav]
                peak = all_navs[0]
                mdd = 0.0
                for v in all_navs:
                    peak = max(peak, v)
                    mdd = max(mdd, (peak - v) / peak)
            else:
                mdd = 0.0

            beat = daily_ret > bench_ret

            con.execute(
                """INSERT INTO portfolio_nav
                   (date, strategy_id, nav, daily_return, benchmark_return, excess_return,
                    cum_excess, max_drawdown, beat_benchmark, total_value, num_holdings)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [signal_date, sid, nav, daily_ret, bench_ret, excess,
                 cum_excess, mdd, beat, total_value, len(holdings)],
            )

            summary["strategies"][sid] = {
                "name": sconf["strategy_name"],
                "nav": round(nav, 4),
                "daily_return": daily_ret,
                "benchmark_return": bench_ret,
                "excess_return": excess,
                "cum_excess": cum_excess,
                "max_drawdown": round(mdd, 4),
                "beat_benchmark": beat,
                "total_value": round(total_value, 2),
                "num_holdings": len(holdings),
                "trades": trades,
                "holdings_detail": [
                    {
                        "stock_code": str(h["stock_code"]),
                        "stock_name": str(h["stock_name"]),
                        "buy_date": str(h["buy_date"]),
                        "buy_price": round(float(h["buy_price"]), 2),
                        "current_price": round(float(h["current_price"]), 2),
                        "shares": round(float(h["shares"]), 0),
                        "weight": round(float(h["weight"]), 4),
                        "current_value": round(float(h["current_value"]), 2),
                        "pnl_pct": round(float(h["pnl_pct"]), 4),
                        "hold_days": int(h["hold_days"]),
                        "benchmark_pnl_since_buy": _get_benchmark_cum_return(
                            con, str(h["buy_date"]), signal_date
                        ),
                        "excess_vs_benchmark": round(
                            float(h["pnl_pct"]) - _get_benchmark_cum_return(
                                con, str(h["buy_date"]), signal_date
                            ), 4
                        ),
                    }
                    for _, h in holdings.iterrows()
                ],
            }
        else:
            # First day - all new buys
            summary["strategies"][sid] = {
                "name": sconf["strategy_name"],
                "nav": 1.0,
                "daily_return": 0.0,
                "benchmark_return": bench_ret,
                "excess_return": 0.0,
                "cum_excess": 0.0,
                "max_drawdown": 0.0,
                "beat_benchmark": False,
                "total_value": per_strategy_capital,
                "num_holdings": len(buy_codes),
                "trades": trades,
                "holdings_detail": [],
            }

    # Combined portfolio
    total_value = sum(s.get("total_value", 0) for s in summary["strategies"].values())
    total_daily_ret = np.mean([s.get("daily_return", 0) for s in summary["strategies"].values()])
    total_excess = round(total_daily_ret - bench_ret, 6)
    summary["combined"] = {
        "total_value": round(total_value, 2),
        "daily_return": round(total_daily_ret, 6),
        "benchmark_return": bench_ret,
        "excess_return": total_excess,
        "num_holdings": len(all_codes),
    }

    con.close()

    # Save tracker snapshot
    out_file = TRACKER_DIR / f"tracker_{signal_date.replace('-', '')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    return summary


def print_tracker_summary(summary: dict) -> None:
    """Print a human-readable tracker summary."""
    print("\n" + "=" * 110)
    print(f"  持仓跟踪  |  日期: {summary['signal_date']}  |  初始资金: ¥{summary['initial_capital']:,.0f}")
    print("=" * 110)

    print(f"\n  {'策略ID':<8} {'策略名称':<16} {'净值':>8} {'当日收益':>10} {'基准收益':>10} {'超额收益':>10} {'累计超额':>10} {'最大回撤':>8} {'跑赢':>4} {'持仓数':>6}")
    print(f"  {'-'*8} {'-'*16} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*4} {'-'*6}")
    for sid, s in summary["strategies"].items():
        beat = "是" if s["beat_benchmark"] else "否"
        print(f"  {sid:<8} {s['name']:<16} {s['nav']:>8.4f} {s['daily_return']:>10.4%} {s['benchmark_return']:>10.4%} {s['excess_return']:>10.4%} {s['cum_excess']:>10.4%} {s['max_drawdown']:>8.2%} {beat:>4} {s['num_holdings']:>6}")

    c = summary["combined"]
    print(f"\n  合并组合: 总市值 ¥{c['total_value']:,.2f}  当日收益 {c['daily_return']:.4%}  超额 {c['excess_return']:.4%}  持仓 {c['num_holdings']} 只")

    # Holdings detail for first strategy
    for sid, s in summary["strategies"].items():
        if not s.get("holdings_detail"):
            continue
        print(f"\n  [{sid}] {s['name']} 持仓明细:")
        print(f"  {'股票代码':<8} {'股票名称':<8} {'买入日':<12} {'买入价':>8} {'现价':>8} {'持仓盈亏%':>10} {'基准同期%':>10} {'超额收益%':>10} {'持有天数':>8}")
        print(f"  {'-'*8} {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        for h in sorted(s["holdings_detail"], key=lambda x: x["pnl_pct"], reverse=True)[:15]:
            print(f"  {h['stock_code']:<8} {h['stock_name']:<8} {h['buy_date']:<12} {h['buy_price']:>8.2f} {h['current_price']:>8.2f} {h['pnl_pct']:>10.2%} {h['benchmark_pnl_since_buy']:>10.2%} {h['excess_vs_benchmark']:>10.2%} {h['hold_days']:>8}")
        break  # Only show first strategy's details

    # Trades
    all_trades = []
    for sid, s in summary["strategies"].items():
        for t in s.get("trades", []):
            t["strategy_id"] = sid
            all_trades.append(t)
    if all_trades:
        print(f"\n  今日调仓 ({len(all_trades)} 笔):")
        for t in all_trades:
            if t["action"] == "BUY":
                print(f"  买入 {t['code']} {t.get('name','')} @ {t['buy_price']:.2f}  [{t['strategy_id']}]")
            else:
                print(f"  卖出 {t['code']} {t.get('name','')} @ {t['sell_price']:.2f}  盈亏 {t['pnl_pct']:.2%}  [{t['strategy_id']}]")

    print("=" * 110)
