# 2026-07-18 US low-correlation round328-330 local memory

## Summary

- Continued low-correlation exploration after adding post-promotion holding audit.
- Current was not modified in this batch.
- Report was regenerated and validated for valuation date 2026-07-17.

## Exploration

- Round 328-329:
  - branch: cleanmomentum,
  - max candidate overlap: 0.20,
  - result: no candidate rounds generated.
- Round 330-331:
  - branch: qmvstableflow,
  - max candidate overlap: 0.20,
  - result: 1 candidate round generated,
  - best rolling IR: about 1.35,
  - best random-test p-value: about 0.097,
  - promoted strategies: 0.

## Current State

- current strategies: 428,
- current holdings: 3626,
- outperformers: 213,
- underperformers kept: 215,
- persistent outperformers: 213,
- holding counts remain within 5/7/10/20.

## Lesson

With strict low-correlation constraints, the existing price-volume factor space is becoming sparse. Clean momentum produced no viable low-overlap candidates, and stable QMV/flow candidates failed statistical quality. Continuing to hard-scan the same branches is likely to add multiple-testing risk without producing genuinely new live candidates.

## Next Step

- Do not keep sweeping cleanmomentum or qmvstableflow under the same settings.
- Next useful work should either:
  - make the promotion stage reproduce branch-specific candidate score adjustments so candidate-stage low overlap survives into final holdings, or
  - introduce a new data/factor family beyond the current price-volume panel.
