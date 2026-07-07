"""A5 — Risk overlays: two-tier trailing stop + volatility-based position sizing.

Parameters mirror the successful case's state.json. Both overlays are OFF by default
so existing backtests are unchanged; enable via RiskOverlay passed to run_factor_backtest.

No look-ahead: the trailing stop walks a position's daily price path forward only and
exits the first day a stop level is breached, using only prices up to that day.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class RiskOverlay:
    # two-tier trailing stop (gains expressed as fractions of entry price)
    trailing_stop_enabled: bool = False
    tier1_trigger: float = 0.15   # once +15% gain reached ...
    tier1_floor: float = 0.05     # ... lock in a +5% floor above entry
    tier2_trigger: float = 0.30   # once +30% gain reached ...
    tier2_pullback: float = 0.10  # ... trail 10% below the running peak

    # volatility-based position sizing (scale a slot down when vol is high)
    vol_position_enabled: bool = False
    vol_tier1_pct: float = 50.0   # above the 50th vol percentile -> scale 0.7
    vol_tier1_scale: float = 0.7
    vol_tier2_pct: float = 80.0   # above the 80th vol percentile -> scale 0.5
    vol_tier2_scale: float = 0.5


def apply_trailing_stop(
    path: Sequence[float], entry_price: float, risk: RiskOverlay
) -> Tuple[float, bool]:
    """Walk a position's daily close path (entry day .. exit day, inclusive of the
    final close) and return (realised_exit_price, exited_early).

    Stop logic per day, using the running peak gain so far:
      - peak gain >= tier2_trigger -> stop at peak * (1 - tier2_pullback)
      - peak gain >= tier1_trigger -> stop at entry * (1 + tier1_floor)
      - otherwise                  -> no stop yet
    The first day the day's close <= active stop, exit at that stop level.
    """
    if not risk.trailing_stop_enabled or entry_price <= 0 or len(path) < 2:
        return (path[-1] if path else entry_price), False
    peak = entry_price
    for price in path[1:]:  # path[0] is the entry close
        peak = max(peak, price)
        peak_gain = peak / entry_price - 1.0
        stop_level = None
        if peak_gain >= risk.tier2_trigger:
            stop_level = peak * (1.0 - risk.tier2_pullback)
        elif peak_gain >= risk.tier1_trigger:
            stop_level = entry_price * (1.0 + risk.tier1_floor)
        if stop_level is not None and price <= stop_level:
            return stop_level, True
    return path[-1], False


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return float("inf")
    k = max(0, min(len(sorted_vals) - 1, int(round(pct / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def position_scales(vols: Sequence[float], risk: RiskOverlay) -> List[float]:
    """Per-position multiplier (1.0 / tier1_scale / tier2_scale) from cross-sectional
    volatility percentiles among the held names. Returns 1.0s when disabled or vols
    missing."""
    if not risk.vol_position_enabled or not vols:
        return [1.0] * len(vols)
    clean = [v for v in vols if v is not None and v == v]  # drop NaN
    if len(clean) < 2:
        return [1.0] * len(vols)
    s = sorted(clean)
    p1 = _percentile(s, risk.vol_tier1_pct)
    p2 = _percentile(s, risk.vol_tier2_pct)
    out: List[float] = []
    for v in vols:
        if v is None or v != v:
            out.append(1.0)
        elif v >= p2:
            out.append(risk.vol_tier2_scale)
        elif v >= p1:
            out.append(risk.vol_tier1_scale)
        else:
            out.append(1.0)
    return out
