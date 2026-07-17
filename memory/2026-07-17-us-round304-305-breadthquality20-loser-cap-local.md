# 2026-07-17 US round304-305 breadthquality20 loser cap

## Summary

Stage: diagnostic-aware-preselection

Added a hard high-loser-exposure cap to the `breadthquality20` preselection adjustment. This keeps obvious current underperformer-exposure symbols out of the top-20 selection before candidate validation.

No strategy was appended to `current`. Existing current strategies were not deleted or filtered.

## What changed

`adjust_scores_for_diagnostic_exposure()` now supports `max_loser_exposure`. If a symbol's current loser exposure exceeds the cap, its score is set to negative infinity before top-N selection.

For `breadthquality20`, the current cap is `6.0`.

## Run result

Command:

`python scripts\us_live_strength_strategy_exploration.py --start-round 304 --rounds 2 --candidates-per-round 36 --candidate-limit 3000 --branch breadthquality20 --revisit-historical-candidates --rolling-top-k 18 --null-top-k 18 --null-iter 700 --max-signal-overlap 0.70`

Results:

- round304 best rolling information ratio: 1.1928
- round304 best random significance probability: 0.1041
- round304 promoted strategies: 0
- round305 best rolling information ratio: 1.3350
- round305 best random significance probability: 0.0670
- round305 promoted strategies: 0

Interpretation: the loser cap does not degrade the best rolling result and improves the best random probability from round302's 0.0756 to 0.0670, but it still does not pass the promotion gate. Do not add these candidates to current.

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
- `$env:PYTHONPATH='.'; pytest -q`: 185 passed, 8 skipped
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_generate_live_html_report.py`: passed

## Next step

The `breadthquality20` line has improved in three iterations but still fails the random/null gate. Do not keep tuning only loser-exposure coefficients. The next useful change is strategy-cluster diversity during top-20 construction, or a new alpha source outside the current price/volume factor family.
