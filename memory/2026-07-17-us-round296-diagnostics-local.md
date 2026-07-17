# 2026-07-17 US round296 diagnostics

## Summary

Stage: diagnostics-before-new-branch

This heartbeat did not change `current` and did not delete any strategy. It performed a read-only diagnosis of the 2026-07-16 current monitoring pool after the v13 model portfolio work.

## Current state

- Current strategies: 425
- Current outperformers: 246
- Underperformers retained: 179
- Persistent outperformers: 246
- Valuation date: 2026-07-16
- Holding counts remain limited to 5/7/10/20

## Cluster diagnosis

Strong clusters:

- `qmv:ret_120d|px_to_ma20|mfi_14`: 15 strategies, 15 winners, average live excess about +4.62%.
- `balanced:ret_120d|ret_5d|px_to_ma20`: 86 strategies, 78 winners, average live excess about +2.18%, but this is already crowded and should not be copied blindly.

Weak clusters with enough sample size:

- `pulltrend:ret_5d|px_to_ma60|ret_120d`: 5 strategies, 0 winners, average live excess about -3.47%.
- `balanced:ret_120d|ret_5d|turnover_stability_20d`: 14 strategies, 2 winners, average live excess about -2.99%.
- `balanced:ret_120d|ret_5d|ret_skew`: 5 strategies, 1 winner, average live excess about -2.63%.
- `balanced:ret_120d|px_to_ma60|turnover_stability_20d`: 11 strategies, 2 winners, average live excess about -2.55%.
- `pulltrend:ret_5d|px_to_ma20|ret_120d`: 20 strategies, 6 winners, average live excess about -1.49%.

Interpretation: the recent underperformance is not only single-name noise. It is also coming from old pullback/mean-reversion-like structures that combine long momentum with short pullback and broad moving-average distance. These structures should be avoided or explicitly protected by stronger current-strength and failure-protection filters.

## Stock exposure diagnosis

Highest loser-minus-winner exposure:

- ARM: +11.89
- DELL: +8.60
- ALB: +2.89
- AA: +2.69
- WFRD: +2.17
- CLF: +1.60
- ARW: +1.55
- BWA: +1.19
- LBRDK: +1.19
- ON: +1.01

These should be treated as live drag exposure in future candidate ranking. They should not automatically ban all related strategies, but new candidates with concentrated exposure here need a higher evidence bar.

## Files

- `reports/us/live/current/us_current_diagnostics_20260716_round296.csv`
- `reports/us/live/current/us_current_cluster_diagnostics_20260716_round296.csv`

## Next branch design

Do not implement another minor rearrangement of the existing pullback/trend templates. The next candidate branch should be one of:

1. `cleanmomentum`: keep medium/long momentum but require positive current relative strength, close-position confirmation, and explicit exclusion/penalty for the weak pullback clusters above.
2. `breadthquality20`: 20-stock stabilizer branch that ranks symbols by persistent winner support, low loser exposure, sector cap, and cluster diversity, then backtests as a true 20-stock candidate rather than a post-hoc model portfolio.
3. `dragawarestrong`: 5/7-stock strong-selection branch that keeps the proven qmv/liquidity core but applies a higher evidence threshold to ARM/DELL/ALB/AA/WFRD/CLF/ON exposure.

Recommended next step: implement `cleanmomentum` first because it targets the observed weak cluster failure directly while preserving the medium-term trend principle that still works in the best qmv and balanced clusters.
