# 2026-07-18 US sectorleader round326-327 local memory

## Summary

- Ran round 326-327 with the `sectorleader` branch and strict candidate-stage max overlap of 0.20.
- Round 326 promoted 0 strategies.
- Round 327 promoted 4 strategies before final holding audit.
- The post-promotion audit rejected all 4, so current was not modified.

## Audit Findings

All rejected strategies had:

- current stock reuse share: 100%,
- max current basket overlap: 50.00% to 71.43%,
- max current symbol count: 383,
- drag symbol hits: 3 to 4,
- positive live excess, but unacceptable final holding crowding.

## Diagnosis

The candidate generation stage can use branch-specific symbol-level adjustments, such as current crowding penalties and sector-strength adjustments. The promotion stage rebuilds holdings from the raw factor weights and does not reproduce those symbol-level adjustments. Therefore, a candidate can look low-overlap during generation, pass statistical tests, and then produce crowded final holdings during promotion.

## Decision

- Do not append round 326-327 strategies.
- Keep the post-promotion audit as a mandatory final gate.
- Future work should either:
  - make promotion reproduce the same branch-specific symbol-level adjustments, or
  - focus on alpha structures that do not rely on symbol-level crowding adjustments to select holdings.

## Current State

- Current remains 428 strategies and 3626 holdings.
- Valuation date remains 2026-07-17.
- Underperforming strategies remain retained in the current report.
