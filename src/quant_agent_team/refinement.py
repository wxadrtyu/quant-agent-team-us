from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

import pandas as pd

from .cost_model import CostModel
from .evaluation import AcceptanceCriteria
from .hpo import HyperParamSpace, SearchResult, search_strategy
from .hypothesis import FactorHypothesis


class InvalidHypothesisError(Exception):
    """Raised by a proposer when its output cannot be parsed/validated."""


@dataclass
class IterationRecord:
    hypothesis: Optional[FactorHypothesis]
    best_score: Optional[float]
    passed: bool
    note: str


@dataclass
class ProposalContext:
    market: str
    return_target: float
    available_factors: List[str]
    history: List[IterationRecord] = field(default_factory=list)


class HypothesisProposer(Protocol):
    def propose(self, context: "ProposalContext") -> FactorHypothesis: ...


@dataclass
class RefinementResult:
    accepted: Optional[SearchResult]
    iterations: List[IterationRecord]
    stopped_reason: str


def run_refinement(
    frame: pd.DataFrame,
    proposer: HypothesisProposer,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    market: str,
    return_target: float,
    available_factors: List[str],
    max_iterations: int = 10,
    n_trials: int = 20,
    seed: int = 0,
    cost_model: CostModel | None = None,
) -> RefinementResult:
    history: List[IterationRecord] = []
    for i in range(max_iterations):
        context = ProposalContext(
            market=market,
            return_target=return_target,
            available_factors=available_factors,
            history=history,
        )
        try:
            hypothesis = proposer.propose(context)
        except InvalidHypothesisError as exc:
            history.append(
                IterationRecord(hypothesis=None, best_score=None, passed=False, note=f"invalid: {exc}")
            )
            continue

        result = search_strategy(
            frame, hypothesis, space, criteria, n_trials=n_trials, seed=seed + i, cost_model=cost_model
        )
        history.append(
            IterationRecord(
                hypothesis=hypothesis,
                best_score=result.hpo.best_score,
                passed=result.evaluation.passed,
                note="; ".join(result.evaluation.notes),
            )
        )
        if result.evaluation.passed:
            return RefinementResult(accepted=result, iterations=history, stopped_reason="accepted")

    return RefinementResult(accepted=None, iterations=history, stopped_reason="budget_exhausted")
