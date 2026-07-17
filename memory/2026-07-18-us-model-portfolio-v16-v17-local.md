# 2026-07-18 US model portfolio v16-v17 local memory

## Summary

- Added a model-portfolio filter for maximum allowed dominant strategy-cluster share.
- Built stricter low-correlation core model portfolios.
- Did not modify current strategy pool.

## Code Change

- `scripts/us_build_current_model_portfolio.py` now supports `max_allowed_cluster_share`.
- CLI flag added: `--max-allowed-cluster-share`.
- The filter is only applied when enough symbols remain for the requested target size.

## Outputs

- `reports/us/live/current/us_current_model_portfolio_20260717_v16_core5_cluster075.csv`
  - 5 symbols,
  - drag symbols: 0,
  - min cluster count: 2,
  - largest cluster share: about 67.76%,
  - issue: target single-stock and sector caps were too tight for a 5-stock portfolio and were exceeded after redistribution.
- `reports/us/live/current/us_current_model_portfolio_20260717_v17_core5_cluster075.csv`
  - 5 symbols,
  - drag symbols: 0,
  - max single-stock weight: 30%,
  - max sector weight: 50%,
  - min cluster count: 2,
  - largest cluster share: about 67.76%.

## Current State

- current strategies: 430,
- current holdings: 3636,
- outperformers: 215,
- underperformers kept: 215,
- persistent outperformers: 215,
- valuation date: 2026-07-17.

## Decision

The v17 core5 portfolio is the strictest low-cluster-correlation model candidate so far. It is concentrated by design because strict cluster-share filtering leaves only a small set of clean names. It should be treated as a portfolio-layer research candidate, not a replacement for the current strategy pool.

## Next Step

- To get back to 10 or 20 names with strict cluster-share control, the system needs more non-price-volume alpha families or more diverse persistent outperforming strategy clusters.
