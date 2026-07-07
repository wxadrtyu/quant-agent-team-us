"""A6 — Monthly rolling re-optimization (walk-forward deployment).

Mirrors the successful case's reopt_*_<month> series: at each month start, refit
(IC-adaptive weights + multi-objective HPO over structural params) using only data
up to that month, then DEPLOY to the next month. Each next-month segment is pure
out-of-sample; stitched together they form a true OOS equity curve — stronger
evidence than a single holdout.

No look-ahead: each refit uses frame rows with trade_date < as_of only; IC weights
are causal (A2 shift).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .hpo import HyperParamSpace, multi_objective_optimize, select_from_pareto
from .hypothesis import FactorHypothesis
from .ic_weighting import add_forward_return, compute_ic_panel, ic_adaptive_weights, weights_as_of
from .risk_overlay import RiskOverlay


@dataclass
class ReoptSnapshot:
    as_of: str
    top_n: Optional[int]
    rebalance_days: Optional[int]
    segment_return: float       # realised OOS return for the deployed month
    segment_start: str
    segment_end: str


@dataclass
class RollingResult:
    snapshots: List[ReoptSnapshot]
    oos_equity: pd.DataFrame    # stitched out-of-sample equity curve [trade_date, equity]
    oos_total_return: float
    months: int = 0
    notes: List[str] = field(default_factory=list)


def _month_starts(dates: List[pd.Timestamp]) -> List[pd.Timestamp]:
    s = pd.Series(sorted(set(dates)))
    # first trading day of each (year, month)
    grp = s.groupby([s.dt.year, s.dt.month]).min()
    return list(grp.sort_values())


def rolling_reoptimize(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    lookback_months: int = 24,
    max_drawdown_limit: float = 0.30,
    forward_days: int = 20,
    n_trials: int = 20,
    n_folds: int = 3,
    seed: int = 0,
    cost_model: Optional[CostModel] = None,
    risk: Optional[RiskOverlay] = None,
    min_train_months: int = 12,
    weighting_scheme: str = "equal",
    weight_alpha: float = 1.0,
) -> RollingResult:
    cost_model = cost_model or CostModel.for_market(hypothesis.market)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])

    # global causal IC weights (shift => safe to compute once over the whole frame)
    price = frame[["stock_code", "trade_date", "close_price_adj"]]
    panel_fwd = add_forward_return(frame, price, forward_days=forward_days, price_col="close_price_adj")
    ic = compute_ic_panel(panel_fwd, [f.source_field for f in hypothesis.factors])
    weights = ic_adaptive_weights(ic, forward_days=forward_days)

    def wp(d: pd.Timestamp) -> Dict[str, float]:
        w = weights_as_of(weights, d)
        return {f.name: w.get(f.source_field, w.get(f.name, 0.0)) for f in hypothesis.factors}

    months = _month_starts(list(frame["trade_date"].unique()))
    snapshots: List[ReoptSnapshot] = []
    segments: List[pd.DataFrame] = []
    equity = 1_000_000.0
    stitched = []

    for i in range(min_train_months, len(months) - 1):
        as_of = months[i]
        seg_start, seg_end = months[i], months[i + 1]
        train = frame[(frame["trade_date"] < as_of)
                      & (frame["trade_date"] >= as_of - pd.DateOffset(months=lookback_months))]
        if train.empty:
            continue
        front = multi_objective_optimize(
            train, hypothesis, space, n_trials=n_trials, seed=seed, n_folds=n_folds,
            cost_model=cost_model, weights_provider=wp,
        )
        pick = select_from_pareto(front, max_drawdown_limit)
        if pick is None:
            continue
        seg = frame[(frame["trade_date"] >= seg_start) & (frame["trade_date"] < seg_end)]
        if seg.empty:
            continue
        if weighting_scheme != "equal":
            from .weighted_backtest import run_weighted_backtest
            bt, eq = run_weighted_backtest(
                seg, hypothesis, pick.config, cost_model=cost_model, weights_provider=wp,
                risk=risk, return_equity_curve=True,
                weighting_scheme=weighting_scheme, weight_alpha=weight_alpha,
            )
        else:
            bt, eq = run_factor_backtest(
                seg, hypothesis, pick.config, cost_model=cost_model, weights_provider=wp,
                risk=risk, return_equity_curve=True,
            )
        snapshots.append(ReoptSnapshot(
            as_of=str(as_of.date()), top_n=pick.config.top_n, rebalance_days=pick.config.rebalance_days,
            segment_return=float(bt.total_return), segment_start=str(seg_start.date()),
            segment_end=str(seg_end.date()),
        ))
        # stitch: scale this segment's normalized curve onto the running equity
        eq = eq.sort_values("trade_date").reset_index(drop=True)
        base = eq["equity"].iloc[0]
        for _, r in eq.iterrows():
            stitched.append({"trade_date": r["trade_date"], "equity": equity * (r["equity"] / base)})
        equity = equity * (1.0 + float(bt.total_return))
        segments.append(eq)

    oos_equity = pd.DataFrame(stitched) if stitched else pd.DataFrame(columns=["trade_date", "equity"])
    oos_total = (equity / 1_000_000.0 - 1.0) if stitched else 0.0
    return RollingResult(
        snapshots=snapshots, oos_equity=oos_equity, oos_total_return=oos_total,
        months=len(snapshots),
        notes=[f"{len(snapshots)} monthly OOS segments stitched into a walk-forward curve"],
    )
