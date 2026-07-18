# 2026-07-18 US correlation controlled model portfolios v22-v23

## Summary

- Added optional pairwise return-correlation control to `scripts/us_build_current_model_portfolio.py`.
- Correlation is computed from local daily close returns, default 120 trading days.
- The selector now prefers lower-correlation symbols before falling back only if the target symbol count cannot be filled.

## Outputs

- `reports/us/live/current/us_current_model_portfolio_20260717_v22_corr085_core10.csv`
  - 10 symbols.
  - Drag symbols: 0.
  - Largest symbol weight: 11%.
  - Largest sector weight: 28.80%.
  - Largest strategy-cluster share: 86.64%.
  - Actual max absolute 120-day pairwise correlation: 0.6072, pair DOW/OXY.
- `reports/us/live/current/us_current_model_portfolio_20260717_v23_corr060_core7.csv`
  - 7 symbols.
  - Drag symbols: 0.
  - Largest symbol weight: 16%.
  - Largest sector weight: 27.35%.
  - Largest strategy-cluster share: 86.64%.
  - Actual max absolute 120-day pairwise correlation: 0.3888, pair GS/R.

## Decision

- v23 is cleaner for the user's low-correlation requirement because it achieves much lower realized pairwise correlation with no drag symbols.
- v22 remains useful as a broader 10-stock reference, but includes MSTR and CRCL and has higher realized pairwise correlation.
- Neither model portfolio modifies current; they are candidate aggregation reports built from persistent winning 5/7 strategies.

## Verification

- `pytest -q tests/test_us_strategy_factory_factors.py tests/test_us_live_strength_strategy_exploration.py tests/test_us_current_model_portfolio.py tests/test_us_model_portfolio.py`: 38 passed, 2 subtests passed.
- `scripts/us_validate_live_current.py`: 430 current strategies, 3636 holdings, 215 outperformers, 215 underperformers retained, invalid holding count 0, no fallback names.

## Next Step

- Prefer v23-style correlation-controlled aggregation for user review.
- If continuing strategy discovery, use the round341-346 lesson: sector-relative continuation was crowded and failed live; sector-relative repair was directionally better but failed random significance.
