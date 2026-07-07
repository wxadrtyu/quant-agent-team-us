from __future__ import annotations

from dataclasses import dataclass

DEFAULT_COMMISSION_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 10.0
_BPS = 10_000.0


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = DEFAULT_COMMISSION_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def entry_fill_price(self, reference_price: float) -> float:
        return reference_price * (1.0 + self.slippage_bps / _BPS)

    def exit_fill_price(self, reference_price: float) -> float:
        return reference_price * (1.0 - self.slippage_bps / _BPS)

    def commission(self, notional: float) -> float:
        return abs(notional) * self.commission_bps / _BPS

    @classmethod
    def for_market(cls, market: str) -> "CostModel":
        if market == "cn":
            return cls(commission_bps=5.0, slippage_bps=10.0)
        if market == "us":
            return cls(commission_bps=1.0, slippage_bps=5.0)
        raise ValueError(f"Unknown market: {market!r}")
