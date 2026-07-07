from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OverfittingInputs:
    outer_iterations: int
    total_trials: int
    hp_dimensions: int
    trade_count: int
    dev_return: Optional[float] = None
    holdout_return: Optional[float] = None


def _saturating(x: float, scale: float) -> float:
    # 0 at x=0, approaches 1 as x grows; higher = riskier
    return 1.0 - math.exp(-max(x, 0.0) / scale)


def overfitting_score(inputs: OverfittingInputs) -> float:
    components: List[float] = [
        _saturating(inputs.outer_iterations, 10.0),
        _saturating(inputs.total_trials, 200.0),
        _saturating(inputs.hp_dimensions, 8.0),
        math.exp(-max(inputs.trade_count, 0) / 30.0),  # few trades -> near 1 (risky)
    ]
    if (
        inputs.dev_return is not None
        and inputs.holdout_return is not None
        and inputs.dev_return != 0
    ):
        degradation = (inputs.dev_return - inputs.holdout_return) / abs(inputs.dev_return)
        components.append(min(1.0, max(0.0, degradation)))
    return float(sum(components) / len(components))


def deflate_return(raw_return: float, n_trials: int) -> float:
    factor = 1.0 / (1.0 + math.log(max(n_trials, 1)))
    return raw_return * factor
