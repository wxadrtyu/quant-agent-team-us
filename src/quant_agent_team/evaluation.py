from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .backtest_runner import BacktestResult
from .io_utils import write_json


@dataclass
class EvaluationResult:
    spec_id: str
    strategy_id: str
    passed: bool
    thresholds: Dict[str, float]
    observed_metrics: Dict[str, float]
    failed_checks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AcceptanceCriteria:
    min_annualized_return: float
    max_drawdown_limit: float
    min_trade_count: int


def evaluate_strategy(result: BacktestResult, criteria: AcceptanceCriteria) -> EvaluationResult:
    failed_checks: List[str] = []
    if result.annualized_return < criteria.min_annualized_return:
        failed_checks.append("annualized_return")
    if result.max_drawdown > criteria.max_drawdown_limit:
        failed_checks.append("max_drawdown")
    if result.trade_count < criteria.min_trade_count:
        failed_checks.append("trade_count")

    notes = (
        ["Strategy did not satisfy the return-focused acceptance gate."]
        if failed_checks
        else ["Strategy satisfied the return-focused acceptance gate."]
    )
    return EvaluationResult(
        spec_id=result.spec_id,
        strategy_id=result.strategy_id,
        passed=not failed_checks,
        thresholds={
            "min_annualized_return": criteria.min_annualized_return,
            "max_drawdown_limit": criteria.max_drawdown_limit,
            "min_trade_count": float(criteria.min_trade_count),
        },
        observed_metrics={
            "annualized_return": result.annualized_return,
            "max_drawdown": result.max_drawdown,
            "trade_count": float(result.trade_count),
        },
        failed_checks=failed_checks,
        notes=notes,
    )


def evaluate_backtest_result(
    result: BacktestResult,
    min_trade_win_rate: float = 0.80,
    min_annualized_return: float = 0.20,
    max_drawdown_limit: float = 0.30,
    min_sharpe: float = 2.0,
) -> EvaluationResult:
    failed_checks: List[str] = []
    if result.trade_win_rate < min_trade_win_rate:
        failed_checks.append("trade_win_rate")
    if result.annualized_return < min_annualized_return:
        failed_checks.append("annualized_return")
    if result.max_drawdown > max_drawdown_limit:
        failed_checks.append("max_drawdown")
    if result.sharpe < min_sharpe:
        failed_checks.append("sharpe")

    notes = []
    if failed_checks:
        notes.append("Backtest did not satisfy all user KPI gates.")
    else:
        notes.append("Backtest satisfied all current user KPI gates.")

    return EvaluationResult(
        spec_id=result.spec_id,
        strategy_id=result.strategy_id,
        passed=not failed_checks,
        thresholds={
            "min_trade_win_rate": min_trade_win_rate,
            "min_annualized_return": min_annualized_return,
            "max_drawdown_limit": max_drawdown_limit,
            "min_sharpe": min_sharpe,
        },
        observed_metrics={
            "trade_win_rate": result.trade_win_rate,
            "annualized_return": result.annualized_return,
            "max_drawdown": result.max_drawdown,
            "sharpe": result.sharpe,
        },
        failed_checks=failed_checks,
        notes=notes,
    )


def write_evaluation_report(path: Path, result: EvaluationResult) -> None:
    write_json(path, result.to_dict())
