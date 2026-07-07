"""A4 — Index-relative evaluation.

Locked decision (2026-06-28): a strategy is judged primarily on its performance
RELATIVE to a benchmark index (alpha / information ratio), not absolute return —
so a bull market's beta is not mistaken for skill. Absolute return stays as a
secondary reference.

Pure functions here (no network); benchmark.py supplies the index series.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict

import pandas as pd

TRADING_DAYS = 252


@dataclass
class RelativeMetrics:
    strategy_return: float        # absolute total return (reference)
    benchmark_return: float       # benchmark total return over the same dates
    excess_return: float          # strategy_return - benchmark_return (total alpha)
    annualized_excess: float      # annualized mean daily excess
    tracking_error: float         # annualized stddev of daily excess
    information_ratio: float       # annualized_excess / tracking_error
    excess_max_drawdown: float    # max drawdown of the cumulative excess curve
    win_rate_vs_benchmark: float  # fraction of days strategy beat benchmark
    n_days: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def relative_metrics(equity_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> RelativeMetrics:
    """Compute index-relative metrics by aligning a strategy equity curve with a
    benchmark level series on shared dates.

    equity_df: columns [trade_date, equity]
    benchmark_df: columns [trade_date, close]
    """
    eq = equity_df[["trade_date", "equity"]].copy()
    bm = benchmark_df[["trade_date", "close"]].copy()
    eq["trade_date"] = pd.to_datetime(eq["trade_date"])
    bm["trade_date"] = pd.to_datetime(bm["trade_date"])
    merged = eq.merge(bm, on="trade_date", how="inner").sort_values("trade_date").reset_index(drop=True)
    n = len(merged)
    if n < 2:
        return RelativeMetrics(0, 0, 0, 0, 0, 0, 0, 0, n)

    merged["strat_ret"] = merged["equity"].pct_change()
    merged["bench_ret"] = merged["close"].pct_change()
    merged = merged.dropna(subset=["strat_ret", "bench_ret"])
    excess = merged["strat_ret"] - merged["bench_ret"]

    strat_total = merged["equity"].iloc[-1] / merged["equity"].iloc[0] - 1.0
    bench_total = merged["close"].iloc[-1] / merged["close"].iloc[0] - 1.0
    # Annualize using the actual date span rather than assuming daily frequency.
    # The equity curve may be at rebalance frequency (e.g. every 20 trading days);
    # a fixed TRADING_DAYS=252 multiplier would inflate IR by ~sqrt(freq) when the
    # curve is sub-daily. periods_per_year = calendar_days_per_year * n_periods / span.
    span_days = (merged["trade_date"].iloc[-1] - merged["trade_date"].iloc[0]).days
    n_periods = max(len(merged) - 1, 1)
    ppy = (365.25 * n_periods / span_days) if span_days > 0 else float(TRADING_DAYS)
    ann_excess = float(excess.mean() * ppy)
    te = float(excess.std(ddof=0) * math.sqrt(ppy))
    ir = 0.0 if te == 0 else ann_excess / te

    excess_curve = (1.0 + excess).cumprod()
    running_max = excess_curve.cummax()
    excess_dd = float((excess_curve / running_max - 1.0).min())

    return RelativeMetrics(
        strategy_return=float(strat_total),
        benchmark_return=float(bench_total),
        excess_return=float(strat_total - bench_total),
        annualized_excess=ann_excess,
        tracking_error=te,
        information_ratio=float(ir),
        excess_max_drawdown=abs(excess_dd),
        win_rate_vs_benchmark=float((excess > 0).mean()),
        n_days=int(len(merged)),
    )


@dataclass
class RelativeAcceptance:
    min_information_ratio: float = 0.5
    min_excess_return: float = 0.0
    # absolute reference floor (secondary)
    min_absolute_return: float = 0.0


def passes_relative(metrics: RelativeMetrics, criteria: RelativeAcceptance) -> Dict[str, Any]:
    failed = []
    if metrics.information_ratio < criteria.min_information_ratio:
        failed.append("information_ratio")
    if metrics.excess_return < criteria.min_excess_return:
        failed.append("excess_return")
    if metrics.strategy_return < criteria.min_absolute_return:
        failed.append("absolute_return")
    return {
        "passed": not failed,
        "failed_checks": failed,
        "metrics": metrics.to_dict(),
        "thresholds": asdict(criteria),
    }
