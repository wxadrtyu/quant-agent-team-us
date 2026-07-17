# 2026-07-15 US Continued Exploration Round 97-106 Local Memory

## Summary

Continued US strategy exploration after the user clarified that live-pool strategies must not be deleted unless explicitly requested. Restored the current report to the full observation pool and kept the compact 73-strategy pool as a separate view.

## Stage

strategy-research / live-monitoring

## KPI Version

US daily large-mid tradable universe, dynamic-liquidity survivorship-reduced snapshot. Research and live report still use the complete 2026-07-12 raw snapshot with prices through 2026-07-10 because the 2026-07-15 Yahoo refresh only covered 80 symbols and was rejected.

## No-Delete Handling

- Restored `us_live_monitoring_strategies_current` from the full pre-prune backup.
- Restored `us_live_monitoring_holdings_current` from the full pre-prune backup.
- Preserved the 73-strategy compact pool as:
  - `us_live_monitoring_strategies_compact_2026_07_15`
  - `us_live_monitoring_holdings_compact_2026_07_15`

## Exploration Result

- Marginal compact rounds 83-92: 78 candidates passed historical rolling/random checks before live filtering, but all failed the 2026-06-30 to 2026-07-10 live excess gate. No strategies were added.
- Continued quality-stability rounds 97-102: 57 candidates passed historical rolling/random checks before live filtering, but all failed the live excess gate. No strategies were added.
- Fresh quality-stability rounds 103-106: added 6 strategies and 57 holdings.
- Round 96 from the interrupted prior run had already added 1 strategy and 5 holdings.
- Added round96 and round103-106 strategies to the current full observation report.

## Current State

- `us_live_monitoring_strategies_current`: 280 rows.
- `us_live_monitoring_holdings_current`: 2814 rows.
- `us_live_pool_strategies`: 336 rows.
- `us_live_pool_holdings`: 3674 rows.
- Current holding distribution: 5 holdings: 43 strategies, 7 holdings: 77 strategies, 10 holdings: 114 strategies, 20 holdings: 46 strategies.
- Current minimum live excess return: 0.0003172228817951428.
- Current average information ratio: 2.069258681758264.
- Current median maximum drawdown: 0.15025141204230008.

## Verification

- Current report regenerated with 280 strategies and 2814 holdings.
- No current strategy has non-positive live excess return.
- No fallback `美股` stock display names remain.
- Holding counts remain only 5, 7, 10, and 20.
- `pytest tests/test_us_live_pool.py tests/test_us_rolling_validation.py tests/test_us_null_overfit_check.py tests/test_us_research_db_ingest.py tests/test_us_universe.py tests/test_us_model_portfolio.py tests/test_us_overlap_aware_monitoring_review.py -q` passed with 19 tests.

## Lessons

- Forcing marginal diversification away from the current pool is not enough; recent live-window behavior rejected all 83-92 marginal candidates.
- Historical rolling/random quality can remain strong while the fixed live window rejects every candidate, so the live excess gate is still doing important work.
- Continue additively. Do not delete or hide existing live-pool observations.

## Tags

project:quant-agent-team-us, market:us, freq:daily, stage:strategy-research, status:validated

## Next Step

Continue with smaller batches and inspect live-window failure patterns every 4-6 rounds. Favor structures that improve both historical validation and the 2026-06-30 live window without replacing or deleting existing live-pool records.
