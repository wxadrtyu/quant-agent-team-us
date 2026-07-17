# 2026-07-16 US Compact Plus Continued Round 107-118 Local Memory

## Summary

User clarified the current report should be compact: original 73 compact strategies plus the 7 most recent live-pool additions, while historical live-pool records must not be deleted. The current monitoring report was switched to this compact-plus-new policy and exploration continued additively.

## Stage

strategy-research / live-monitoring

## KPI Version

US daily large-mid tradable universe, dynamic-liquidity survivorship-reduced snapshot. Research and live report still use the complete 2026-07-12 raw snapshot with prices through 2026-07-10 because the 2026-07-15 Yahoo refresh only covered 80 symbols and was rejected.

## Current Pool Policy

- Current report should start from the 73-strategy compact pool.
- New live-pool strategies are screened and appended to current compact observation after promotion.
- Existing live-pool records are not deleted unless the user explicitly requests deletion.
- Full observation backups remain available:
  - `us_live_monitoring_strategies_full_2026_07_16_before_compact_switch`
  - `us_live_monitoring_holdings_full_2026_07_16_before_compact_switch`

## Result

- Rebuilt current report from 73 compact strategies plus 7 recent additions: 80 strategies.
- Rounds 107-110:
  - Round 107: 0 promoted.
  - Round 108: 0 promoted.
  - Round 109: 2 promoted.
  - Round 110: 1 promoted.
  - Added 3 strategies and 30 holdings to current compact observation.
- Rounds 111-114:
  - Round 111: 7 promoted.
  - Round 112: 1 promoted.
  - Round 113: 0 promoted.
  - Round 114: 0 promoted.
  - Added 8 strategies and 77 holdings to current compact observation.
- Rounds 115-118:
  - No strategies promoted, despite strong historical rolling metrics in several rounds.

## Current State

- `us_live_monitoring_strategies_current`: 91 rows.
- `us_live_monitoring_holdings_current`: 956 rows.
- `us_live_pool_strategies`: 347 rows.
- `us_live_pool_holdings`: 3781 rows.
- Current holding distribution: 5 holdings: 9 strategies, 7 holdings: 13 strategies, 10 holdings: 56 strategies, 20 holdings: 13 strategies.
- Current minimum live excess return: 0.0003172228817951428.
- Current average information ratio: 2.119996154251759.
- Current median maximum drawdown: 0.1416488344859729.

## Verification

- Current report regenerated with 91 strategies and 956 holdings.
- No current strategy has non-positive live excess return.
- No fallback `美股` stock display names remain.
- Holding counts remain only 5, 7, 10, and 20.
- `pytest tests/test_us_live_pool.py tests/test_us_rolling_validation.py tests/test_us_null_overfit_check.py tests/test_us_research_db_ingest.py tests/test_us_universe.py tests/test_us_model_portfolio.py tests/test_us_overlap_aware_monitoring_review.py -q` passed with 19 tests.
- Python compilation passed for the live/report/exploration scripts.

## Lessons

- Strong historical rolling information ratio alone is insufficient; rounds 107, 108, and 115-118 showed high rolling quality but no final live-passing promotion.
- The productive recent additions came from quality-stability rounds 109-112, especially variants of momentum plus short pullback plus trend/risk/liquidity.
- Continue in small batches and append only live-passing promoted strategies to the compact current report.

## Tags

project:quant-agent-team-us, market:us, freq:daily, stage:strategy-research, status:validated

## Next Step

Continue rounds 119+ in small batches. After each batch, append promoted live-passing strategies to current compact observation, regenerate the report, validate, and record promoted versus rejected counts.
