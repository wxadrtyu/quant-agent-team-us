# 2026-07-17 US round312-315 qmvstableflow and smoothquality local memory

- stage: strategy-exploration
- kpi_version: us-live-compact-current-20260716
- tags: project:quant-agent-team-us, market:us, freq:daily, strategy:qmvstableflow, strategy:smoothquality, status:failed-experiment
- summary: Tested two follow-up branches after qmvstrongnodrag and sectorleader failed promotion. qmvstableflow kept the ret_120d + px_to_ma20 + flow core while excluding short reversal factors entirely. smoothquality shifted to 60/120-day strength plus flow, volatility, tail-risk, and stability guards. Neither branch passed rolling OOS and random/null thresholds.
- evidence:
  - round312 qmvstableflow best rolling IR 1.3464475986193865, best random pvalue 0.08273894436519258, promoted 0.
  - round313 had no candidate chunk because qmvstableflow was too narrow after historical de-duplication.
  - round314 smoothquality best rolling IR 0.9537085284740052, best random pvalue 0.12696148359486448, promoted 0.
  - round315 smoothquality best rolling IR 1.201804901333438, best random pvalue 0.0898716119828816, promoted 0.
  - Current report was regenerated for 2026-07-16 and validation kept 425 strategies, 246 outperformers, 179 underperformers, and holding counts limited to 5/7/10/20.
- decision: Do not promote round312-315. Removing short reversal noise made qmvstableflow too narrow and less robust, while smoothquality did not produce enough rolling OOS IR.
- next_step: Stop minor qmv/price-volume branch variations for now. The strongest near-miss remains round309, but further progress likely needs a genuinely new signal dimension, such as fundamentals/earnings quality if available, or a stricter portfolio construction layer rather than more single-strategy factor reshuffling.
