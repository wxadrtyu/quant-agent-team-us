# 2026-07-18 US low-correlation admission gates

## Summary

- Created branch `codex/low-correlation-admission-gates`.
- Upgraded final promotion audit so new strategies cannot enter current if they fail low-correlation or recent-weak-symbol controls.
- Added candidate-stage hard filtering so high-correlation baskets do not waste rolling/null validation capacity.

## New Gates

- Final audit now records and rejects on:
  - `max_pairwise_correlation` above threshold, default 0.60.
  - `weak_symbol_hits` above threshold, default 1.
  - Existing checks remain active: max current basket overlap, current stock reuse share, max current symbol count, drag symbol leakage, positive live excess, holding count.
- Candidate generation now writes and filters:
  - `max_pairwise_correlation`
  - `weak_symbol_hits`

## Smoke Run

- round348 `decorrelated`, small smoke run:
  - promoted strategies: 0.
  - best rolling information ratio: 1.3146.
  - best random p-value: 0.0647, not enough to enter current.
  - candidate max pairwise correlation after hard filter: 0.5415.
  - candidate max weak symbol hits after hard filter: 0.

## Current State

- current remains unchanged:
  - 430 strategies.
  - 3636 holdings.
  - 215 outperformers.
  - 215 underperformers retained.
- Latest report validation still passes for valuation date 2026-07-17.

## Verification

- `pytest -q tests/test_us_audit_promoted_rounds_before_append.py tests/test_us_live_strength_strategy_exploration.py tests/test_us_current_model_portfolio.py tests/test_us_strategy_factory_factors.py`: 43 passed, 2 subtests passed.
- `scripts/us_validate_live_current.py`: invalid holding count 0, no fallback names, underperformers retained.

## Next Step

- Use this branch as the new baseline for future strategy discovery.
- Do not loosen the correlation gate unless no candidates appear for several truly new factor families.
- Continue prioritizing 5/7-stock strategies and v23-style low-correlation model portfolio aggregation.
