"""A2 — IC-adaptive factor weighting.

Weight each factor by its recent predictive power (Information Coefficient) instead
of optimizing weights on past returns (which overfits — see the colleague's 3fopt
losing to equal-weight). Locked decision (2026-06-28): IC sets factor weights; HPO
only tunes structural params.

IC(d) for a factor = cross-sectional rank correlation (Spearman) between the factor
value at date d and the forward N-day return realised from d.

NO LOOK-AHEAD (critical): IC(d) depends on prices up to d+N. So the weight used AT
date T may only use IC observations whose forward window has fully closed by T, i.e.
dates d with d + N <= T. `ic_adaptive_weights` enforces this by shifting the smoothed
IC series forward by `forward_days` trading rows before it is consumed as a weight.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def add_forward_return(
    panel: pd.DataFrame,
    price: pd.DataFrame,
    forward_days: int = 20,
    price_col: str = "close_adj",
) -> pd.DataFrame:
    """Attach `fwd_ret` (label for IC only) by joining trailing price to forward price.

    `price` must have columns [stock_code, trade_date, <price_col>]. The forward return
    is computed per stock as price[t+N]/price[t]-1 and merged onto the panel. This label
    is used ONLY to measure IC; it is never a model feature.
    """
    p = price[["stock_code", "trade_date", price_col]].copy()
    p["trade_date"] = pd.to_datetime(p["trade_date"])
    p = p.sort_values(["stock_code", "trade_date"])
    p["fwd_ret"] = p.groupby("stock_code")[price_col].shift(-forward_days) / p[price_col] - 1.0
    out = panel.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"])
    out = out.merge(p[["stock_code", "trade_date", "fwd_ret"]], on=["stock_code", "trade_date"], how="left")
    return out


def compute_ic_panel(
    panel_with_fwd: pd.DataFrame,
    factors: List[str],
    ret_col: str = "fwd_ret",
    method: str = "spearman",
    min_names: int = 10,
) -> pd.DataFrame:
    """Daily cross-sectional IC for each factor. Returns DataFrame indexed by trade_date,
    columns = factors. NaN where too few names that day."""
    df = panel_with_fwd.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    records: Dict[pd.Timestamp, Dict[str, float]] = {}
    for date, grp in df.groupby("trade_date"):
        sub = grp.dropna(subset=[ret_col])
        if len(sub) < min_names:
            continue
        row: Dict[str, float] = {}
        fwd = sub[ret_col]
        for f in factors:
            col = sub[f]
            valid = col.notna() & fwd.notna()
            if valid.sum() < min_names:
                row[f] = np.nan
            elif method == "spearman":
                # Spearman = Pearson on ranks (avoids a scipy dependency)
                row[f] = col[valid].rank().corr(fwd[valid].rank())
            else:
                row[f] = col[valid].corr(fwd[valid], method=method)
        records[date] = row
    ic = pd.DataFrame.from_dict(records, orient="index").sort_index()
    return ic[factors] if not ic.empty else ic


def ic_adaptive_weights(
    ic_panel: pd.DataFrame,
    forward_days: int = 20,
    smooth_alpha: float = 0.3,
    floor: float = 0.01,
    lookback: Optional[int] = 60,
) -> pd.DataFrame:
    """Turn a daily IC panel into per-date factor weights (rows sum to 1).

    Steps: (1) optional rolling-mean over `lookback` days to denoise; (2) EMA smooth
    with `smooth_alpha`; (3) shift forward by `forward_days` so weights at T only use
    IC whose forward window closed by T (NO LOOK-AHEAD); (4) clip at `floor`, normalize.
    """
    if ic_panel.empty:
        return ic_panel.copy()
    ic = ic_panel.sort_index()
    if lookback:
        ic = ic.rolling(lookback, min_periods=max(5, lookback // 4)).mean()
    smoothed = ic.ewm(alpha=smooth_alpha, min_periods=1).mean()
    # critical no-look-ahead shift: IC(d) needs data through d+forward_days, so it is
    # only usable as a weight forward_days rows later.
    usable = smoothed.shift(forward_days)
    clipped = usable.clip(lower=floor)
    weights = clipped.div(clipped.sum(axis=1), axis=0)
    return weights


def weights_as_of(weights: pd.DataFrame, date) -> Dict[str, float]:
    """Latest available weight row on/before `date` as a {factor: weight} dict.

    Falls back to equal weights when the IC panel is empty / not yet usable (e.g. a
    universe too small to produce IC, or before the first usable date)."""
    if weights is None or weights.empty or weights.shape[1] == 0:
        return {}
    if not isinstance(weights.index, pd.DatetimeIndex):
        n = weights.shape[1]
        return {c: 1.0 / n for c in weights.columns}
    date = pd.Timestamp(date)
    avail = weights.loc[weights.index <= date]
    if avail.empty:
        n = weights.shape[1]
        return {c: 1.0 / n for c in weights.columns}
    row = avail.iloc[-1].dropna()
    if row.empty or row.sum() == 0:
        n = weights.shape[1]
        return {c: 1.0 / n for c in weights.columns}
    return (row / row.sum()).to_dict()
