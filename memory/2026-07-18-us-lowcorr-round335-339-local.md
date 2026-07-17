# 2026-07-18 US low-correlation round335-339 local memory

## Summary

- Continued exploration after selected-symbols promotion fix.
- No new strategies were appended to current in this batch.
- Current report was regenerated and validated.

## Exploration

- Round 335-336:
  - branch: sectorleader,
  - max candidate overlap: 0.20,
  - candidate limit: 110000,
  - promoted strategies: 0.
- Round 337-338:
  - branch: decorrelated,
  - max candidate overlap: 0.20,
  - candidate limit: 110000,
  - promoted strategies: 0.
- Round 339-340:
  - branch: smoothquality,
  - max candidate overlap: 0.20,
  - candidate limit: 110000,
  - only one round generated,
  - promoted strategies: 0.

## Current State

- current strategies: 430,
- current holdings: 3636,
- outperformers: 215,
- underperformers kept: 215,
- persistent outperformers: 215,
- valuation date: 2026-07-17.

## Lesson

The selected-symbols fix solved the candidate-to-promotion consistency issue, but strict low-correlation constraints still leave limited alpha in the current price-volume branch set. Sectorleader, decorrelated, and smoothquality did not produce additional statistically qualified strategies after round334. Continuing to scan the same settings is likely low value.

## Next Step

- Avoid further hard-sweeping sectorleader/decorrelated/smoothquality with the same factor families and overlap limits.
- Next productive direction should be a new factor family or a model portfolio layer using existing persistent outperformers with explicit stock and strategy-cluster constraints.
