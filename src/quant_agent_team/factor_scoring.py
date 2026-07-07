from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .hypothesis import FactorDef


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=series.index)
    return (numeric - numeric.mean()) / std


def composite_scores(
    frame: pd.DataFrame,
    factors: List[FactorDef],
    weights: Dict[str, float],
    sector_neutral: bool = False,
    sector_column: str = "sector_name",
) -> pd.DataFrame:
    frame = frame.copy()
    total = pd.Series(0.0, index=frame.index)
    for factor in factors:
        column = frame[factor.source_field]
        if sector_neutral and sector_column in frame.columns:
            z = column.groupby(frame[sector_column]).transform(_zscore)
        else:
            z = _zscore(column)
        sign = 1.0 if factor.direction == "long_high" else -1.0
        weight = weights.get(factor.name, 0.0)
        total = total + weight * sign * z.fillna(0.0)
    frame["composite_score"] = total
    return frame


def select_top_n(scored: pd.DataFrame, top_n: int) -> pd.DataFrame:
    return scored.sort_values("composite_score", ascending=False).head(top_n)
