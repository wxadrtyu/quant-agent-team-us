# 2026-07-18 US relative factor exploration round341-346

## Summary

- Added explicit sector-relative factor family to avoid only reordering old price-volume templates:
  - `sector_rel_ret_20d`
  - `sector_rel_ret_60d`
  - `sector_rel_drawdown_20d`
- Added candidate templates:
  - `relativeleader`: sector-relative strength continuation.
  - `relativerepair`: sector-relative pullback repair with trend/risk confirmation.
- round341-344 `relativeleader` produced no rolling candidates after live-strength screening. Diagnostics showed it selected semiconductor-chain leaders such as AMAT/LRCX/KLAC that underperformed badly from 2026-06-30 to 2026-07-17.
- round345-346 `relativerepair` produced candidates but no promoted strategies:
  - round345 best rolling information ratio: 0.9560, random p-value: 0.4351.
  - round346 best rolling information ratio: 1.2971, random p-value: 0.0813.

## Decision

- Do not append any round341-346 strategies to current.
- Sector-relative continuation is rejected for now because current live window treats recent industry leaders, especially semiconductor equipment, as crowded reversal risk.
- Sector-relative repair is directionally better but still lacks enough random-test significance.

## Current State

- Current pool remains 430 strategies and 3636 holdings.
- Latest report regenerated for valuation date 2026-07-17:
  - `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0717.html`
- Validation passed:
  - outperformers: 215
  - underperformers kept: 215
  - persistent outperformers: 215
  - invalid holding count: 0
  - fallback names: false

## Next Step

- Do not hard-sweep `relativeleader`.
- If continuing sector-relative work, focus on repair plus explicit semiconductor/hardware-chain avoidance or cluster-diversified 7-stock baskets.
- Better next research direction: build portfolio-level correlation controls from persistent winners and/or add return-correlation factors instead of adding more same-source price templates.
