"""实盘模拟核心 — 带风控的实盘 P&L 计算。

从 gen_simulation_v2.py 沉淀，确保风控逻辑被版本控制追踪。

核心功能:
  - 按 best_rebalance 天数分段调仓
  - 每段内应用移动止损 (apply_trailing_stop)
  - 波动率仓位管理 (position_scales)
  - 输出逐股明细 (entry/exit/exit_reason/stop_hit)
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

from .risk_overlay import RiskOverlay, default_live_overlay, apply_trailing_stop, position_scales


def simulate_live_with_risk(
    frame: pd.DataFrame,
    picks_df: pd.DataFrame,
    hyp,
    wp,
    weighting_scheme: str,
    signal_date,
    mtm_date,
    best_rebalance: int,
    initial_capital: float,
    mtm_close_map: Dict[str, float],
    risk: Optional[RiskOverlay] = None,
    composite_scores_fn=None,
    select_top_n_fn=None,
    apply_weighting_fn=None,
) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
    """带风控的实盘模拟。

    参数:
        frame: 因子面板数据 (含 trade_date, stock_code, close_price_adj, 各因子列)
        picks_df: 信号日选股结果 (用于确定 top_n)
        hyp: 因子假设 (含 factors 列表)
        wp: IC 自适应权重函数 (传入日期返回权重)
        weighting_scheme: 加权方式 (equal/hybrid_ratio/inv_vol 等)
        signal_date: 信号日
        mtm_date: 估值日
        best_rebalance: 调仓周期 (交易日数)
        initial_capital: 初始资金
        mtm_close_map: 估值日收盘价 {stock_code: price}
        risk: 风控层 (默认用 default_live_overlay)
        composite_scores_fn: 复合打分函数
        select_top_n_fn: 选股函数
        apply_weighting_fn: 加权函数

    返回: (total_pnl, stock_details, stats)
    """
    risk = risk or default_live_overlay()

    # 1. 构造调仓日序列
    live_frame = frame[(frame["trade_date"] >= signal_date) & (frame["trade_date"] <= mtm_date)]
    all_dates = sorted(live_frame["trade_date"].unique())
    if len(all_dates) < 2:
        return _buy_and_hold_pnl(picks_df, signal_date, mtm_close_map,
                                  initial_capital, weighting_scheme, risk,
                                  apply_weighting_fn)

    step = max(1, best_rebalance)
    rebalance_dates = list(all_dates[::step])
    if rebalance_dates[-1] != all_dates[-1]:
        rebalance_dates.append(all_dates[-1])

    equity = initial_capital
    all_trades = []
    n_stop_exits = 0
    equity_curve = [{"trade_date": str(all_dates[0].date()), "equity": equity}]

    for i in range(len(rebalance_dates) - 1):
        entry_date = rebalance_dates[i]
        exit_date = rebalance_dates[i + 1]

        # 调仓日重新选股
        entry_rows = live_frame[live_frame["trade_date"] == entry_date].copy()
        if entry_rows.empty:
            equity_curve.append({"trade_date": str(exit_date.date()), "equity": equity})
            continue

        entry_weights = wp(entry_date)
        scored = composite_scores_fn(entry_rows, hyp.factors, entry_weights)
        picks = select_top_n_fn(scored, picks_df.shape[0])
        if picks.empty:
            equity_curve.append({"trade_date": str(exit_date.date()), "equity": equity})
            continue

        # 加权 + 波动率仓位管理
        stock_weights = apply_weighting_fn(picks, weighting_scheme)
        if risk.vol_position_enabled and "vol_20d" in picks.columns:
            vols = picks["vol_20d"].fillna(0).tolist()
            vol_scales = position_scales(vols, risk)
            stock_weights = stock_weights * np.array(vol_scales)
        total_w = stock_weights.sum()
        if total_w > 0:
            stock_weights = stock_weights / total_w
        else:
            continue

        picks = picks.sort_values("composite_score", ascending=False).reset_index(drop=True)
        picks["weight"] = stock_weights

        # 逐股: entry→exit 价格路径, 应用移动止损
        for _, srow in picks.iterrows():
            code = srow["stock_code"]
            entry_price = float(srow["close_price_adj"])
            if entry_price <= 0:
                continue

            stock_path = (
                live_frame[
                    (live_frame["stock_code"] == code)
                    & (live_frame["trade_date"] >= entry_date)
                    & (live_frame["trade_date"] <= exit_date)
                ]
                .sort_values("trade_date")["close_price_adj"]
                .astype(float)
                .tolist()
            )

            if len(stock_path) < 2:
                mtm_p = mtm_close_map.get(code, entry_price)
                stock_ret = mtm_p / entry_price - 1.0 if entry_price > 0 else 0.0
                w = float(srow["weight"])
                contribution = w * stock_ret
                equity *= (1.0 + contribution)
                all_trades.append({
                    "code": code, "weight": w, "buy_price": entry_price,
                    "mtm_price": mtm_p, "return": stock_ret,
                    "contribution": contribution,
                    "score": float(srow["composite_score"]),
                    "entry_date": str(entry_date.date()),
                    "exit_date": str(exit_date.date()),
                    "exit_reason": "rebalance", "stop_hit": False,
                })
                continue

            # 应用移动止损
            raw_exit_price, exited_early = apply_trailing_stop(stock_path, entry_price, risk)

            if not exited_early:
                exit_reason = "rebalance"
            else:
                gain = raw_exit_price / entry_price - 1.0
                if gain >= risk.tier2_trigger:
                    exit_reason = "stop_tier2"
                else:
                    exit_reason = "stop_tier1"
                n_stop_exits += 1

            stock_ret = raw_exit_price / entry_price - 1.0
            w = float(srow["weight"])
            contribution = w * stock_ret
            equity *= (1.0 + contribution)

            shares = int(initial_capital * w / entry_price / 100) * 100 if entry_price > 0 else 0
            all_trades.append({
                "code": code, "weight": w, "buy_price": entry_price,
                "mtm_price": raw_exit_price, "return": stock_ret,
                "contribution": contribution,
                "score": float(srow["composite_score"]),
                "shares": shares,
                "cost_value": shares * entry_price,
                "current_value": shares * raw_exit_price,
                "entry_date": str(entry_date.date()),
                "exit_date": str(exit_date.date()),
                "exit_reason": exit_reason, "stop_hit": exited_early,
                "holding_days": len(stock_path) - 1,
            })

        equity_curve.append({"trade_date": str(exit_date.date()), "equity": equity})

    total_pnl = equity / initial_capital - 1.0

    # 计算实盘模拟 MDD
    eq_values = [p["equity"] for p in equity_curve]
    peak = eq_values[0] if eq_values else initial_capital
    max_dd = 0.0
    for v in eq_values:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    stats = {
        "risk_enabled": True,
        "n_stop_exits": n_stop_exits,
        "n_rebalances": len(rebalance_dates) - 1,
        "live_mdd": max_dd,
        "equity_curve": equity_curve,
    }

    return total_pnl, all_trades, stats


def _buy_and_hold_pnl(picks_df, signal_date, mtm_close_map, initial_capital,
                      weighting_scheme, risk, apply_weighting_fn=None):
    """退化为买入持有 (信号日=估值日时使用)"""
    total_pnl = 0.0
    stock_details = []
    stock_weights = (apply_weighting_fn(picks_df, weighting_scheme)
                     if apply_weighting_fn else np.ones(len(picks_df)) / max(len(picks_df), 1))
    for idx, srow in picks_df.iterrows():
        code = srow["stock_code"]
        w = float(stock_weights[idx]) if idx < len(stock_weights) else 1.0 / max(len(picks_df), 1)
        buy_p = float(srow["close_price_adj"])
        mtm_p = mtm_close_map.get(code, buy_p)
        stock_ret = mtm_p / buy_p - 1.0 if buy_p > 0 else 0.0
        contribution = w * stock_ret
        total_pnl += contribution
        shares = int(initial_capital * w / buy_p / 100) * 100 if buy_p > 0 else 0
        stock_details.append({
            "code": code, "weight": w, "buy_price": buy_p, "mtm_price": mtm_p,
            "return": stock_ret, "contribution": contribution,
            "score": float(srow["composite_score"]),
            "shares": shares, "cost_value": shares * buy_p, "current_value": shares * mtm_p,
            "entry_date": str(signal_date.date()), "exit_date": str(signal_date.date()),
            "exit_reason": "end_of_window", "stop_hit": False,
        })
    stats = {"risk_enabled": False, "n_stop_exits": 0, "n_rebalances": 0, "live_mdd": 0.0}
    return total_pnl, stock_details, stats
