"""Tests for A3 multi-objective NSGA-II HPO + Pareto selection."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.cost_model import CostModel  # noqa: E402
from quant_agent_team.hpo import (  # noqa: E402
    HyperParamSpace,
    ParetoPoint,
    multi_objective_optimize,
    select_from_pareto,
)
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis  # noqa: E402


def _signal_frame(n_stocks=30, n_days=60, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n_days)
    # each stock has a fixed "quality" that drives its drift; momentum factor reflects it
    quality = rng.normal(size=n_stocks)
    prices = np.full(n_stocks, 10.0)
    rows = []
    for d in dates:
        drift = 0.002 * quality + rng.normal(scale=0.01, size=n_stocks)
        prices = prices * (1.0 + drift)
        for i in range(n_stocks):
            rows.append({
                "stock_code": f"{i:04d}", "trade_date": d,
                "close_price_adj": float(prices[i]), "mom": float(quality[i]),
            })
    return pd.DataFrame(rows)


def _hyp() -> FactorHypothesis:
    return FactorHypothesis(market="cn", factors=[FactorDef("mom", "mom", "long_high")])


def test_pareto_front_non_empty():
    frame = _signal_frame()
    space = HyperParamSpace(top_n_choices=[2, 5, 10], rebalance_days_choices=[1, 2])
    front = multi_objective_optimize(
        frame, _hyp(), space, n_trials=12, seed=0, n_folds=3, cost_model=CostModel(0.0, 0.0)
    )
    assert front, "Pareto front should not be empty"
    for p in front:
        assert isinstance(p, ParetoPoint)
        assert p.max_drawdown >= 0.0


def test_select_respects_drawdown_limit():
    front = [
        ParetoPoint(config=None, oos_return=0.5, max_drawdown=0.40),
        ParetoPoint(config=None, oos_return=0.3, max_drawdown=0.15),
        ParetoPoint(config=None, oos_return=0.1, max_drawdown=0.05),
    ]
    pick = select_from_pareto(front, max_drawdown_limit=0.20)
    assert pick.oos_return == 0.3  # highest return within dd<=0.20
    # when nothing qualifies, fall back to lowest drawdown
    pick2 = select_from_pareto(front, max_drawdown_limit=0.01)
    assert pick2.max_drawdown == 0.05


def test_select_empty_front():
    assert select_from_pareto([], 0.2) is None
