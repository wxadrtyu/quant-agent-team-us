from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import pandas as pd

from .cost_model import CostModel
from .evaluation import AcceptanceCriteria
from .holdout import HoldoutResult, HoldoutVault
from .hpo import HyperParamSpace
from .null_test import run_null_test
from .overfitting import OverfittingInputs, deflate_return, overfitting_score
from .refinement import HypothesisProposer, RefinementResult, run_refinement
from .walk_forward import split_three_year_window


@dataclass
class OrchestratorReport:
    refinement: RefinementResult
    holdout: Optional[HoldoutResult]
    overfitting: Optional[float]
    deflated_holdout_return: Optional[float]
    null_pass_rate: Optional[float]


def run_pipeline(
    frame: pd.DataFrame,
    proposer: HypothesisProposer,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    market: str,
    return_target: float,
    available_factors: List[str],
    end_date: date,
    max_iterations: int = 10,
    n_trials: int = 20,
    seed: int = 0,
    cost_model: CostModel | None = None,
    run_null: bool = True,
    null_runs: int = 3,
) -> OrchestratorReport:
    split = split_three_year_window(end_date)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    dev_start = pd.Timestamp(split.development_start)
    dev_end = pd.Timestamp(split.development_end)
    development = frame.loc[(frame["trade_date"] >= dev_start) & (frame["trade_date"] <= dev_end)]

    refinement = run_refinement(
        development,
        proposer,
        space,
        criteria,
        market=market,
        return_target=return_target,
        available_factors=available_factors,
        max_iterations=max_iterations,
        n_trials=n_trials,
        seed=seed,
        cost_model=cost_model,
    )
    if refinement.accepted is None:
        return OrchestratorReport(
            refinement=refinement,
            holdout=None,
            overfitting=None,
            deflated_holdout_return=None,
            null_pass_rate=None,
        )

    hypothesis = refinement.iterations[-1].hypothesis
    config = refinement.accepted.hpo.best_config

    vault = HoldoutVault(split.holdout_start, split.holdout_end, cost_model=cost_model)
    holdout = vault.evaluate("accepted", frame, hypothesis, config)

    dev_return = refinement.accepted.development_result.annualized_return
    holdout_return = holdout.backtest.annualized_return
    n_trials_total = refinement.accepted.hpo.n_trials
    overfitting = overfitting_score(
        OverfittingInputs(
            outer_iterations=len(refinement.iterations),
            total_trials=n_trials_total,
            hp_dimensions=len(hypothesis.factors) + 2,
            trade_count=holdout.backtest.trade_count,
            dev_return=dev_return,
            holdout_return=holdout_return,
        )
    )
    deflated = deflate_return(holdout_return, n_trials_total)

    null_pass_rate: Optional[float] = None
    if run_null:
        null_pass_rate = run_null_test(
            development,
            hypothesis,
            space,
            criteria,
            n_runs=null_runs,
            n_trials=n_trials,
            cost_model=cost_model,
        ).pass_rate

    return OrchestratorReport(
        refinement=refinement,
        holdout=holdout,
        overfitting=overfitting,
        deflated_holdout_return=deflated,
        null_pass_rate=null_pass_rate,
    )
