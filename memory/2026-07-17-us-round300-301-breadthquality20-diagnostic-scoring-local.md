# 2026-07-17 US round300-301 breadthquality20 diagnostic scoring

## Summary

Stage: diagnostic-aware-exploration

Added diagnostic-aware scoring to the `breadthquality20` branch. The scoring now uses current monitoring evidence directly:

- reward symbols with persistent winner support
- penalize symbols with loser exposure
- include net support in candidate ranking

No strategy was appended to `current`. Existing current strategies were not deleted or filtered.

## What changed

Added:

- `load_current_symbol_exposure()`
- `diagnostic_support_metrics()`
- `winner_support_score`
- `loser_exposure_score`
- `net_support_score`

These metrics are included in candidate rows and `candidate_quality_score()`.

## Run result

Command:

`python scripts\us_live_strength_strategy_exploration.py --start-round 300 --rounds 2 --candidates-per-round 36 --candidate-limit 3000 --branch breadthquality20 --revisit-historical-candidates --rolling-top-k 18 --null-top-k 18 --null-iter 700 --max-signal-overlap 0.70`

Result:

- round300 candidate file: `E:\quant-agent-team-us\research\2026-07-17-round300-live-strength-candidates.csv`
- best rolling information ratio: 1.1928
- best random significance probability: 0.0956
- promoted strategies: 0
- promoted holdings: 0

Compared with round298 breadthquality20:

- best rolling information ratio improved from about 1.0539 to 1.1928
- random probability improved from about 0.1612 to 0.0956
- still did not pass the promotion gate

Interpretation: diagnostic-aware scoring is directionally useful, but not strong enough to justify adding strategies to current.

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
- `$env:PYTHONPATH='.'; pytest -q`: 184 passed, 8 skipped
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_generate_live_html_report.py`: passed

## Next step

Do not add round300 to current. The next branch should not only score diagnostics after picks are formed. It should use diagnostics before scoring or during symbol ranking:

- explicitly subtract loser-exposure symbols from scores before selecting top 20
- add a hard cap for high loser-minus-winner exposure names
- preserve sector and cluster diversity

This likely requires a branch-specific pick transform rather than only final-row scoring.
