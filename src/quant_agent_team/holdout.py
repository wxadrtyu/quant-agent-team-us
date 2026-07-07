from __future__ import annotations

from dataclasses import dataclass
from typing import Set

import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .hypothesis import FactorConfig, FactorHypothesis


class HoldoutAlreadyUsedError(Exception):
    """Raised when a strategy is evaluated against the holdout more than once."""


@dataclass
class HoldoutResult:
    strategy_id: str
    backtest: BacktestResult
    touches: int
    degraded: bool


class HoldoutVault:
    def __init__(
        self,
        holdout_start,
        holdout_end,
        touch_budget: int = 20,
        cost_model: CostModel | None = None,
    ) -> None:
        self._start = pd.Timestamp(holdout_start)
        self._end = pd.Timestamp(holdout_end)
        self._touch_budget = touch_budget
        self._cost_model = cost_model
        self._used: Set[str] = set()
        self._touches = 0

    def evaluate(
        self,
        strategy_id: str,
        frame: pd.DataFrame,
        hypothesis: FactorHypothesis,
        config: FactorConfig,
    ) -> HoldoutResult:
        if strategy_id in self._used:
            raise HoldoutAlreadyUsedError(
                f"strategy {strategy_id!r} has already consumed its one-shot holdout evaluation"
            )
        self._used.add(strategy_id)
        self._touches += 1

        frame = frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        window = frame.loc[(frame["trade_date"] >= self._start) & (frame["trade_date"] <= self._end)]
        backtest = run_factor_backtest(window, hypothesis, config, cost_model=self._cost_model)
        return HoldoutResult(
            strategy_id=strategy_id,
            backtest=backtest,
            touches=self._touches,
            degraded=self._touches > self._touch_budget,
        )
