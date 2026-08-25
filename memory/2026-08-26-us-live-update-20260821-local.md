# 2026-08-26 美股实盘更新本地记忆

- summary: 按用户要求将美股 current 实盘尽量更新到当前可用行情；北京时间 2026-08-26 执行，最新可用于 current 全持仓估值的交易日为 2026-08-21。
- stage: live-monitoring-refresh
- kpi_version: us-live-v1.1
- tags: project:quant-agent-team-us, market:us, freq:daily, stage:live-monitoring, status:revalued
- data_decision: Yahoo/yfinance 批量接口在 2026-08 当前窗口几乎无有效行，Stooq 被浏览器校验页拦截；Nasdaq 历史接口补到 2026-08-24，但 2026-08-24 缺 current 关键持仓 LBRDK，2026-08-25 仅 35 个标的有数据，因此不用于估值。对 Nasdaq 缺口再用 Yahoo chart 单标的接口补齐，最终 2026-08-21 覆盖 current 全持仓。
- result: `us_live_monitoring_strategies_current` 全量保留 437 条，`us_live_monitoring_holdings_current` 3671 条；估值日 2026-08-21，跑赢 114 条，跑输诊断保留 323 条，入库至今持续跑赢 77 条；持仓数分布为 5:106、7:123、10:188、20:20。
- report: 生成 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0821.html`、`us_simulation_formal_monitoring_0630_0821.json`、`us_simulation_formal_monitoring_simple_0630_0821.html`。
- validation: `python scripts\us_validate_live_current.py --report reports\us\live\current\us_simulation_formal_monitoring_detail_0630_0821.html --json reports\us\live\current\us_simulation_formal_monitoring_0630_0821.json` 通过；`python -m unittest tests.test_us_live_report_integrity tests.test_us_live_pool -v` 结果 14 passed, 1 skipped。
- next_step: 下次实盘更新应从 `E:\quant-agent-team-us\data\us\raw\2026-08-24-intraday-chart` 继续补数；优先确认 LBRDK、NSA 以及 2026-08-25 之后全市场覆盖，不要用部分覆盖日期生成正式估值。
