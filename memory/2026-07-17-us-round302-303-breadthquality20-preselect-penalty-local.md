# 2026-07-17 US round302-303 breadthquality20 preselect penalty

## Summary

Stage: diagnostic-aware-preselection

Moved diagnostic loser-exposure control from final candidate-row scoring into the stock selection step for the `breadthquality20` branch. The branch now adjusts symbol scores before selecting the top 20 stocks.

No strategy was appended to `current`. Existing current strategies were not deleted or filtered.

## What changed

Added `adjust_scores_for_diagnostic_exposure()`:

- rewards symbols with current winner support
- penalizes symbols with current loser exposure
- works with both symbol-indexed scores and row-indexed scores via an explicit symbol map

The adjustment is applied only to the `breadthquality20` branch before top-20 selection.

## Run result

Command:

`python scripts\us_live_strength_strategy_exploration.py --start-round 302 --rounds 2 --candidates-per-round 36 --candidate-limit 3000 --branch breadthquality20 --revisit-historical-candidates --rolling-top-k 18 --null-top-k 18 --null-iter 700 --max-signal-overlap 0.70`

Result:

- round302 candidate file: `E:\quant-agent-team-us\research\2026-07-17-round302-live-strength-candidates.csv`
- best rolling information ratio: 1.3350
- best random significance probability: 0.0756
- promoted strategies: 0
- promoted holdings: 0

Progress versus prior breadthquality20 runs:

- round298 baseline best rolling information ratio: about 1.0539
- round300 final-row diagnostic scoring: about 1.1928
- round302 preselection diagnostic penalty: about 1.3350

Random significance probability improved from about 0.1612 to 0.0956 to 0.0756, but still did not pass the promotion gate.

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

This direction is improving but not yet promotable. Next iteration should add a stricter high-loser-exposure cap before top-20 selection or combine the diagnostic penalty with strategy-cluster diversity. Do not add round302 candidates to current unless random/null significance and rolling OOS gates are passed.
