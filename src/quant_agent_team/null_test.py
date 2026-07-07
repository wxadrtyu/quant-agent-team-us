from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .cost_model import CostModel
from .evaluation import AcceptanceCriteria
from .hpo import HyperParamSpace, search_strategy
from .hypothesis import FactorHypothesis


@dataclass
class NullTestResult:
    n_runs: int
    passes: int
    pass_rate: float


def _shuffle_factors(frame: pd.DataFrame, hypothesis: FactorHypothesis, rng: np.random.Generator) -> pd.DataFrame:
    shuffled = frame.copy()
    for factor in hypothesis.factors:
        values = shuffled[factor.source_field].to_numpy()
        shuffled[factor.source_field] = rng.permutation(values)
    return shuffled


def run_null_test(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    n_runs: int = 5,
    base_seed: int = 0,
    n_trials: int = 10,
    cost_model: CostModel | None = None,
) -> NullTestResult:
    passes = 0
    for i in range(n_runs):
        rng = np.random.default_rng(base_seed + i)
        shuffled = _shuffle_factors(frame, hypothesis, rng)
        result = search_strategy(
            shuffled, hypothesis, space, criteria, n_trials=n_trials, seed=base_seed + i, cost_model=cost_model
        )
        if result.evaluation.passed:
            passes += 1
    pass_rate = passes / n_runs if n_runs else 0.0
    return NullTestResult(n_runs=n_runs, passes=passes, pass_rate=pass_rate)
