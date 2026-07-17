# 2026-07-18 US live current revalue to 2026-07-17 local memory

- stage: live-monitoring-update
- kpi_version: us-live-compact-current-20260717
- tags: project:quant-agent-team-us, market:us, freq:daily, status:monitoring-observation, valuation-date:2026-07-17
- summary: Updated the US raw daily dataset to a new `2026-07-17-intraday-chart` snapshot and revalued the full current monitoring pool to 2026-07-17 without deleting underperforming strategies.
- evidence:
  - Yahoo chart update requested 1011 symbols, fetched 1011 symbols, had 0 errors, and produced max trade date 2026-07-17.
  - Current pool after revaluation: 425 strategies and 3611 holdings retained.
  - 2026-07-17 live status: 210 strategies outperforming benchmark, 215 underperforming kept for diagnostics, 210 persistent outperformers.
  - Holding distribution stayed within allowed counts: 5=94, 7=123, 10=188, 20=20.
  - Generated `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0717.html` and matching JSON; validation passed with no fallback stock names or invalid holding counts.
- decision: Treat 2026-07-17 as the latest valuation date for subsequent reports and exploration. The old 2026-07-16 defaults should not be used for new exploration.
- next_step: Continue strategy exploration against the 2026-07-17 raw directory. Because price/volume factor reshuffling has shown diminishing returns through round315, prioritize new data dimensions or a portfolio-level construction layer over more minor single-factor-family tweaks.
