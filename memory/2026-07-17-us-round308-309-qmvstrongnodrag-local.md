# 2026-07-17 US round308-309 qmvstrongnodrag local memory

- stage: strategy-exploration
- kpi_version: us-live-compact-current-20260716
- tags: project:quant-agent-team-us, market:us, freq:daily, strategy:qmvstrongnodrag, status:failed-experiment
- summary: Added a qmvstrongnodrag 5/7-stock branch that keeps the historically strong ret_120d + px_to_ma20 + flow-confirmed quality momentum core while rejecting old 5-day pullback cores and applying a stricter loser-exposure cap before selection. Round308 and round309 did not append to current.
- evidence:
  - round308 best rolling IR 1.427789828763856, best random pvalue 0.0912981455064194, promoted 0.
  - round309 best rolling IR 1.4387840253232054, best random pvalue 0.042796005706134094, promoted 0.
  - best round309 candidate had OOS excess 0.7340750134196148 and random pvalue 0.042796005706134094, but deflated IR z was only 1.6558888911535292, below the promotion threshold.
  - Current report was regenerated for 2026-07-16 and validation kept 425 strategies, 246 outperformers, 179 underperformers, and holding counts limited to 5/7/10/20.
- decision: Do not promote round308-309. The qmvstrongnodrag direction is closer than breadthquality20 on random pvalue, but still not robust enough under deflated IR. Keep it as a near-miss hypothesis, not current.
- next_step: If continuing, either tighten qmvstrongnodrag around the round309 near-miss with a higher deflated-IR prior and lower MDD penalty, or switch to a new data dimension such as sector-relative strength or fundamental quality proxy. Avoid adding more breadthquality20 ranking tweaks.
