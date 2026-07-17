# 2026-07-18 US model portfolio 20260717 v1 local memory

- stage: portfolio-construction
- kpi_version: us-live-compact-current-20260717
- tags: project:quant-agent-team-us, market:us, freq:daily, status:model-portfolio-candidate, valuation-date:2026-07-17
- summary: Built a 20-stock candidate model portfolio from current persistent outperforming 5/7-stock strategies after the current pool was revalued to 2026-07-17. This does not replace or modify the current single-strategy monitoring pool.
- evidence:
  - Output files: `reports/us/live/current/us_current_model_portfolio_20260717_v1.csv` and `.json`.
  - Symbols: 20.
  - Total weight: 100%.
  - Largest single-stock weight: 8%.
  - Largest sector weight: about 17.88%.
  - Drag symbols: 0 after excluding the diagnostic drag list.
  - Source pool: persistent outperforming current strategies, limited to 5/7-stock sleeves.
- decision: Keep this as a candidate portfolio-level aggregation only. Do not write it into current and do not treat it as a replacement for the monitored strategy pool.
- next_step: If portfolio-layer work continues, improve field encoding in `us_build_current_model_portfolio.py` and add a Chinese-facing model portfolio report that summarizes holdings by stock name, sector, source strategy count, and cluster concentration.
