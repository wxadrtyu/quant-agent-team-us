# 2026-07-26 美股高收益实盘探索本地记忆

- summary: 以 2026-06-30 信号、2026-07-24 最新完整估值日继续探索高收益且跑赢实盘基准的美股策略；先修复探索/审计脚本旧估值日硬编码，再按滚动样本外、随机检验、实盘超基准、最终持仓审计追加策略。
- stage: live-monitoring-strategy-exploration
- kpi_version: us-live-v1.1
- tags: project:quant-agent-team-us, market:us, freq:daily, stage:live-monitoring, status:current-appended
- result: round357-360 追加 3 条 5 只策略，新增平均实盘超基准约 10.11%；round361-362 decorrelated 分支追加 4 条 5 只策略，新增平均实盘超基准约 6.78%，且最终审计显示 current 篮子重叠为 0。
- current_state: current 策略 437 条，持仓 3671 条；跑赢 367 条，跑输诊断保留 70 条，入库至今持续跑赢 214 条；估值日全为 2026-07-24，持仓数仅 5/7/10/20。
- validation: `python scripts\us_validate_live_current.py --report reports\us\live\current\us_simulation_formal_monitoring_detail_0630_0724.html --json reports\us\live\current\us_simulation_formal_monitoring_0630_0724.json` 通过；`python -m unittest discover -s tests -v` 结果 191 passed, 9 skipped。
- next_step: 后续继续优先高收益但低相关方向；短期可沿 decorrelated 成功结构扩展，但必须控制 AMT/T/DDS/RS/ALSN 与 CBOE/CHRD/NDAQ/COIN/BKR 两组拥挤度，避免重复篮子。
