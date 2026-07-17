# 2026-07-17 US round310-311 sectorleader local memory

- stage: strategy-exploration
- kpi_version: us-live-compact-current-20260716
- tags: project:quant-agent-team-us, market:us, freq:daily, strategy:sectorleader, status:failed-experiment
- summary: Added a sectorleader 5/7-stock branch that combines strength/confirmation/risk-guard factor structures with current sector relative strength preselection and loser-exposure suppression. The first implementation was too slow because score adjustments looped per candidate; diagnostic and sector score adjustments were vectorized before running the batch.
- evidence:
  - round310 best rolling IR 1.427789828763856, best random pvalue 0.08559201141226819, promoted 0.
  - round311 best rolling IR 1.1914187511268701, best random pvalue 0.08131241084165478, promoted 0.
  - Current report was regenerated for 2026-07-16 and validation kept 425 strategies, 246 outperformers, 179 underperformers, and holding counts limited to 5/7/10/20.
- decision: Do not promote round310-311. Sector-relative live strength as a preselection overlay did not improve random robustness versus the qmvstrongnodrag near-miss.
- next_step: Prefer qmvstrongnodrag refinements around the round309 near-miss or new non-price data dimensions. Avoid broad sectorleader scans unless adding a more structural sector-neutral historical validation layer.
