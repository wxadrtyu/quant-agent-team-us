from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

MAX_FACTORS = 8


@dataclass(frozen=True)
class FactorDef:
    name: str
    source_field: str
    direction: str

    def __post_init__(self) -> None:
        if self.direction not in {"long_high", "long_low"}:
            raise ValueError(f"direction must be 'long_high' or 'long_low', got {self.direction!r}")


@dataclass
class FactorHypothesis:
    market: str
    factors: List[FactorDef]
    sector_neutral: bool = False
    combination: str = "linear_zscore"

    def __post_init__(self) -> None:
        if self.market not in {"cn", "us"}:
            raise ValueError(f"market must be 'cn' or 'us', got {self.market!r}")
        if not self.factors:
            raise ValueError("a hypothesis needs at least one factor")
        if len(self.factors) > MAX_FACTORS:
            raise ValueError(
                f"at most {MAX_FACTORS} factors allowed (parsimony cap), got {len(self.factors)}"
            )
        if self.combination != "linear_zscore":
            raise ValueError(f"combination must be 'linear_zscore', got {self.combination!r}")


@dataclass
class FactorConfig:
    weights: Dict[str, float]
    top_n: int
    rebalance_days: int
