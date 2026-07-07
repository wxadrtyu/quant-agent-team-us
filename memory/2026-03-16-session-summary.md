# Session Summary - 2026-03-16

## Context

用户希望构建一个长期运行的 A 股日频量化策略生产项目 `quant-agent-team`，并要求：

- 采用研究驱动流程，而不是模板策略工厂
- 项目具备长效记忆
- 初版先完成项目骨架
- 具体量化代码实现架构需要先讨论再写

## Confirmed Decisions

### Project scope

- 市场：A 股日频
- 初版不自动下单
- 初版监控：手动触发
- 通知渠道优先：飞书
- 自动化时间仅预留：`15:30 Asia/Shanghai`

### Research workflow

用户明确要求工作流改为：

1. `quant-researcher` 先提出策略假设
2. `quant-researcher` 与 `strategy-engineer` 一起讨论所需数据
3. `data-engineer` 负责收集与准备数据
4. 数据准备完成后，才进入工程化与回测

说明：

- 不再以固定模板策略库作为主入口
- 但技术面仍然非常重要，不能极端地只做基本面或事件驱动

### Research dimensions

研究维度已对齐为可组合的多维框架，至少包括：

- 技术面：趋势、动量、均线、反转等
- 基本面因子
- 事件驱动
- 市场环境
- 股票类别/行业/板块/题材

用户特别补充：

- 行业、板块、题材非常重要
- 股票类别也需要纳入考虑
- 例如可以按科技股、白酒、军工等方向筛选

### Event scope

事件驱动初版收敛为：

- 只做市场/板块/题材级事件
- 暂不做个股级事件

事件示例：

- 战争
- 地缘政治
- 政策变化
- 题材升温
- 板块轮动
- 市场风格切换

事件到股票的映射初版直接依赖：

- `industry_name`
- `sector_name`
- `theme_tags`

### Database direction

用户明确接受：

- 使用数据库作为项目内部正式数据源
- 先把 `Downloads/stock_history` 导入数据库
- 后续所有更新都以数据库为主，不继续直接从散落文件工作

#### `stock_history` observation

已确认本地存在：

- 路径：`/Users/laisicong/Downloads/stock_history`
- 规模：约 5309 个 CSV，约 632.71 MB
- 结构：一股一文件
- 当前实际字段：
  - `股票代码`
  - `交易日期`
  - `收盘价`
  - `开盘价`
  - `最高价`
  - `最低价`
  - `成交量`
  - `成交额`

判断：

- 适合作为 `market_data.raw` 的原始输入
- 不足以单独支撑研究层/回测层

### `raw_market_daily`

已对齐的字段：

- `id`
- `stock_code`
- `trade_date`
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `volume`
- `turnover`
- `raw_line_hash`
- `raw_payload`
- `created_at`
- `updated_at`

冲突规则最终定为：

- 同 `raw_line_hash`：跳过
- 新 `(stock_code, trade_date)`：插入
- 同 `(stock_code, trade_date)` 但内容不同：
  - 不自动覆盖
  - 写冲突日志
  - `resolution = manual_review_required`
  - 主表保留旧值，待人工处理

### `ingest_conflict_log`

方向已确定：

- 保留旧值和新值
- 初版冲突处理模式以 `manual_review_required` 为主

### `normalized_market_daily`

用户确认标准层里直接放：

- `industry_name`
- `sector_name`
- `theme_tags`

其中类型约定：

- `industry_name`：单值
- `sector_name`：单值
- `theme_tags`：多值

### `research_feature_store`

已确定：

- 研究层数据尽量保留，不轻易丢弃
- 采用持久化特征存储
- 设计方向为长表

目标：

- 避免下一个策略复用同类特征时重新采集和重算

### `fundamental_indicator_daily`

方向已确认：

- 初版先做指标层，不先做完整三大财务报表仓库

### `strategy_brief`

已确认其是系统核心业务对象之一，用来连接：

- researcher
- data-engineer
- strategy-engineer
- risk-reviewer
- memory-archivist
- manager-orchestrator

尚未最终定稿，但已确定：

- 不是模板策略对象
- 而是研究驱动的策略说明对象

### Team / project skeleton

项目基础骨架已创建在：

- `/Users/laisicong/quant-agent-team`

已包含：

- 项目级 `AGENTS.md`
- 架构与流程文档
- 角色说明
- 第三方评审说明
- 最小 Python CLI 外壳
- KPI / strategy brief / review stub 生成能力

## Next discussion topics

下次继续时，优先从这里接着谈：

1. `strategy_brief` 最终结构
2. `normalized_market_daily` 最终字段、主键和索引
3. `market_event_timeline` 最小结构
4. `fundamental_indicator_daily` 最终结构
5. 数据库选型与 schema 具体实现
6. 量化代码实现架构（需先和用户讨论，再写代码）

## Important constraint from user

用户明确要求：

- 今天先把思路记住
- 具体量化代码实现架构，后续必须先商量，再写

