# 2026-07-10 US Large/Mid Factor Data Design

summary: US v1.0 factor-data scope was approved and documented for large/mid-cap tradable universes instead of reusing A-share factor conclusions.
stage: us-factor-data-design
kpi_version: kpi-unset
tags:
  - project:quant-agent-team
  - market:cn_a
  - freq:daily
  - stage:us-factor-data-design
  - status:local-memory-fallback
  - repo:quant-agent-team-us
  - market:us_equity
next_step: User reviews `docs/superpowers/specs/2026-07-10-us-large-mid-factor-data-design.md`; after approval, create an implementation plan for data sources, schema, download scripts, validation, and US factor-panel construction.

Details:
- The approved initial universes are `sp500`, `nasdaq100`, `russell1000`, and their de-duplicated union `us_large_mid`.
- The A-share pipeline shape is reusable, but A-share factor efficacy and A-share-specific fields are not reused for US equities.
- First raw tables are `us_stock_meta`, `us_index_membership`, and `us_market_daily`.
- First candidate factor families are momentum, short-term reversal/pullback, trend, volatility/tail-risk, volume-price structure, liquidity/size controls, and sector/industry relative strength.
- Fundamentals, options, news/sentiment, analyst estimates, institutional ownership, and A-share-only event/flow fields are deferred from v1.0.
- Design doc committed in commit `a202511` with message `docs: define US large-mid factor data design`.
- MCP memory tools were not available in this session, so this record is local fallback per project policy.
