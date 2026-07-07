from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .factor_scoring import composite_scores, select_top_n
from .hypothesis import FactorConfig, FactorHypothesis


@dataclass
class PaperTradeResult:
    backtest: BacktestResult
    latest_signal: List[str]


def run_paper_trade(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    cost_model: CostModel | None = None,
) -> PaperTradeResult:
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    backtest = run_factor_backtest(frame, hypothesis, config, cost_model=cost_model)

    last_date = frame["trade_date"].max()
    last_rows = frame.loc[frame["trade_date"] == last_date]
    scored = composite_scores(
        last_rows, hypothesis.factors, config.weights, sector_neutral=hypothesis.sector_neutral
    )
    picks = select_top_n(scored, config.top_n)
    latest_signal = [str(code) for code in picks["stock_code"].tolist()]
    return PaperTradeResult(backtest=backtest, latest_signal=latest_signal)
