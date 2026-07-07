"""V5.1 integrated pipeline — the pure-algorithm tight loop (no LLM inside).

Ties together A1-A5 + validation gates into one trustworthy-verdict run:
  factor library hypothesis  (curated offline; A17)
    -> IC-adaptive weights    (A2)
    -> multi-objective NSGA-II HPO over structural params  (A3)
    -> pick from Pareto front under a drawdown limit
    -> holdout backtest with IC weights + risk overlays    (A5)
    -> index-relative metrics on the holdout               (A4)
    -> validation gates: null test + deflated return + overfitting (existing)
    -> verdict: trustworthy or not (index-relative IR primary).

Look-ahead safety: IC weights are causal (A2 shifts by forward_days); the holdout
window is scored once with weights/params fitted on development data only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd

from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .hpo import HyperParamSpace, multi_objective_optimize, select_from_pareto
from .hypothesis import FactorHypothesis
from .ic_weighting import add_forward_return, compute_ic_panel, ic_adaptive_weights, weights_as_of
from .null_test import run_null_test
from .overfitting import OverfittingInputs, deflate_return, overfitting_score
from .relative_eval import RelativeAcceptance, RelativeMetrics, passes_relative, relative_metrics
from .risk_overlay import RiskOverlay
from .walk_forward import split_three_year_window


def load_backtest_frame(
    db_path: str,
    factors: List[str],
    universe: Optional[List[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Assemble a backtest frame from factor_panel + market_daily price.

    Returns columns: stock_code, trade_date, close_price_adj, vol_20d, <factors>.
    """
    con = duckdb.connect(db_path, read_only=True)
    cols = ", ".join(f"fp.{f}" for f in factors)
    where = []
    if start:
        where.append(f"m.trade_date >= DATE '{start}'")
    if end:
        where.append(f"m.trade_date <= DATE '{end}'")
    if universe:
        codes = ",".join(f"'{c}'" for c in universe)
        where.append(f"m.stock_code IN ({codes})")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    df = con.execute(f"""
        SELECT m.stock_code, m.trade_date, m.close_adj AS close_price_adj,
               fp.vol_20d, {cols}
        FROM market_daily m
        JOIN factor_panel fp ON fp.stock_code = m.stock_code AND fp.trade_date = m.trade_date
        {clause}
        ORDER BY m.trade_date, m.stock_code
    """).fetchdf()
    con.close()
    return df


@dataclass
class TrustworthyReport:
    hypothesis_factors: List[str]
    pareto_size: int
    selected_top_n: Optional[int]
    selected_rebalance_days: Optional[int]
    dev_return: Optional[float]
    dev_drawdown: Optional[float]
    holdout_return: Optional[float]
    holdout_drawdown: Optional[float]
    relative: Optional[Dict[str, Any]]
    null_pass_rate: Optional[float]
    deflated_holdout_return: Optional[float]
    overfitting: Optional[float]
    trustworthy: bool = False
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        return d


def run_v51_pipeline(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    end_date: date,
    benchmark_df: Optional[pd.DataFrame] = None,
    relative_criteria: Optional[RelativeAcceptance] = None,
    max_drawdown_limit: float = 0.30,
    forward_days: int = 20,
    n_trials: int = 40,
    n_folds: int = 3,
    seed: int = 0,
    cost_model: Optional[CostModel] = None,
    risk: Optional[RiskOverlay] = None,
    run_null: bool = True,
    null_runs: int = 3,
    null_pass_threshold: float = 0.34,
    overfitting_threshold: float = 0.6,
) -> TrustworthyReport:
    factor_names = [f.source_field for f in hypothesis.factors]
    relative_criteria = relative_criteria or RelativeAcceptance()
    cost_model = cost_model or CostModel.for_market(hypothesis.market)

    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    split = split_three_year_window(end_date)
    dev = frame[(frame["trade_date"] >= pd.Timestamp(split.development_start))
                & (frame["trade_date"] <= pd.Timestamp(split.development_end))]
    holdout = frame[(frame["trade_date"] >= pd.Timestamp(split.holdout_start))
                    & (frame["trade_date"] <= pd.Timestamp(split.holdout_end))]

    # A2: causal IC-adaptive weights over the whole frame (shift enforces no look-ahead)
    price = frame[["stock_code", "trade_date", "close_price_adj"]]
    panel_fwd = add_forward_return(frame, price, forward_days=forward_days, price_col="close_price_adj")
    ic = compute_ic_panel(panel_fwd, factor_names)
    weights = ic_adaptive_weights(ic, forward_days=forward_days)

    def wp(d: pd.Timestamp) -> Dict[str, float]:
        w = weights_as_of(weights, d)
        # map factor source_field weights onto factor names used by composite_scores
        return {f.name: w.get(f.source_field, w.get(f.name, 0.0)) for f in hypothesis.factors}

    # A3: multi-objective HPO on development data
    front = multi_objective_optimize(
        dev, hypothesis, space, n_trials=n_trials, seed=seed, n_folds=n_folds,
        cost_model=cost_model, weights_provider=wp,
    )
    pick = select_from_pareto(front, max_drawdown_limit)
    reasons: List[str] = []
    if pick is None:
        return TrustworthyReport(
            hypothesis_factors=factor_names, pareto_size=0, selected_top_n=None,
            selected_rebalance_days=None, dev_return=None, dev_drawdown=None,
            holdout_return=None, holdout_drawdown=None, relative=None,
            null_pass_rate=None, deflated_holdout_return=None, overfitting=None,
            trustworthy=False, reasons=["empty Pareto front"],
        )

    # holdout backtest (one shot) with IC weights + risk overlay; capture the equity
    # curve so the index-relative metrics use the exact same path (incl. risk overlays)
    holdout_bt, holdout_equity = run_factor_backtest(
        holdout, hypothesis, pick.config, cost_model=cost_model, weights_provider=wp,
        risk=risk, return_equity_curve=True,
    )

    # A4: index-relative metrics on holdout (if a benchmark is provided)
    relative_dict: Optional[Dict[str, Any]] = None
    rel_metrics: Optional[RelativeMetrics] = None
    if benchmark_df is not None and holdout_bt.trade_count > 0:
        rel_metrics = relative_metrics(holdout_equity, benchmark_df)
        relative_dict = passes_relative(rel_metrics, relative_criteria)

    # gates
    null_rate = None
    if run_null:
        # meaningful null test: can shuffled factors match the strategy's own dev return?
        null_bar = max(0.0, float(pick.oos_return))
        null_rate = run_null_test(
            dev, hypothesis, space, _abs_criteria(max_drawdown_limit, min_return=null_bar),
            n_runs=null_runs, n_trials=max(5, n_trials // 4), cost_model=cost_model,
        ).pass_rate
    deflated = deflate_return(holdout_bt.annualized_return, n_trials)
    overfit = overfitting_score(OverfittingInputs(
        outer_iterations=1, total_trials=n_trials,
        hp_dimensions=2, trade_count=holdout_bt.trade_count,
        dev_return=pick.oos_return, holdout_return=holdout_bt.annualized_return,
    ))

    # verdict: index-relative IR primary, plus the anti-overfit gates
    trustworthy = True
    if relative_dict is not None:
        if not relative_dict["passed"]:
            trustworthy = False
            reasons.append("relative gate failed: " + ",".join(relative_dict["failed_checks"]))
    else:
        trustworthy = False
        reasons.append("no benchmark -> cannot judge index-relative (primary gate)")
    if null_rate is not None and null_rate > null_pass_threshold:
        trustworthy = False
        reasons.append(f"null test pass-rate {null_rate:.2f} > {null_pass_threshold}")
    if overfit > overfitting_threshold:
        trustworthy = False
        reasons.append(f"overfitting score {overfit:.2f} > {overfitting_threshold}")
    if not reasons:
        reasons.append("passed index-relative + null + overfitting gates")

    return TrustworthyReport(
        hypothesis_factors=factor_names, pareto_size=len(front),
        selected_top_n=pick.config.top_n, selected_rebalance_days=pick.config.rebalance_days,
        dev_return=pick.oos_return, dev_drawdown=pick.max_drawdown,
        holdout_return=holdout_bt.annualized_return, holdout_drawdown=holdout_bt.max_drawdown,
        relative=relative_dict, null_pass_rate=null_rate,
        deflated_holdout_return=deflated, overfitting=overfit,
        trustworthy=trustworthy, reasons=reasons,
    )


def _abs_criteria(max_drawdown_limit: float, min_return: float = 0.0):
    from .evaluation import AcceptanceCriteria
    return AcceptanceCriteria(
        min_annualized_return=min_return, max_drawdown_limit=max_drawdown_limit, min_trade_count=1
    )
