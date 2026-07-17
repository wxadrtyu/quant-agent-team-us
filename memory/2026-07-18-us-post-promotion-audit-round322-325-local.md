# 2026-07-18 US post-promotion audit local memory

## Summary

- Added a post-promotion audit before appending promoted strategies into current.
- Added `scripts/us_audit_promoted_rounds_before_append.py`.
- Added `--allowlist` support to `scripts/us_append_promoted_rounds_to_current.py`.
- Fixed `scripts/us_live_pool.py` so an empty promoted batch no longer shrinks or replaces the existing pool table schema.

## Exploration

- Round 322-323:
  - branch: decorrelated,
  - max overlap: 0.25,
  - promoted strategies: 0.
- Round 324-325:
  - branch: breadthquality20,
  - max overlap: 0.25,
  - round 324 promoted 1 strategy before post-promotion audit,
  - round 325 promoted 0 strategies.

## Audit Result

- The round 324 promoted 20-stock strategy was rejected before append.
- Rejection reasons:
  - max current basket overlap: 42.86%,
  - current stock reuse share: 85.00%,
  - max current symbol count: 383,
  - drag symbol hits: 5.
- It passed statistical gates but failed final holding-quality gates, so it was not added to current.

## Current State

- Current remained unchanged after this batch:
  - strategies: 428,
  - holdings: 3626,
  - outperformers: 213,
  - underperformers kept: 215,
  - persistent outperformers: 213,
  - valuation date: 2026-07-17.

## Lesson

Rolling OOS, random checks, and positive live excess are necessary but not sufficient when the objective is a diversified live pool. A strategy can be statistically valid yet operationally undesirable if the final promoted holdings reuse the same crowded current stocks. Future appends must pass the post-promotion holding audit and use the allowlist path.

## Next Step

- New candidate generators should optimize final holding uniqueness directly, not only candidate-stage overlap.
- Keep post-promotion audit thresholds tight for 5/7 strategies:
  - no drag-symbol leakage,
  - max overlap at or below 25%,
  - current stock reuse share at or below 40%,
  - max current symbol count at or below 8.
