"""Integration test for the v5.1 pipeline (A1-A5 + gates end-to-end)."""
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
from quant_agent_team.pipeline_v51 import TrustworthyReport, run_v51_pipeline  # noqa: E402


def _frame_and_benchmark(n_stocks=25, predictive=True, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-06-26", periods=760)  # ~3 years
    quality = rng.normal(size=n_stocks)
    prices = np.full(n_stocks, 10.0)
    rows = []
    bench = []
    blevel = 1000.0
    for d in dates:
        if predictive:
            drift = 0.0008 * quality + rng.normal(scale=0.012, size=n_stocks)
        else:
            drift = rng.normal(scale=0.012, size=n_stocks)
        prices = prices * (1.0 + drift)
        blevel *= 1.0 + float(np.mean(drift))  # benchmark ~ equal-weight universe
        bench.append({"trade_date": d, "close": blevel})
        # factor: noisy view of quality (predictive) or pure noise
        fac = quality + rng.normal(scale=0.5, size=n_stocks) if predictive else rng.normal(size=n_stocks)
        for i in range(n_stocks):
            rows.append({
                "stock_code": f"{i:04d}", "trade_date": d,
                "close_price_adj": float(prices[i]), "vol_20d": 0.02,
                "mom": float(fac[i]),
            })
    return pd.DataFrame(rows), pd.DataFrame(bench)


def _hyp():
    return FactorHypothesis(market="cn", factors=[FactorDef("mom", "mom", "long_high")])


def test_pipeline_runs_and_reports():
    frame, bench = _frame_and_benchmark(predictive=True)
    space = HyperParamSpace(top_n_choices=[3, 5], rebalance_days_choices=[5])
    report = run_v51_pipeline(
        frame, _hyp(), space, end_date=date(2026, 6, 26), benchmark_df=bench,
        n_trials=6, n_folds=3, cost_model=CostModel(0.0, 0.0), run_null=True, null_runs=2,
    )
    assert isinstance(report, TrustworthyReport)
    assert report.pareto_size >= 1
    assert report.holdout_return is not None
    assert report.relative is not None
    assert isinstance(report.trustworthy, bool)
    assert report.reasons  # always explains the verdict


def test_predictive_factor_beats_benchmark_on_holdout():
    frame, bench = _frame_and_benchmark(predictive=True)
    space = HyperParamSpace(top_n_choices=[3, 5], rebalance_days_choices=[5])
    report = run_v51_pipeline(
        frame, _hyp(), space, end_date=date(2026, 6, 26), benchmark_df=bench,
        n_trials=6, n_folds=3, cost_model=CostModel(0.0, 0.0), run_null=False,
    )
    # a factor that genuinely predicts cross-sectional returns should produce
    # positive excess return over the equal-weight benchmark on the holdout
    assert report.relative["metrics"]["excess_return"] > 0
