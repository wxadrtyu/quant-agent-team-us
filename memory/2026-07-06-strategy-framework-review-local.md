---
type: review-decision
stage: strategy-framework-audit
kpi_version: unknown
tags:
  - project:quant-agent-team
  - market:cn_a
  - freq:daily
  - stage:strategy-framework-audit
  - status:local-memory-fallback
---

summary: >
  2026-07-06 audit of the strategy production framework found the architecture direction
  reasonable but current production strategy results are not reliable enough for monitoring
  or live use without remediation. Strengths: causal IC weighting, monthly rolling OOS
  reports, benchmark-relative IR, null/overfitting gates, and human-reviewed factor library
  constraints. Key risks: factor backtests compute signals from same-day close-derived
  factors and also enter at same-day adjusted close, which is not executable for the
  after-close daily workflow; the production report set contains thousands of variants,
  so final registry choices require family-level holdout / multiple-testing correction;
  single holdout relative metrics in summary.json use only 12 aligned equity points;
  factor path lacks explicit ST/suspension/limit-up filtering compared with StrategySpec
  backtester; and no MCP memory tool was available, so this record is local fallback.

next_step: >
  Before approving any strategy, rerun top candidates with next-trading-day executable
  fills, tradability filters, daily equity/benchmark alignment, frozen family-level
  validation, and multiple-comparison accounting across all generated variants.
