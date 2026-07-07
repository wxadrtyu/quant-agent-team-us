# Quant Agent Team 已拍板架构

## 1. 项目目标

`quant-agent-team` 是一个 A 股日频量化策略生产系统。

当前已拍板目标：

- 市场范围：A 股日频
- 初版只输出信号，不自动下单
- 用户手动买入
- 监控方式：手动触发
- 通知渠道：飞书
- 自动化时间仅作预留，不在初版启用 agent 自动化

当前系统定位不是自动交易系统，而是：

- 策略研究与生产
- 策略回测与审核
- 达标策略日常扫描
- 命中股票推送

## 2. 业务闭环

当前已拍板业务闭环如下：

1. 用户给 KPI
2. `quant-researcher` 提出策略假设
3. `strategy-engineer` 把研究结果固化为 `strategy_spec`
4. 系统根据 `strategy_spec` 自动补齐策略依赖数据
5. `backtest_runner` 回测策略
6. `evaluation` 判断是否满足 KPI
7. 用户审核通过
8. 已批准策略进入扫描阶段
9. `scan_runner` 扫描市场并输出命中股票
10. `monitoring` 负责推送结果或零信号说明

关键约束：

- 未经回测、评估和人工审核的策略不得进入扫描池
- 不以固定模板策略库作为主入口
- 研究员定义策略所需数据，用户不参与字段级采集决策

## 3. 研究维度

当前已拍板研究维度至少包括：

- 技术面因子
  - 趋势
  - 动量
  - 均线
  - 反转
- 基本面因子
- 事件驱动因子
- 市场环境因子
- 类别因子
  - 行业
  - 板块
  - 题材
  - 股票类别

说明：

- 行业 / 板块 / 题材 / 股票类别不是固定顶级模块
- 它们属于策略中的 `category_factors`

## 4. 数据架构

### 4.1 主数据源

当前已拍板：

- 内部正式数据源：`PostgreSQL`
- 初始种子数据：`/Users/laisicong/Downloads/stock_history`

`stock_history` 当前已确认：

- 一股一文件
- 字段包含：
  - 股票代码
  - 交易日期
  - 收盘价
  - 开盘价
  - 最高价
  - 最低价
  - 成交量
  - 成交额

### 4.2 原始行情表

表名：`raw_market_daily`

已确认字段：

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

已确认冲突规则：

- 相同行哈希：跳过
- 同一股票同一交易日但内容不同：不自动覆盖
- 写冲突日志，状态为 `manual_review_required`

### 4.3 标准化行情层

表名：`normalized_market_daily`

已确认必须包含的类别字段：

- `industry_name`：行业名称，单值
- `sector_name`：板块名称，单值
- `theme_tags`：题材标签，多值

说明：

- 标准层保存稳定事实和标准化字段
- 研究层保存可复用研究特征

### 4.4 研究特征层

表名：`research_feature_daily`

已确认方向：

- 使用持久化宽表
- 以 `(stock_code, trade_date)` 为唯一键，一行保存同一股票同一交易日的一组研究特征
- 避免长表 `feature_name -> feature_value` 结构带来的超大索引和海量 `upsert` 膨胀
- 旧 `research_feature_store` 只保留兼容空壳，不再作为主写入目标

### 4.5 基本面层

表名：`fundamental_indicator_daily`

已确认方向：

- 初版先做指标层
- 不先做完整三大财务报表仓库

### 4.6 事件层

表名：`market_event_timeline`

已确认方向：

- 初版只做市场 / 板块 / 题材级事件
- 暂不做个股级事件
- 股票映射直接依赖：
  - `industry_name`
  - `sector_name`
  - `theme_tags`

事件范围示例：

- 战争
- 地缘政治
- 政策变化
- 热点题材
- 板块轮动
- 市场风格切换

## 5. 策略产物

### 5.1 `strategy_brief`

`strategy_brief` 是研究驱动的策略说明对象，不是模板策略对象。

已确认结构方向：

- `basic_info`
- `research_conclusion`
- `factor_system`
- `trading_rules`
- `data_requirements`
- `implementation_and_review`

说明：

- 不单独设固定的“范围/股票池”顶级模块
- 行业 / 板块 / 题材 / 股票类别作为 `category_factors` 进入因子体系

### 5.2 因子对象统一结构

所有因子统一使用同一对象结构，字段包括：

- `name`
- `group`
- `purpose`
- `direction`
- `expression_hint`
- `source_hint`
- `notes`

适用分组：

- `technical`
- `fundamental`
- `event`
- `market_context`
- `category`

### 5.3 `strategy_spec`

`strategy_spec` 是实现级策略规格，是系统真正运行和回测的策略本体。

当前已拍板方向：

- 它是静态定义，不是某一时点的运行结果
- 它必须精确到实现级，而不是只有研究说明
- 它是后续数据同步、回测和扫描的共同输入

已确认应覆盖：

- 输入字段
- 派生特征
- 过滤条件
- 入场公式
- 出场公式
- 排序公式
- 持仓规则
- 风险规则
- 执行时点
- 审核关注点

## 6. 规则体系

### 6.1 trading_rules

已确认包含：

- `entry_rules`
- `exit_rules`
- `position_rules`
- `risk_constraints`

### 6.2 entry_rules / exit_rules

已确认：

- 使用半结构化规则对象
- 顶层规则字段：
  - `rule_id`
  - `logic`
  - `conditions`
  - `notes`

condition 字段：

- `field`
- `operator`
- `value`
- `value_from`
- `window`
- `notes`

约束：

- `value` 和 `value_from` 二选一

已确认操作符：

- 比较类：
  - `>`
  - `>=`
  - `<`
  - `<=`
  - `=`
  - `!=`
- 集合类：
  - `in`
  - `not_in`
  - `contains`
  - `not_contains`
- 区间类：
  - `between`
- 状态类：
  - `is_true`
  - `is_false`

### 6.3 position_rules

`position_rules` 的含义是持仓规则，它解决的是：

- 买多少
- 买几只
- 如何分配
- 持多久
- 多久重新检查
- 候选太多时按什么排序

当前已确认字段：

- `position_sizing_method`
- `max_positions`
- `min_positions`
- `holding_period_hint`
- `rebalance_frequency`
- `ranking_key`

`position_sizing_method` 已确认取值：

- `equal_weight`
- `score_weight`
- `fixed_slots`

## 7. 代码实现架构

当前已拍板代码实现架构不是自动交易系统，而是策略生产、回测验证和扫描推送系统。

核心模块如下：

- `research`
- `specs`
- `ingestion`
- `datahub`
- `features`
- `backtest_runner`
- `evaluation`
- `scan_runner`
- `monitoring`

### 7.1 各模块职责

`research`

- 负责策略研究
- 输出 `strategy_brief`

`specs`

- 负责策略规格
- 输出 `strategy_spec`

`ingestion`

- 负责外部数据采集和入库
- 负责基础采集脚本和按策略需求扩展采集

`datahub`

- 负责从数据库读取标准数据
- 负责时间和口径对齐

`features`

- 负责派生特征计算和复用
- 特征计算后写入 `research_feature_daily`

`backtest_runner`

- 负责历史区间回测
- 服务于策略验证阶段

`evaluation`

- 负责回测指标和审核判断
- 判断是否满足 KPI

`scan_runner`

- 仅对已批准策略运行
- 在最新时点扫描命中的股票

`monitoring`

- 负责输出零信号说明
- 负责生成飞书推送内容

### 7.2 执行原则

- 初版不做自动交易
- `backtest_runner` 先于 `scan_runner`
- 只有通过回测、评估和人工审核的策略才能进入扫描阶段
- “已批准策略池”第一版可用 `strategy_spec.status = approved` 轻量落地

## 8. 数据收集架构

### 8.1 总原则

已拍板的数据收集原则：

- 不使用 agent 自动化做固定日常采集
- 使用纯脚本和系统级定时
- 基础数据固定维护
- 扩展数据按策略需求补齐

### 8.2 固定维护的数据

每天固定维护的基础数据：

- 行情数据
- 交易约束数据
  - 复权
  - 停复牌
  - 涨跌停
  - ST 等可交易性强相关字段

### 8.3 按策略需求补齐的数据

不预先全量定死，而由研究员定义需求后按需补齐：

- 基本面指标
- 标签数据
- 事件数据
- 其他专用数据

### 8.4 脚本分层

已拍板脚本方向：

- `bootstrap_ingest.py`
- `base_incremental_ingest.py`
- `strategy_data_sync.py`

含义：

- `bootstrap_ingest.py`
  - 初始化导入历史数据
- `base_incremental_ingest.py`
  - 固定维护基础市场数据
- `strategy_data_sync.py`
  - 根据 `strategy_spec` 自动补齐策略依赖数据

### 8.5 数据需求定义权

已拍板：

- 用户不手工决定采哪些字段
- `quant-researcher` 定义策略需要什么数据
- `strategy-engineer` 把需求写入 `strategy_spec`
- 系统据此自动补齐

## 9. dependency_registry

`dependency_registry` 是策略需求翻译层。

它的作用是：

- 把 `strategy_spec` 中的字段或特征需求
- 翻译成来源表、底层依赖和补齐动作

第一版已拍板原则：

- 先做成代码内注册表
- 不先做数据库表
- 不预先穷举全量字段
- 只随着研究需求逐步扩展

它将供 `strategy_data_sync.py` 使用，用于：

- 需求解析
- 缺失检查
- 补齐调度

## 10. 当前实施顺序

当前建议的实施顺序：

1. 先以本文件为基线，不偏离架构
2. 先落第一版代码骨架
3. 第一批优先实现：
   - `strategy_spec` Python 模型
   - `dependency_registry`
   - `strategy_data_sync.py`
   - `base_incremental_ingest.py`
   - `backtest_runner` 最小骨架
   - `evaluation` 最小骨架

## 11. 变更规则

后续实现若要偏离本文件，必须先更新本文件，再改代码。
