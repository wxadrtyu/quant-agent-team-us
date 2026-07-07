"""Tests for A4 index-relative metrics (alpha / IR / tracking error)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.relative_eval import (  # noqa: E402
    RelativeAcceptance,
    passes_relative,
    relative_metrics,
)


def _frames(strat_rets, bench_rets):
    n = len(strat_rets) + 1
    dates = pd.bdate_range("2025-01-01", periods=n)
    eq, bm = [100.0], [100.0]
    for sr, br in zip(strat_rets, bench_rets):
        eq.append(eq[-1] * (1 + sr))
        bm.append(bm[-1] * (1 + br))
    equity_df = pd.DataFrame({"trade_date": dates, "equity": eq})
    bench_df = pd.DataFrame({"trade_date": dates, "close": bm})
    return equity_df, bench_df


def test_positive_alpha_and_ir():
    # strategy beats benchmark every day, with varying (non-zero TE) excess
    strat = [0.12, 0.08, 0.15, 0.05, 0.10]
    bench = [0.01, 0.00, 0.02, -0.01, 0.01]
    m = relative_metrics(*_frames(strat, bench))
    assert m.excess_return > 0.3
    assert m.win_rate_vs_benchmark == 1.0
    assert m.tracking_error > 0
    assert m.information_ratio > 0
    assert m.strategy_return > m.benchmark_return


def test_underperformance_is_negative_alpha():
    strat = [-0.02, 0.01, -0.03, 0.00, -0.01]
    bench = [0.01, 0.02, 0.01, 0.015, 0.02]
    m = relative_metrics(*_frames(strat, bench))
    assert m.excess_return < 0
    assert m.win_rate_vs_benchmark == 0.0


def test_acceptance_gate_uses_ir():
    m = relative_metrics(*_frames([0.12, 0.08, 0.15, 0.05, 0.10], [0.01, 0.0, 0.02, -0.01, 0.01]))
    res = passes_relative(m, RelativeAcceptance(min_information_ratio=0.5))
    assert res["passed"]
    res2 = passes_relative(m, RelativeAcceptance(min_information_ratio=1e9))
    assert not res2["passed"] and "information_ratio" in res2["failed_checks"]
