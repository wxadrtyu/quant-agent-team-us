# 2026-07-25 美股实盘报告 2026-07-24 审计

- summary: 当前 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0724.html` 的核心估值数据自洽：430 条策略、3636 条持仓、估值日均为 2026-07-24，持仓数只包含 5/7/10/20，跑输 70 条被保留，JSON 与数据库 current 表数量一致，当前持仓无缺价。
- stage: monitoring-observation
- kpi_version: v1.1
- tags: project:quant-agent-team-us, market:us, freq:daily, stage:live-report-audit, status:bug-found
- findings:
  - 真实 bug: `scripts/us_generate_live_html_report.py` 默认 `--raw-dir` 仍指向 `E:\quant-agent-team-us\data\us\raw\2026-07-17-intraday-chart`。不带参数生成 2026-07-24 报告时，430 条策略全部持仓缺 2026-07-24 价格，持仓贡献和为 0，但策略收益仍来自数据库，导致策略层收益与持仓明细不一致。
  - 真实 bug: 现有 `scripts/us_validate_live_current.py` 未检查持仓价格缺失，也未检查策略实盘收益是否等于持仓贡献和，因此无法拦截上述错误。
  - 展示问题: `策略编号` 只有 23 个唯一值，430 条中大量重复，例如“策略一”重复 66 次。`monitor_key` 唯一，因此计算不受影响，但用户阅读报告时容易误判不同策略为同一策略。
  - 口径风险: 旧 `us_live_pool_strategies/us_live_pool_holdings` 表只有 8/65 行，当前报告实际使用 `us_live_monitoring_strategies_current/us_live_monitoring_holdings_current`。需要统一文档和脚本命名，避免后续读错旧实盘池。
- next_step: 优先修复报告生成脚本默认行情目录或自动选择 current 表估值日对应的最新 raw-dir；增强验证脚本，强制检查缺价、收益贡献一致性、策略展示编号唯一性或改名；随后再继续低相关策略探索。
