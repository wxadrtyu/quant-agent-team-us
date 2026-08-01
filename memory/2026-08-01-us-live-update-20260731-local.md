# 2026-08-01 美股实盘更新本地记忆

- summary: 按用户要求更新美股 current 实盘报告；最新完整交易日为 2026-07-31，使用 2026-06-30 信号、2026-07-01 入场、2026-07-31 估值。
- stage: live-monitoring-refresh
- kpi_version: us-live-v1.1
- tags: project:quant-agent-team-us, market:us, freq:daily, stage:live-monitoring, status:revalued
- data_decision: 直连 Yahoo chart API 返回 HTTP 403，本次改用项目已有 yfinance 下载逻辑补齐同一 Yahoo/yfinance 价格源家族；清理 NSA 在 2026-07-27 至 2026-07-31 的 5 行无效 OHLC。
- result: `us_live_monitoring_strategies_current` 保留 437 条，`us_live_monitoring_holdings_current` 保留 3671 条；跑赢 209 条，跑输诊断保留 228 条，入库至今持续跑赢 161 条；持仓数分布为 5:106、7:123、10:188、20:20。
- report: 生成 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0731.html`、`us_simulation_formal_monitoring_0630_0731.json`、`us_simulation_formal_monitoring_simple_0630_0731.html`。
- validation: `python scripts\us_validate_live_current.py --report reports\us\live\current\us_simulation_formal_monitoring_detail_0630_0731.html --json reports\us\live\current\us_simulation_formal_monitoring_0630_0731.json` 通过；`python -m unittest tests.test_us_live_report_integrity tests.test_us_live_pool -v` 结果 14 passed, 1 skipped。
- next_step: 后续若继续更新实盘，应优先复用 `E:\quant-agent-team-us\data\us\raw\2026-07-31-intraday-chart` 作为 base，继续排除无效 OHLC 行，并关注跑输策略从 70 增至 228 的归因。
