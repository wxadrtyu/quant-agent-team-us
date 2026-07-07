# Base Incremental Ingest - 2026-03-19

## Context

- 用户要求继续 `quant-agent-team`，优先把 `base_incremental_ingest` 从“计划/summary 生成器”升级成真实增量更新链。
- 本 session 中 MCP 资源列表为空，没有可写的 memory MCP 或其他项目记忆入口。
- 因此本次记忆仅落本地项目目录 `memory/`。

## Confirmed implementation

- `base_incremental_ingest` 的职责已明确为：
  - 固定维护基础市场数据
  - 执行真实数据库增量更新
  - 不再只是扫描种子目录并输出 ready 状态
- 增量来源仍是本地 `stock_history` CSV。
- 真实写入目标仍是 PostgreSQL `raw_market_daily`。

## Implemented chain

- `src/quant_agent_team/ingestion.py`
  - 新增 `run_base_incremental_ingest(...)` 执行真实增量入库。
  - `write_base_incremental_outputs(...)` 现在调用真实增量执行，而不是旧的 summary-only 逻辑。
  - `BaseIncrementalIngestSummary` 新增 `execution` 字段，回写本次执行统计。
- `src/quant_agent_team/db.py`
  - 新增表 `ingest_source_file_state`，用于记录每个源 CSV 的：
    - `source_path`
    - `stock_code`
    - `file_hash`
    - `file_size_bytes`
    - `row_count`
    - `latest_trade_date`
    - `last_ingested_at`
  - 继续使用 `ingest_runs` 和 `ingest_conflict_log`。
- `src/quant_agent_team/cli.py`
  - 新增主命令 `base-incremental-ingest`
  - 保留 `base-ingest-plan` 作为兼容别名
- `scripts/base_incremental_ingest.py`
  - 描述文案改为真实执行语义

## Incremental rules now in code

- 文件级增量判定：
  - 读取每个 CSV 文件内容
  - 计算 `sha256(file_bytes)`
  - 和 `ingest_source_file_state.file_hash` 比较
  - 未变化文件不进入 staging
- 行级写入规则：
  - 新 `(stock_code, trade_date)`：插入 `raw_market_daily`
  - 同 `raw_line_hash`：跳过
  - 同 `(stock_code, trade_date)` 但内容不同：
    - 不覆盖旧值
    - 写 `ingest_conflict_log`
    - `resolution = manual_review_required`
- 每次运行都写 `ingest_runs`
  - `run_type = base_incremental`
  - 状态可能为：
    - `success`
    - `no_changes`
    - `completed_with_conflicts`

## Validation completed

- 单测通过：
  - `python3 -m unittest /Users/laisicong/quant-agent-team/tests/test_workflow.py`
- 编译检查通过：
  - `python3 -m compileall /Users/laisicong/quant-agent-team/src`
- 端到端 CLI 验证通过：
  - `base-incremental-ingest` 首跑成功
  - 独立临时数据库中确认 `inserted_rows = 2`
  - `files_changed = 1`
- 集成测试已覆盖四种场景：
  - 首次导入
  - 重复运行无变化
  - 追加新交易日
  - 同交易日内容冲突

## Small correction made during implementation

- 修正了 `latest_trade_date` 的计算方式。
- 现在取文件内最大交易日，而不是“最后读到的一行”，避免源 CSV 顺序变化导致状态记录错误。

## Git

- 本次改动已提交。
- 分支：`codex/architecture-baseline`
- commit：`a46e354`
- message：`Implement base incremental ingest chain`

## Next likely step

- 在此基础上继续补：
  - `trading_constraints` 的真实增量链
  - `normalized_market_daily` 的标准化链
  - 从 base ingest 到下游标准层/特征层的明确衔接
