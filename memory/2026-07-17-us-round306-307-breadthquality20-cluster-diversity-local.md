# 2026-07-17 US round306-307 breadthquality20 cluster diversity

## Summary

Stage: candidate-pool-diversity

Added candidate-pool strategy-cluster diversity to the `breadthquality20` branch. This limits the number of candidates from the same strategy cluster at the round-selection stage rather than only adjusting individual symbol scores.

No strategy was appended to `current`. Existing current strategies were not deleted or filtered.

## What changed

Added `rank_with_cluster_diversity()`:

- maps `candidate_id` to `strategy_cluster`
- sorts candidates by existing final score
- selects at most two candidates per strategy cluster before deferred same-cluster candidates
- applies only to the `breadthquality20` branch

## Run result

Command:

`python scripts\us_live_strength_strategy_exploration.py --start-round 306 --rounds 2 --candidates-per-round 36 --candidate-limit 3000 --branch breadthquality20 --revisit-historical-candidates --rolling-top-k 18 --null-top-k 18 --null-iter 700 --max-signal-overlap 0.70`

Results:

- round306 best rolling information ratio: 1.1928
- round306 best random significance probability: 0.1041
- round306 promoted strategies: 0
- round307 best rolling information ratio: 0.6513
- round307 best random significance probability: 0.2568
- round307 promoted strategies: 0

Interpretation: candidate-cluster diversity did not improve this branch. It reduced concentration but also pushed weaker clusters into validation. The best result regressed relative to round305's random probability of about 0.0670.

## Current report state

The live report was regenerated after the batch:

- current strategies: 425
- outperformers: 246
- underperformers retained: 179
- persistent outperformers: 246
- valuation date: 2026-07-16
- holding counts: 5/7/10/20 only

## Validation

- `python scripts\tmp_validate_us_live_20260716.py`: passed
- `$env:PYTHONPATH='.'; pytest -q`: 186 passed, 8 skipped
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_generate_live_html_report.py`: passed

## Next step

Stop spending more rounds on minor `breadthquality20` ranking tweaks. The current price/volume-only 20-stock branch appears to be near its ceiling. Next useful work should introduce a genuinely different source of signal or branch:

- sector/industry relative strength using explicit sector-neutral ranking,
- earnings or fundamental quality proxy if data exists,
- or a separate 5/7 branch built around the historically strongest `qmv:ret_120d|px_to_ma20|mfi_14` family but with hard live-drag exclusions.
