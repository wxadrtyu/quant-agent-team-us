# 2026-07-18 US low-correlation strategy exploration local memory

## Summary

- Added a `decorrelated` branch to `scripts/us_live_strength_strategy_exploration.py`.
- The branch lowers overlap pressure by:
  - penalizing stocks already frequently held by current strategies,
  - recording current stock reuse share and decorrelation score,
  - limiting repeated strategy clusters with `max_per_cluster=1`,
  - requiring low-congestion factor structures and 5/7-stock baskets.
- Fixed live exploration valuation date to `2026-07-17`.
- Fixed `scripts/us_explore_strategy_rounds.py` so promotion uses the same `2026-07-17` raw data and explicit valuation date as candidate generation.

## Results

- Round 316-317, max overlap 0.35:
  - promoted 2 strategies before the promotion-date fix,
  - appended to current as `2026-07-17-current-compact-add-round316-317`.
- Round 318-319, max overlap 0.25:
  - promoted 1 strategy before the promotion-date fix,
  - appended to current as `2026-07-17-current-compact-add-round318-319`.
- After revaluation:
  - current strategies: 428,
  - current holdings: 3626,
  - outperforming: 213,
  - underperforming kept: 215,
  - persistent outperforming: 213,
  - holding count distribution: 5=97, 7=123, 10=188, 20=20.
- Round 320-321 after the promotion-date fix:
  - promoted 0 strategies,
  - best rolling IR was below production quality and random-test p-values were weak.

## Lesson

The first three appended low-correlation strategies passed candidate screening under `2026-07-17` generation, but promotion had still used the stale `2026-07-16` raw directory in `us_explore_strategy_rounds.py`. That date mismatch caused holdings to be reselected with a different live frame and introduced repeated drag symbols such as HON, JEF, DUOL, VIRT, ON, and IBKR. Per user rule, these already admitted strategies were not deleted. Future promotion now uses the same latest raw directory and explicit valuation date to avoid this mismatch.

## Next Step

- Do not keep sweeping the same `decorrelated` structure without a new alpha dimension.
- Next exploration should add a hard post-promotion holding audit before append:
  - no stale raw directory,
  - no drag-symbol leakage for 5/7-stock strategies,
  - max overlap and current-stock-reuse checks using the final promoted holdings,
  - only then append to current.
