# 2026-07-18 US model portfolio v18-v21 local memory

## Summary

- Continued model-portfolio layer work without modifying current.
- The heartbeat automation prompt was updated from stale round295/current425 instructions to current round339/current430 instructions.
- Current validation stayed unchanged:
  - current strategies: 430,
  - holdings: 3636,
  - outperformers: 215,
  - underperformers kept: 215,
  - valuation date: 2026-07-17.

## Outputs

- `us_current_model_portfolio_20260717_v18_core7_cluster075`
  - 7 symbols,
  - drag symbols: 0,
  - but strict `max_allowed_cluster_share <= 0.75` was not feasible; largest cluster share was about 84.22%.
- `us_current_model_portfolio_20260717_v19_core6_cluster075`
  - 6 symbols,
  - drag symbols: 0,
  - strict 0.75 cluster-share target was still not feasible; largest cluster share was about 84.22%.
- `us_current_model_portfolio_20260717_v20_core10_cluster085`
  - 10 symbols,
  - drag symbols: 0,
  - 0.85 cluster-share target was not quite feasible; largest cluster share was about 86.64%.
- `us_current_model_portfolio_20260717_v21_core10_cluster087`
  - 10 symbols,
  - drag symbols: 0,
  - max single-stock weight: 11%,
  - max sector weight: 30%,
  - min cluster count: 2,
  - largest cluster share: about 86.64%.

## Feasibility Boundary

Using the v13 candidate universe:

- `max_cluster_share <= 0.75` supports only 5 names.
- `max_cluster_share <= 0.85` supports 9 names.
- `max_cluster_share <= 0.87` supports 10 names.

## Decision

- v17 remains the strictest clean core: 5 names, largest cluster share about 67.76%.
- v21 is the best 10-name compromise: 10 names, drag symbols 0, largest cluster share about 86.64%.

## Next Step

- To build a 10-20 name portfolio with stricter cluster-share control, the system needs more diverse alpha clusters or additional non-price-volume factor families.
