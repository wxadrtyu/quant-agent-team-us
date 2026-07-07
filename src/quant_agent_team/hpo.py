from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import optuna
import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .evaluation import AcceptanceCriteria, EvaluationResult, evaluate_strategy
from .factor_backtest import run_factor_backtest
from .hypothesis import FactorConfig, FactorHypothesis
from .walk_forward import purged_walk_forward

PENALTY = -1.0e9


def walk_forward_objective(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    n_folds: int = 3,
    embargo: int = 1,
    max_drawdown_limit: float = 0.30,
    min_trade_count: int = 1,
    cost_model: CostModel | None = None,
) -> float:
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    all_dates = sorted(pd.Timestamp(d).date() for d in frame["trade_date"].unique())
    folds = purged_walk_forward(all_dates, n_folds=n_folds, embargo=embargo)
    if not folds:
        return PENALTY

    oos_returns: List[float] = []
    total_trades = 0
    for fold in folds:
        test_set = {pd.Timestamp(d) for d in fold.test}
        test_frame = frame.loc[frame["trade_date"].isin(test_set)]
        if test_frame.empty:
            continue
        result = run_factor_backtest(test_frame, hypothesis, config, cost_model=cost_model)
        if result.max_drawdown > max_drawdown_limit:
            return PENALTY
        oos_returns.append(result.annualized_return)
        total_trades += result.trade_count

    if not oos_returns or total_trades < min_trade_count:
        return PENALTY
    return float(sum(oos_returns) / len(oos_returns))


@dataclass
class HyperParamSpace:
    top_n_choices: list
    rebalance_days_choices: list
    weight_low: float = 0.0
    weight_high: float = 1.0


@dataclass
class HpoResult:
    best_config: FactorConfig
    best_score: float
    n_trials: int


def optimize(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    n_trials: int = 20,
    seed: int = 0,
    n_folds: int = 3,
    cost_model: CostModel | None = None,
) -> HpoResult:
    def _suggest(trial: "optuna.Trial") -> FactorConfig:
        weights: Dict[str, float] = {
            factor.name: trial.suggest_float(f"w_{factor.name}", space.weight_low, space.weight_high)
            for factor in hypothesis.factors
        }
        top_n = trial.suggest_categorical("top_n", space.top_n_choices)
        rebalance_days = trial.suggest_categorical("rebalance_days", space.rebalance_days_choices)
        return FactorConfig(weights=weights, top_n=top_n, rebalance_days=rebalance_days)

    def _objective(trial: "optuna.Trial") -> float:
        config = _suggest(trial)
        return walk_forward_objective(frame, hypothesis, config, n_folds=n_folds, cost_model=cost_model)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(_objective, n_trials=n_trials)

    best = study.best_trial
    weights = {factor.name: best.params[f"w_{factor.name}"] for factor in hypothesis.factors}
    best_config = FactorConfig(
        weights=weights, top_n=best.params["top_n"], rebalance_days=best.params["rebalance_days"]
    )
    return HpoResult(best_config=best_config, best_score=float(best.value), n_trials=len(study.trials))


@dataclass
class SearchResult:
    hpo: HpoResult
    development_result: BacktestResult
    evaluation: EvaluationResult


def search_strategy(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    n_trials: int = 20,
    seed: int = 0,
    n_folds: int = 3,
    cost_model: CostModel | None = None,
) -> SearchResult:
    hpo = optimize(
        frame, hypothesis, space, n_trials=n_trials, seed=seed, n_folds=n_folds, cost_model=cost_model
    )
    development_result = run_factor_backtest(frame, hypothesis, hpo.best_config, cost_model=cost_model)
    evaluation = evaluate_strategy(development_result, criteria)
    return SearchResult(hpo=hpo, development_result=development_result, evaluation=evaluation)


# ---------------------------------------------------------------------------
# A3 — Multi-objective HPO (NSGA-II). Locked decision (2026-06-28):
#   * objectives = (MAXIMIZE walk-forward OOS return, MINIMIZE OOS max drawdown)
#     -> a Pareto front of return/risk trade-offs, not one return-max point.
#   * HPO tunes STRUCTURAL params only (top_n, rebalance_days). Factor WEIGHTS
#     come from IC-adaptive weighting (weights_provider), never searched here —
#     that is exactly what overfit in the colleague's 3fopt.
# ---------------------------------------------------------------------------
from typing import Callable, Dict, List, Optional, Tuple  # noqa: E402

PARETO_PENALTY: Tuple[float, float] = (-1.0e9, 1.0e9)


def _equal_weights(hypothesis: FactorHypothesis) -> Dict[str, float]:
    return {f.name: 1.0 for f in hypothesis.factors}


def walk_forward_multi_objective(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    n_folds: int = 3,
    embargo: int = 1,
    cost_model: CostModel | None = None,
    weights_provider: Optional[Callable] = None,
    _folds_cache: Optional[List] = None,
) -> Tuple[float, float]:
    """Return (mean OOS annualised return, worst OOS max drawdown) across folds.

    Performance: callers that invoke this many times (e.g. HPO) should pass
    `_folds_cache` (precomputed folds + a date-parsed frame) so the per-trial
    copy/to_datetime/fold-split work is done once instead of N times. The cache
    is a list of (test_set, test_frame) tuples. Results are identical with or
    without the cache (verified by test_hpo_multiobjective).
    """
    if _folds_cache is not None:
        folds_frames = _folds_cache
    else:
        frame = frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        all_dates = sorted(pd.Timestamp(d).date() for d in frame["trade_date"].unique())
        folds = purged_walk_forward(all_dates, n_folds=n_folds, embargo=embargo)
        if not folds:
            return PARETO_PENALTY
        folds_frames = []
        for fold in folds:
            test_set = {pd.Timestamp(d) for d in fold.test}
            test_frame = frame.loc[frame["trade_date"].isin(test_set)]
            if not test_frame.empty:
                folds_frames.append(test_frame)
    if not folds_frames:
        return PARETO_PENALTY
    oos_returns: List[float] = []
    worst_dd = 0.0
    total_trades = 0
    for test_frame in folds_frames:
        if test_frame.empty:
            continue
        result = run_factor_backtest(
            test_frame, hypothesis, config, cost_model=cost_model, weights_provider=weights_provider
        )
        oos_returns.append(result.annualized_return)
        worst_dd = max(worst_dd, result.max_drawdown)
        total_trades += result.trade_count
    if not oos_returns or total_trades < 1:
        return PARETO_PENALTY
    return float(sum(oos_returns) / len(oos_returns)), float(worst_dd)


@dataclass
class ParetoPoint:
    config: FactorConfig
    oos_return: float
    max_drawdown: float


def multi_objective_optimize(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    n_trials: int = 40,
    seed: int = 0,
    n_folds: int = 3,
    cost_model: CostModel | None = None,
    weights_provider: Optional[Callable] = None,
) -> List[ParetoPoint]:
    """NSGA-II over structural params; returns the Pareto front of (return, drawdown).

    Performance: precomputes the walk-forward folds once and reuses them across
    all trials (the folds depend only on the frame dates, not on the config).
    This skips a per-trial frame.copy()/to_datetime/fold-split that was repeated
    n_trials times. Output is identical to the uncached version."""

    def _suggest(trial: "optuna.Trial") -> FactorConfig:
        top_n = trial.suggest_categorical("top_n", space.top_n_choices)
        rebalance_days = trial.suggest_categorical("rebalance_days", space.rebalance_days_choices)
        return FactorConfig(weights=_equal_weights(hypothesis), top_n=top_n, rebalance_days=rebalance_days)

    # Precompute folds once (dates don't change across trials, only config does).
    _f = frame.copy()
    _f["trade_date"] = pd.to_datetime(_f["trade_date"])
    _all_dates = sorted(pd.Timestamp(d).date() for d in _f["trade_date"].unique())
    _folds = purged_walk_forward(_all_dates, n_folds=n_folds, embargo=1)
    _folds_cache: List = []
    if _folds:
        for fold in _folds:
            _test_set = {pd.Timestamp(d) for d in fold.test}
            _tf = _f.loc[_f["trade_date"].isin(_test_set)]
            if not _tf.empty:
                _folds_cache.append(_tf)

    def _objective(trial: "optuna.Trial") -> Tuple[float, float]:
        config = _suggest(trial)
        return walk_forward_multi_objective(
            frame, hypothesis, config, n_folds=n_folds, cost_model=cost_model,
            weights_provider=weights_provider, _folds_cache=_folds_cache or None,
        )

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        directions=["maximize", "minimize"],
        sampler=optuna.samplers.NSGAIISampler(seed=seed),
    )
    study.optimize(_objective, n_trials=n_trials)

    front: List[ParetoPoint] = []
    for t in study.best_trials:
        if t.values is None:
            continue
        ret, dd = t.values
        if (ret, dd) == PARETO_PENALTY:
            continue
        cfg = FactorConfig(
            weights=_equal_weights(hypothesis),
            top_n=t.params["top_n"], rebalance_days=t.params["rebalance_days"],
        )
        front.append(ParetoPoint(config=cfg, oos_return=ret, max_drawdown=dd))
    return front


def select_from_pareto(
    front: List[ParetoPoint], max_drawdown_limit: float
) -> Optional[ParetoPoint]:
    """Pick the highest-return point that respects the drawdown limit; if none qualify,
    fall back to the lowest-drawdown point."""
    if not front:
        return None
    eligible = [p for p in front if p.max_drawdown <= max_drawdown_limit]
    if eligible:
        return max(eligible, key=lambda p: p.oos_return)
    return min(front, key=lambda p: p.max_drawdown)
