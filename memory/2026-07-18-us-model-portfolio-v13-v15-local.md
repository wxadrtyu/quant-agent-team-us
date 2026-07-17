# 2026-07-18 US model portfolio v13-v15 local memory

## Summary

- Built model-portfolio candidates from persistent outperforming current strategies.
- Did not modify current strategy pool.
- Current validation stayed unchanged:
  - current strategies: 430,
  - holdings: 3636,
  - outperformers: 215,
  - underperformers kept: 215,
  - valuation date: 2026-07-17.

## Outputs

- `reports/us/live/current/us_current_model_portfolio_20260717_v13.csv`
  - 20 symbols,
  - max single-stock weight: 7%,
  - max sector weight: about 22.37%,
  - drag symbols: 0,
  - issue: several names had `cluster_count=1`, so strategy-cluster diversification was not strong enough.
- `reports/us/live/current/us_current_model_portfolio_20260717_v14_core10.csv`
  - 10 symbols,
  - all symbols had at least 2 strategy clusters,
  - drag symbols: 0,
  - issue: tight 10% single-stock and 25% sector caps were slightly exceeded during redistribution.
- `reports/us/live/current/us_current_model_portfolio_20260717_v15_core10.csv`
  - 10 symbols,
  - total weight: 100%,
  - max single-stock weight: 11%,
  - max sector weight: 30%,
  - drag symbols: 0,
  - min cluster count: 2.

## Decision

The v15 core10 portfolio is the cleaner low-correlation model candidate. It is not a replacement for the current single-strategy pool, but it is a useful portfolio-layer candidate because every symbol has multi-cluster support and no drag-symbol exposure.

## Next Step

- If continuing portfolio-layer work, build a stricter v16 that explicitly filters or penalizes `max_cluster_share > 0.75` instead of only requiring `cluster_count >= 2`.
- Do not treat the 20-stock v13 as the preferred low-correlation portfolio because it includes single-cluster-supported names.
