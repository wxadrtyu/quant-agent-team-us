from __future__ import annotations

import math
from datetime import datetime
from typing import Callable, Dict, List, Optional

import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_scoring import composite_scores, select_top_n
from .hypothesis import FactorConfig, FactorHypothesis
from .risk_overlay import RiskOverlay, apply_trailing_stop, position_scales

# A weights provider returns {factor_name: weight} for a given rebalance date.
# Used to plug in time-varying IC-adaptive weights (A2). When None, the fixed
# config.weights are used (original behaviour, preserved).
WeightsProvider = Callable[[pd.Timestamp], Dict[str, float]]


def _rebalance_dates(dates: List[pd.Timestamp], step: int) -> List[pd.Timestamp]:
    """Rebalance dates spaced `step` apart, always including the first date.

    A segment shorter than `step` trading days must still trade at least once
    (build a position at the start, hold to the end). Previously `dates[::step]`
    returned only [dates[0]] for short segments, making the main loop's
    `range(len-1)` empty -> zero trades -> fake 0.0 return."""
    if step < 1:
        step = 1
    rd = list(dates[::step])
    # ensure at least two points (entry + exit) so a position is always taken
    if len(rd) < 2 and len(dates) >= 2:
        rd = [dates[0], dates[-1]]
    return rd


def _next_execution_date(dates: List[pd.Timestamp], signal_date: pd.Timestamp) -> Optional[pd.Timestamp]:
    try:
        idx = dates.index(signal_date)
    except ValueError:
        return None
    next_idx = idx + 1
    return dates[next_idx] if next_idx < len(dates) else None


def _execution_price(rows: pd.DataFrame, prefer_open: bool = True) -> Optional[float]:
    if rows.empty:
        return None
    row = rows.iloc[0]
    price = row.get("open_price") if prefer_open and "open_price" in rows.columns else None
    if pd.isna(price) or price is None:
        price = row.get("close_price_adj")
    if pd.isna(price) or price is None:
        return None
    return float(price)


def run_factor_backtest(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    cost_model: CostModel | None = None,
    initial_capital: float = 1_000_000.0,
    weights_provider: Optional[WeightsProvider] = None,
    risk: Optional[RiskOverlay] = None,
    return_equity_curve: bool = False,
):
    """Run a linear composite factor backtest.

    Returns a BacktestResult, or (BacktestResult, equity_df[trade_date, equity]) when
    return_equity_curve=True (used by the v5.1 pipeline for index-relative metrics so the
    curve matches the backtest exactly, including risk overlays)."""
    costs = cost_model if cost_model is not None else CostModel()
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    all_dates = [pd.Timestamp(d) for d in sorted(frame["trade_date"].unique())]
    rebalance_dates = _rebalance_dates(all_dates, config.rebalance_days)

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

        # A5 volatility-based position sizing: unequal slots when enabled, else equal
        if risk is not None and risk.vol_position_enabled and "vol_20d" in picks.columns:
            scales = position_scales(list(picks["vol_20d"]), risk)
        else:
            scales = [1.0] * len(picks)
        total_scale = sum(scales) or float(len(picks))

        period_equity = 0.0
        for (_, pick), scale in zip(picks.iterrows(), scales):
            slot_capital = equity * scale / total_scale
            code = pick["stock_code"]
            entry_price = _execution_price(
                frame.loc[(frame["trade_date"] == entry_exec_date) & (frame["stock_code"] == code)]
            )
            if entry_price is None:
                period_equity += slot_capital
                continue
            # A5 trailing stop: walk the position's daily path entry->exit
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
        notes=["Linear composite factor model with periodic rebalance and transaction costs."],
        trades=[],
    )
    if return_equity_curve:
        return result, equity_df[["trade_date", "equity"]].copy()
    return result
