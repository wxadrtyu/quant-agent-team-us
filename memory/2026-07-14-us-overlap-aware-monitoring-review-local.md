# 2026-07-14 US Overlap-Aware Monitoring Review Local Memory

## Summary

The current US live monitoring pool has 273 live-outperforming strategies, but many of the strongest strategies share similar signal-date holdings. A new overlap-aware review layer was added to preserve strong strategies while reducing redundant exposure.

## Stage

portfolio-selection / live-monitoring-review

## KPI Version

US daily large-mid tradable universe, dynamic-liquidity survivorship-reduced snapshot, live signal date 2026-06-30, entry 2026-07-01 open, valuation 2026-07-10 close.

## Implementation

- Added `scripts/us_overlap_aware_monitoring_review.py`.
- Added `tests/test_us_overlap_aware_monitoring_review.py`.
- The script reads `us_live_monitoring_strategies_current` and `us_live_monitoring_holdings_current`.
- It writes review tables without replacing the current official monitoring tables:
  - `us_live_monitoring_overlap_selected_current`
  - `us_live_monitoring_overlap_holdings_current`
  - `us_live_monitoring_overlap_review_current`
- It also exports CSV reports under `reports/us/live/current`.

## Result

Using target count 80 and maximum Jaccard holding overlap 0.70:

- Reviewed strategies: 273
- Suggested keep: 73
- Delayed observation: 200
- Selected holdings: 787
- Holding count distribution: 5 holdings: 8 strategies, 7 holdings: 11 strategies, 10 holdings: 41 strategies, 20 holdings: 13 strategies.
- Minimum live excess return among selected strategies: 0.0003172228817951428.

## Lessons

- A strict 0.55 overlap threshold selected only 45 strategies and was too conservative for monitoring breadth.
- A 0.70 threshold selected 73 strategies, kept average rolling quality similar, and still reduced redundant holdings compared with the full 273-strategy pool.
- This review layer should be used for candidate pruning and human review before replacing the current monitoring pool.

## Verification

- `pytest tests/test_us_live_pool.py tests/test_us_rolling_validation.py tests/test_us_null_overfit_check.py tests/test_us_research_db_ingest.py tests/test_us_universe.py tests/test_us_model_portfolio.py tests/test_us_overlap_aware_monitoring_review.py -q` passed with 19 tests.
- `python -m py_compile` passed for the US live, rolling, null-check, report, and overlap-aware review scripts.

## Tags

project:quant-agent-team-us, market:us, freq:daily, stage:portfolio-selection, status:validated

## Next Step

Use the overlap-aware selected set as the review candidate for a compact monitoring pool, but do not replace the official current monitoring table until the user explicitly approves the pruning.
