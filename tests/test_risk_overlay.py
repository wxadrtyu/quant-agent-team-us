"""Tests for A5 risk overlays — trailing stop + vol position sizing."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.cost_model import CostModel  # noqa: E402
from quant_agent_team.factor_backtest import run_factor_backtest  # noqa: E402
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis  # noqa: E402
from quant_agent_team.risk_overlay import (  # noqa: E402
    RiskOverlay,
    apply_trailing_stop,
    position_scales,
)


def test_trailing_stop_locks_gain_on_pullback():
    risk = RiskOverlay(trailing_stop_enabled=True)
    # entry 100, rises to 140 (+40% > tier2 30%), then crashes to 80
    path = [100, 110, 130, 140, 120, 80]
    exit_price, exited = apply_trailing_stop(path, 100.0, risk)
    assert exited
    # tier2: stop at peak(140)*(1-0.10)=126; price 120 <= 126 -> exit at 126
    assert abs(exit_price - 126.0) < 1e-9


def test_trailing_stop_holds_when_only_rising():
    risk = RiskOverlay(trailing_stop_enabled=True)
    path = [100, 110, 120, 135]
    exit_price, exited = apply_trailing_stop(path, 100.0, risk)
    assert not exited and exit_price == 135


def test_trailing_stop_disabled_returns_last():
    risk = RiskOverlay(trailing_stop_enabled=False)
    assert apply_trailing_stop([100, 50, 30], 100.0, risk) == (30, False)


def test_position_scales_downweights_high_vol():
    risk = RiskOverlay(vol_position_enabled=True)
    vols = [0.01, 0.02, 0.03, 0.04, 0.05]  # highest should be scaled to 0.5
    scales = position_scales(vols, risk)
    assert scales[-1] <= scales[0]
    assert max(scales) == 1.0


def _spike_crash_frame() -> pd.DataFrame:
    """One held name spikes +40% then crashes by exit; trailing stop should help."""
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
    prices = [100.0, 130.0, 140.0, 120.0, 90.0]  # peak 140 then down to 90
    rows = []
    for d, p in zip(dates, prices):
        rows.append({"stock_code": "A", "trade_date": d, "close_price_adj": p, "mom": 1.0})
        rows.append({"stock_code": "B", "trade_date": d, "close_price_adj": 100.0, "mom": -1.0})
    return pd.DataFrame(rows)


def test_trailing_stop_improves_realized_return_on_crash():
    frame = _spike_crash_frame()
    hyp = FactorHypothesis(market="cn", factors=[FactorDef("mom", "mom", "long_high")])
    config = FactorConfig(weights={"mom": 1.0}, top_n=1, rebalance_days=4)  # hold across the spike-crash
    no_stop = run_factor_backtest(frame, hyp, config, cost_model=CostModel(0.0, 0.0))
    with_stop = run_factor_backtest(
        frame, hyp, config, cost_model=CostModel(0.0, 0.0),
        risk=RiskOverlay(trailing_stop_enabled=True),
    )
    assert with_stop.total_return > no_stop.total_return
