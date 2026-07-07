"""A7 — Per-index-universe optimization.

Mirrors the successful case's factor_wf_v1_<universe>_* studies: each index pool is
run through the whole tight loop independently and scored against ITS OWN benchmark
(value dominates in CSI1000, momentum elsewhere — one set of params does not fit all
pools). Universe membership comes from index constituents (data B2/B3).
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from .hpo import HyperParamSpace
from .hypothesis import FactorHypothesis
from .pipeline_v51 import TrustworthyReport, run_v51_pipeline


def run_per_universe(
    frame: pd.DataFrame,
    universes: Dict[str, List[str]],
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    end_date: date,
    benchmarks: Optional[Dict[str, pd.DataFrame]] = None,
    **pipeline_kwargs,
) -> Dict[str, TrustworthyReport]:
    """Run the v5.1 pipeline once per universe. `universes` maps a pool name to its
    member stock_codes; `benchmarks` maps a pool name to its benchmark [trade_date, close].
    Returns {pool_name: TrustworthyReport}."""
    benchmarks = benchmarks or {}
    reports: Dict[str, TrustworthyReport] = {}
    for name, codes in universes.items():
        sub = frame[frame["stock_code"].isin(set(codes))]
        if sub.empty:
            continue
        reports[name] = run_v51_pipeline(
            sub, hypothesis, space, end_date=end_date,
            benchmark_df=benchmarks.get(name), **pipeline_kwargs,
        )
    return reports
