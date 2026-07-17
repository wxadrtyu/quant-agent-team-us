# 2026-07-18 US low-correlation selected-symbols round331-334 local memory

## Summary

- Fixed the candidate-to-promotion mismatch by writing `selected_symbols` into live-strength candidate CSV rows.
- Updated `build_signal_holdings_and_live_metrics` to use `selected_symbols` when present, so final promoted holdings match candidate-stage low-overlap selections.
- Added stronger current-crowding penalty to `sectorleader`.

## Exploration

- Round 331-332:
  - branch: sectorleader,
  - max candidate overlap: 0.20,
  - round 332 promoted 1 strategy, but post-promotion audit rejected it.
  - Rejection was no longer basket overlap or drag leakage; max overlap was 13.33% and drag hits were 0, but current stock reuse was 85.71% and max current symbol count was 25.
- Round 333-334:
  - branch: sectorleader with stronger current-crowding penalty,
  - both rounds promoted 1 strategy each,
  - both passed post-promotion audit and were appended to current.

## New Strategies Added

- Added 2 low-correlation 5-stock strategies via allowlist:
  - average live excess: about 9.97%,
  - minimum live excess: about 9.19%,
  - max current basket overlap: 5.26%,
  - current stock reuse share: 10.00%,
  - max current symbol count: 4,
  - drag symbol hits: 0.

## Current State

- current strategies: 430,
- current holdings: 3636,
- outperformers: 215,
- underperformers kept: 215,
- persistent outperformers: 215,
- valuation date: 2026-07-17,
- holding counts remain within 5/7/10/20.

## Lesson

Preserving the exact candidate-stage selected symbols is necessary when candidate scoring includes branch-specific symbol-level adjustments. Otherwise promotion can rebuild a different, more crowded basket from raw factor weights. After preserving selected symbols and increasing current-crowding penalties, the same sectorleader family produced genuinely low-overlap additions.

## Next Step

- Continue from round335 with the selected-symbols promotion fix in place.
- Prefer sectorleader variants with current-crowding penalty or new branches that explicitly minimize current stock reuse.
- Keep post-promotion audit mandatory before any append.
