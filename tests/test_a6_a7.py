"""Tests for A6 rolling re-optimization and A7 per-universe."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.cost_model import CostModel  # noqa: E402
from quant_agent_team.hpo import HyperParamSpace  # noqa: E402
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis  # noqa: E402
from quant_agent_team.per_universe import run_per_universe  # noqa: E402
from quant_agent_team.rolling_reopt import RollingResult, rolling_reoptimize  # noqa: E402
from quant_agent_team.pipeline_v51 import TrustworthyReport  # noqa: E402


def _frame(n_stocks=24, n_days=520, seed=5):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-06-26", periods=n_days)
    quality = rng.normal(size=n_stocks)
    prices = np.full(n_stocks, 10.0)
    rows = []
    for d in dates:
        drift = 0.0008 * quality + rng.normal(scale=0.012, size=n_stocks)
        prices = prices * (1.0 + drift)
        fac = quality + rng.normal(scale=0.5, size=n_stocks)
        for i in range(n_stocks):
            rows.append({"stock_code": f"{i:04d}", "trade_date": d,
                         "close_price_adj": float(prices[i]), "vol_20d": 0.02, "mom": float(fac[i])})
    return pd.DataFrame(rows)


def _hyp():
    return FactorHypothesis(market="cn", factors=[FactorDef("mom", "mom", "long_high")])


def test_rolling_reopt_produces_oos_curve():
    frame = _frame()
    space = HyperParamSpace(top_n_choices=[3, 5], rebalance_days_choices=[5])
    res = rolling_reoptimize(
        frame, _hyp(), space, lookback_months=6, min_train_months=6,
        n_trials=4, n_folds=2, cost_model=CostModel(0.0, 0.0),
    )
    assert isinstance(res, RollingResult)
    assert res.months >= 1
    assert len(res.oos_equity) > 0
    assert res.snapshots and all(s.top_n in (3, 5) for s in res.snapshots)


def test_per_universe_runs_each_pool():
    frame = _frame()
    codes = sorted(frame["stock_code"].unique())
    universes = {"poolA": codes[:12], "poolB": codes[12:]}
    space = HyperParamSpace(top_n_choices=[3], rebalance_days_choices=[5])
    reports = run_per_universe(
        frame, universes, _hyp(), space, end_date=date(2026, 6, 26),
        n_trials=4, n_folds=2, cost_model=CostModel(0.0, 0.0), run_null=False,
    )
    assert set(reports) == {"poolA", "poolB"}
    for r in reports.values():
        assert isinstance(r, TrustworthyReport)
        assert r.holdout_return is not None
