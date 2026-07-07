# Quant Agent Team Policy

本项目是 A 股日频量化策略工厂，用于持续产生、评估、审核和监控量化策略。

## 工作规则

- 新任务开始前，先通过 `codex-mcp-memory` 检索项目长期记忆，至少使用标签 `project:quant-agent-team`、`market:cn_a`、`freq:daily`。
- 每个阶段结束后，必须通过 `codex-mcp-memory` 写入阶段结论到长期记忆。
- 若 MCP 记忆暂时不可用，必须退化为写入项目目录下的本地记忆文件，并在后续补写回 MCP。
- 未经人工审核通过，任何策略不得进入监控池。
- 允许零信号日；若没有高质量信号，必须输出原因，不得为了产出而强行推荐股票。
- 默认在收盘后开展研究和监控；自动化时间仅预留为 `15:30 Asia/Shanghai`，初版不启用自动调度。
- 第三方 skill 或 agent 只能先进入 `Phase 0` 评审，待用户确认后再纳入项目。

## 团队结构

- `manager-orchestrator`
- `quant-researcher`
- `data-engineer`
- `strategy-engineer`
- `risk-reviewer`
- `memory-archivist`
- `signal-monitor` 模块

## 研究原则

- 策略来源以研究驱动，不以固定模板库驱动。
- 初版研究维度至少覆盖：
  - 技术面：趋势、动量、均线、反转、波动率、量价
  - 基本面：盈利、成长、估值、现金流、财务质量
  - 事件驱动：热点、政策、公告、业绩预告、题材、新闻热度
  - 市场环境：指数趋势、行业轮动、风格切换、风险偏好
  - 股票类别：行业、主题、赛道、板块属性

## 记忆规则

强制记忆类型：

- `kpi-version`
- `market-research`
- `strategy-hypothesis`
- `data-decision`
- `backtest-result`
- `review-decision`
- `failed-experiment`
- `monitoring-observation`

记忆必须尽量结构化，且至少包含：

- `summary`
- `stage`
- `kpi_version`
- `tags`
- `next_step`

## MCP Memory 使用要求

- recall 阶段优先调用 `memory_search`，必要时继续读取历史项目结论。
- save 阶段优先调用 `memory_create`，把可复用知识沉淀到 MCP。
- MCP 记忆标签至少包含：
  - `project:quant-agent-team`
  - `market:cn_a`
  - `freq:daily`
- 推荐按阶段补充：
  - `stage:<stage>`
  - `strategy:<strategy_id>`
  - `status:<state>`
- 本地文件记忆仅作为 MCP 不可用时的保底层，不替代 MCP。
