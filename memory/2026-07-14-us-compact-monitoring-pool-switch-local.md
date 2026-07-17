# 2026-07-14 US Compact Monitoring Pool Switch Local Memory

## Summary

The user approved the overlap-aware monitoring review direction. The current US live monitoring main tables were switched from the full 273-strategy pool to the 73-strategy overlap-aware compact pool.

## Stage

live-monitoring / portfolio-selection

## KPI Version

US daily large-mid tradable universe, dynamic-liquidity survivorship-reduced snapshot, live signal date 2026-06-30, entry 2026-07-01 open, valuation 2026-07-10 close.

## Database Changes

- Backed up the prior full current pool:
  - `us_live_monitoring_strategies_full_2026_07_14_before_overlap_prune`: 273 rows.
  - `us_live_monitoring_holdings_full_2026_07_14_before_overlap_prune`: 2752 rows.
- Replaced the current monitoring main tables with the overlap-aware selected pool:
  - `us_live_monitoring_strategies_current`: 73 rows.
  - `us_live_monitoring_holdings_current`: 787 rows.

## Current Compact Pool

- Strategy count: 73.
- Holding rows: 787.
- Holding distribution: 5 holdings: 8 strategies, 7 holdings: 11 strategies, 10 holdings: 41 strategies, 20 holdings: 13 strategies.
- Minimum live excess return: 0.0003172228817951428.
- Average information ratio: 2.1609648322460515.
- Median maximum drawdown: 0.1422155800939541.

## Report

Regenerated current reports:

- `reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`
- `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`
- `reports/us/live/current/us_simulation_formal_monitoring_simple_0630_0710.html`

## Verification

- Report strategy count: 73.
- Report holding rows: 787.
- No strategy in the current report has non-positive live excess return.
- Holding counts are only 5, 7, 10, and 20.
- No fallback `美股` display names remain.
- No `NaN`, `Infinity`, `__PLACEHOLDER__`, or `TBD` tokens remain.
- `pytest tests/test_us_live_pool.py tests/test_us_rolling_validation.py tests/test_us_null_overfit_check.py tests/test_us_research_db_ingest.py tests/test_us_universe.py tests/test_us_model_portfolio.py tests/test_us_overlap_aware_monitoring_review.py -q` passed with 19 tests.
- `python -m py_compile` passed for the US live/report/research scripts.

## Tags

project:quant-agent-team-us, market:us, freq:daily, stage:live-monitoring, status:validated

## Next Step

Continue strategy research against the compact current pool. New strategies should be judged by whether they improve marginal quality and diversification relative to the 73-strategy compact pool, not merely by standalone backtest quality.
