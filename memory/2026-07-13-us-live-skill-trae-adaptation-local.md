# 2026-07-13 美股实盘报告技能吸收 Trae 流程纪律

- summary: 参考 `G:\quant-agent-team\.trae\skills\live-trading-update\SKILL.md`，将可复用的实盘更新纪律合并到 `.agents/skills/us-live-strategy-report/SKILL.md`。
- stage: live-report-skill-hardening
- kpi_version: us_v1
- tags: project:quant-agent-team-us, market:us_equity, freq:daily, skill:us-live-strategy-report, source:trae-live-trading-update
- decision:
  - 采纳数据库作为实盘池唯一可信来源，不使用代码固定列表或临时字典代表实盘池。
  - 采纳最新可用交易日估值规则，避免用过期估值日刷新实盘表现。
  - 采纳生成物验证规则，检查数据库行数、持仓行数、报告文件和无效占位符。
  - 未采纳 A 股项目的进攻型和防守型双池结构，因为美股项目当前尚未建立该分层数据库设计。
- next_step: 后续生成或刷新美股实盘报告时，按该技能先检查数据库来源、估值日、入库状态和中文报告展示规范。
