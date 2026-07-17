"""Weighted backtest engine — 支持多种非等权分配方案.

基于 factor_backtest.py 修改，添加 weighting_scheme 参数：
- equal: 等权（原始基准）
- rank_linear: 排名线性递减（第1名权重最大）
- rank_power: 排名幂律递减（alpha控制集中度）
- score_softmax: 得分softmax加权（tau控制温度）
- hybrid: 前半加重，后半减轻
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_backtest import _execution_price, _next_execution_date
from .factor_scoring import composite_scores, select_top_n
from .hypothesis import FactorConfig, FactorHypothesis
from .risk_overlay import RiskOverlay, apply_trailing_stop, position_scales

WeightsProvider = Callable[[pd.Timestamp], Dict[str, float]]


def compute_weights(
    scores: np.ndarray,
    scheme: str,
    alpha: float = 1.0,
    tau: float = 1.0,
    vols: np.ndarray = None,
) -> np.ndarray:
    """根据综合得分和加权方案计算各股权重.

    Args:
        scores: 已排序的综合得分数组（降序，第0名最好）
        scheme: 加权方案
        alpha: 幂律指数（rank_power / hybrid_ratio 使用）
        tau: 温度参数（score_softmax使用）

    Returns:
        权重数组（和为1.0）
    """
    n = len(scores)
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])

    if scheme == "equal":
        return np.ones(n) / n

    elif scheme == "rank_linear":
        ranks = np.arange(n, 0, -1, dtype=float)
        return ranks / ranks.sum()

    elif scheme == "rank_linear_floor":
        # 线性递减但有保底: max(linear, floor_ratio * equal)
        # floor_ratio由alpha控制, alpha=0.3 → 最小权重=0.3/n
        ranks = np.arange(n, 0, -1, dtype=float)
        linear = ranks / ranks.sum()
        floor = alpha / n
        weights = np.maximum(linear, floor)
        return weights / weights.sum()

    elif scheme == "rank_power":
        ranks = np.arange(n, 0, -1, dtype=float)
        powered = ranks ** alpha
        return powered / powered.sum()

    elif scheme == "score_softmax":
        s = scores - scores.max()
        exp_s = np.exp(s / tau)
        return exp_s / exp_s.sum()

    elif scheme == "hybrid":
        half = n // 2
        weights = np.ones(n)
        weights[:half] = 1.5
        weights[half:] = 0.5
        return weights / weights.sum()

    elif scheme == "hybrid_ratio":
        # 可调比例: 前半alpha, 后半(2-alpha), alpha由参数控制
        # alpha=1.5 → 原hybrid, alpha=1.3 → 温和, alpha=1.0 → 等权
        half = n // 2
        weights = np.ones(n)
        weights[:half] = alpha
        weights[half:] = 2.0 - alpha
        return weights / weights.sum()

    elif scheme == "inv_vol":
        # 反波动率加权 (risk parity lite)
        # 需要vols数组, 如果没有则退化为等权
        if vols is None or np.all(vols == 0) or len(vols) != n:
            return np.ones(n) / n
        inv_v = 1.0 / np.maximum(vols, 1e-8)
        return inv_v / inv_v.sum()

    elif scheme == "inv_vol_hr12":
        # 混合: 先inv_vol再hr12倾斜 (前半1.2x后半0.8x)
        if vols is None or np.all(vols == 0) or len(vols) != n:
            return np.ones(n) / n
        inv_v = 1.0 / np.maximum(vols, 1e-8)
        weights = inv_v
        half = n // 2
        weights[:half] *= 1.2
        weights[half:] *= 0.8
        return weights / weights.sum()

    elif scheme == "inv_vol_hr13":
        # 混合: 先inv_vol再hr13倾斜 (前半1.3x后半0.7x)
        if vols is None or np.all(vols == 0) or len(vols) != n:
            return np.ones(n) / n
        inv_v = 1.0 / np.maximum(vols, 1e-8)
        weights = inv_v
        half = n // 2
        weights[:half] *= 1.3
        weights[half:] *= 0.7
        return weights / weights.sum()

    else:
        return np.ones(n) / n


def run_weighted_backtest(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    cost_model: CostModel | None = None,
    initial_capital: float = 1_000_000.0,
    weights_provider: Optional[WeightsProvider] = None,
    risk: Optional[RiskOverlay] = None,
    return_equity_curve: bool = False,
    weighting_scheme: str = "equal",
    weight_alpha: float = 1.0,
    weight_tau: float = 1.0,
):
    """加权回测 — 与 run_factor_backtest 相同但支持非等权分配。"""
    costs = cost_model if cost_model is not None else CostModel()
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    all_dates = [pd.Timestamp(d) for d in sorted(frame["trade_date"].unique())]

    # rebalance dates
    step = config.rebalance_days
    if step < 1:
        step = 1
    rebalance_dates = list(all_dates[::step])
    if len(rebalance_dates) < 2 and len(all_dates) >= 2:
        rebalance_dates = [all_dates[0], all_dates[-1]]

    equity = initial_capital
    equity_points = [{"trade_date": all_dates[0], "equity": equity}]
    trade_count = 0
    period_returns: List[float] = []

    for i in range(len(rebalance_dates) - 1):
        entry_date = rebalance_dates[i]
        exit_date = rebalance_dates[i + 1]
        entry_exec_date = _next_execution_date(all_dates, entry_date)
        exit_exec_date = _next_execution_date(all_dates, exit_date)
        exit_prefers_open = True
        if exit_exec_date is None:
            exit_exec_date = exit_date
            exit_prefers_open = False
        if entry_exec_date is None or entry_exec_date >= exit_exec_date:
            continue
        entry_rows = frame.loc[frame["trade_date"] == entry_date]
        weights = weights_provider(entry_date) if weights_provider is not None else config.weights
        scored = composite_scores(
            entry_rows, hypothesis.factors, weights, sector_neutral=hypothesis.sector_neutral
        )
        picks = select_top_n(scored, config.top_n)
        if picks.empty:
            equity_points.append({"trade_date": exit_date, "equity": equity})
            continue

        # ── 核心：计算非等权权重 ──
        scores = picks["composite_score"].values
        vols = picks["vol_20d"].values if "vol_20d" in picks.columns else None
        stock_weights = compute_weights(scores, weighting_scheme, weight_alpha, weight_tau, vols=vols)

        # 叠加波动率风险控制（如果启用）
        if risk is not None and risk.vol_position_enabled and "vol_20d" in picks.columns:
            vol_scales = position_scales(list(picks["vol_20d"]), risk)
            stock_weights = stock_weights * np.array(vol_scales)

        total_w = stock_weights.sum()
        if total_w <= 0:
            stock_weights = np.ones(len(picks)) / len(picks)
            total_w = 1.0

        period_equity = 0.0
        for (idx, pick), sw in zip(picks.iterrows(), stock_weights):
            slot_capital = equity * sw / total_w
            code = pick["stock_code"]
            entry_price = _execution_price(
                frame.loc[(frame["trade_date"] == entry_exec_date) & (frame["stock_code"] == code)]
            )
            if entry_price is None:
                period_equity += slot_capital
                continue

            if risk is not None and risk.trailing_stop_enabled:
                path = (
                    frame.loc[
                        (frame["stock_code"] == code)
                        & (frame["trade_date"] >= entry_exec_date)
                        & (frame["trade_date"] <= exit_exec_date)
                    ]
                    .sort_values("trade_date")["close_price_adj"]
                    .astype(float)
                    .tolist()
                )
                if len(path) < 2 or entry_price <= 0:
                    period_equity += slot_capital
                    continue
                raw_exit_price, _ = apply_trailing_stop(path, entry_price, risk)
            else:
                raw_exit_price = _execution_price(
                    frame.loc[(frame["trade_date"] == exit_exec_date) & (frame["stock_code"] == code)],
                    prefer_open=exit_prefers_open,
                )
                if raw_exit_price is None or entry_price <= 0:
                    period_equity += slot_capital
                    continue

            fill_entry = costs.entry_fill_price(entry_price)
            fill_exit = costs.exit_fill_price(raw_exit_price)
            shares = (slot_capital - costs.commission(slot_capital)) / fill_entry
            proceeds = shares * fill_exit
            proceeds -= costs.commission(proceeds)
            period_equity += proceeds
            trade_count += 1

        period_returns.append((period_equity / equity) - 1.0 if equity else 0.0)
        equity = period_equity
        equity_points.append({"trade_date": exit_date, "equity": equity})

    equity_df = pd.DataFrame(equity_points).sort_values("trade_date").reset_index(drop=True)
    equity_df["cummax"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = equity_df["equity"] / equity_df["cummax"] - 1.0
    equity_df["ret"] = equity_df["equity"].pct_change().fillna(0.0)

    total_return = (equity / initial_capital) - 1.0
    num_days = max(len(all_dates), 1)
    annualized_return = (equity / initial_capital) ** (252 / num_days) - 1.0
    std = float(equity_df["ret"].std(ddof=0))
    sharpe = 0.0 if std == 0 else float(equity_df["ret"].mean() / std * math.sqrt(252))
    win_rate = 0.0 if not period_returns else float(sum(r > 0 for r in period_returns) / len(period_returns))

    result = BacktestResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        spec_id=f"factor-{hypothesis.market}",
        strategy_id=f"factor-{hypothesis.market}",
        start_date=pd.Timestamp(all_dates[0]).strftime("%Y-%m-%d"),
        end_date=pd.Timestamp(all_dates[-1]).strftime("%Y-%m-%d"),
        trade_count=trade_count,
        trade_win_rate=win_rate,
        annualized_return=float(annualized_return),
        total_return=float(total_return),
        max_drawdown=float(abs(equity_df["drawdown"].min())),
        sharpe=sharpe,
        average_holding_days=float(config.rebalance_days),
        equity_curve_points=len(equity_df),
        notes=[f"Weighted backtest ({weighting_scheme}) with periodic rebalance and transaction costs."],
        trades=[],
    )
    if return_equity_curve:
        return result, equity_df[["trade_date", "equity"]].copy()
    return result
