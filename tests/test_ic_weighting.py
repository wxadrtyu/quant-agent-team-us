"""Tests for A2 ic_weighting — IC discriminates signal vs noise + no look-ahead."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.ic_weighting import (  # noqa: E402
    compute_ic_panel,
    ic_adaptive_weights,
    weights_as_of,
)


def _synthetic(n_stocks=40, n_days=200, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    rows = []
    for d in dates:
        signal = rng.normal(size=n_stocks)
        noise = rng.normal(size=n_stocks)
        # forward return is driven by `signal` (predictive) + idiosyncratic noise
        fwd = 0.6 * signal + rng.normal(scale=0.5, size=n_stocks)
        for i in range(n_stocks):
            rows.append({
                "stock_code": f"{i:06d}", "trade_date": d,
                "sig_factor": signal[i], "noise_factor": noise[i], "fwd_ret": fwd[i],
            })
    return pd.DataFrame(rows)


def test_signal_factor_outweighs_noise():
    panel = _synthetic()
    ic = compute_ic_panel(panel, ["sig_factor", "noise_factor"])
    assert ic["sig_factor"].mean() > 0.2
    assert abs(ic["noise_factor"].mean()) < 0.1
    w = ic_adaptive_weights(ic, forward_days=20, lookback=40)
    last = weights_as_of(w, w.index[-1])
    assert last["sig_factor"] > last["noise_factor"]
    assert last["sig_factor"] > 0.6  # signal dominates


def test_no_lookahead_weights_stable_under_future_append():
    panel = _synthetic(n_days=200)
    cutoff = panel["trade_date"].sort_values().unique()[150]

    ic_full = compute_ic_panel(panel, ["sig_factor", "noise_factor"])
    ic_trunc = compute_ic_panel(panel[panel["trade_date"] <= cutoff], ["sig_factor", "noise_factor"])

    w_full = ic_adaptive_weights(ic_full, forward_days=20, lookback=40)
    w_trunc = ic_adaptive_weights(ic_trunc, forward_days=20, lookback=40)

    # weights at dates well before the cutoff must be identical with/without future data
    horizon = pd.Timestamp(cutoff) - pd.Timedelta(days=40)
    common = [d for d in w_trunc.index if d <= horizon and d in w_full.index]
    assert len(common) > 10
    for d in common:
        a = w_full.loc[d].dropna()
        b = w_trunc.loc[d].dropna()
        if a.empty or b.empty:
            continue
        for f in a.index:
            assert abs(a[f] - b[f]) < 1e-9, f"look-ahead leak in weights at {d}"
