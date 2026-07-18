# 2026-07-18 US low-correlation gated exploration round349-356

## Summary

- Ran strategy exploration on branch `codex/v1.1` after low-correlation admission gates were added.
- No strategies were appended to current.
- current remains unchanged at 430 strategies and 3636 holdings.

## Runs

- round349-350 `decorrelated`:
  - round349 best rolling information ratio: 1.1551.
  - round349 best random p-value: 0.0858.
  - round350 best rolling information ratio: 0.9472.
  - round350 best random p-value: 0.1377.
  - No promoted strategies.
- round351-352 `qmvstableflow`:
  - No candidate rounds after low-correlation hard filtering.
- round353-354 `cleanmomentum`:
  - No candidate rounds after low-correlation hard filtering.
- round355-356 `breadthquality20`:
  - No candidate rounds after low-correlation hard filtering.

## Decision

- Do not continue sweeping old price-volume families under the same constraints.
- The low-correlation gate is working: older strong-flow and clean-momentum families are too overlapped with current or too correlated to produce independent additions.
- The closest result remains round349, but random significance did not pass. It should not be admitted.

## Verification

- Current validation passed:
  - 430 current strategies.
  - 3636 current holdings.
  - 215 outperformers.
  - 215 underperformers retained.
  - holding counts only 5/7/10/20.
  - no fallback names.

## Next Step

- Stop scanning existing price-volume branches.
- Next productive work should add a genuinely new data or factor source, such as fundamentals, earnings revision proxies, analyst estimates, short interest, options, or news/event data.
- If no new external data is available, continue with portfolio-level aggregation and risk controls rather than adding more single-strategy variants.
