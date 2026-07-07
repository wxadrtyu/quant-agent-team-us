# quant-agent-team

## Data Ingest

基础行情增量：

```bash
PYTHONPATH=src python3 -m quant_agent_team.cli \
  --root . \
  base-incremental-ingest \
  --source-dir ~/Downloads/stock_history
```

默认只读取 `stock_history` 行情源，不会自动读取项目内交易约束样例目录。
真实日常流程约定为：上游继续向原股票文件追加新交易日，本项目再对变更过的股票文件做增量入库。

带交易约束增量：

```bash
PYTHONPATH=src python3 -m quant_agent_team.cli \
  --root . \
  base-incremental-ingest \
  --source-dir ~/Downloads/stock_history \
  --constraints-dir ./inputs/trading_constraints
```

交易约束 CSV 样例和字段约定见：

- `inputs/trading_constraints/README.md`

每日更新入口：

```bash
PYTHONPATH=src python3 -m quant_agent_team.cli \
  --root . \
  daily-update \
  --source-dir ~/Downloads/stock_history
```

也可以直接跑脚本：

```bash
./scripts/daily_update.py --source-dir ~/Downloads/stock_history
```

这个入口的语义是：读取被追加更新过的 `stock_history/*.csv`，识别发生变化的股票文件，再执行真实增量入库。

免费多源抓取：

```bash
python3.11 ./scripts/fetch_market_daily.py \
  --source-dir ~/Downloads/stock_history \
  --stock-code 000001 \
  --start-date 2026-03-01 \
  --end-date 2026-03-10
```

抓取后直接入库的一体化日更脚本：

```bash
python3.11 ./scripts/run_daily_pipeline.py \
  --source-dir ~/Downloads/stock_history \
  --start-date 2026-03-01 \
  --end-date 2026-03-10
```

若不显式传 `--start-date`，脚本会先读取数据库里 `raw_market_daily` 的最大 `trade_date`，再从下一天开始抓取新增数据。
默认还会跳过 `reports/data_quality/lagging_backfill_status.json` 里已经确认“免费源无数据”的股票；只有显式传 `--stock-code` 或 `--include-free-source-unavailable` 时才会重试这些股票。
脚本生成的 `daily_update_latest.json` 现在还会在 `execution.fetch` 里写入本次尝试抓取数、跳过数和抓取失败数。
数据库看板也会直接展示最近一次日更的 fetch 摘要，包括尝试数、失败数、跳过的 free-source-unavailable 数量。

质量报表 `reports/data_quality/latest.json` 现在还会输出结构化 `anomaly_rules`，把当前库状态归类成 `pass / info / warn / fail`，用于固定化处理：
- `market_row_balance`
- `feature_refresh_gap`
- `recent_lagging_symbols`
- `known_free_source_unavailable`
- `conflict_backlog`
- `lagging_bucket_visibility`

给系统级定时直接调用的包装脚本：

```bash
./scripts/run_daily_job.sh
```

它会：
- 调 `run_daily_pipeline.py`
- 自动写日志到 `reports/logs/`
- 在日志里打印当前已确认免费源无数据的 skip 桶数量
- 用 `.daily_job.lock` 防止重复并发执行

如果以后拿到真实交易约束源，再显式传入：

```bash
CONSTRAINTS_DIR=/path/to/real/trading_constraints ./scripts/run_daily_job.sh
```

安装到 macOS `launchd`：

```bash
./scripts/install_launchd_daily_job.sh
```

默认会在本机时区每天 `15:30` 触发。

数据库可视化看板：

```bash
./scripts/open_db_dashboard.sh
```

默认地址：

```text
http://127.0.0.1:8501
```

每日更新会同时写：

- `reports/ingestion/base_incremental_summary.json`
- `reports/ingestion/daily_update_latest.json`
- `reports/ingestion/daily_updates/daily_update_<timestamp>.json`

用于 A 股日频量化策略生产的项目骨架。

当前版本只提供项目级规则、角色分工、记忆规范、第三方评审框架，以及一个最小 CLI 外壳。具体量化代码实现架构需在进一步对齐后再写入。

## 当前范围

- KPI 版本化
- 研究驱动的策略说明流程
- 数据需求说明
- 回测/审核/监控的文档与接口占位
- 长期记忆标签和归档规范
- 第三方专业 agent/skill 的 Phase 0 评审清单

## 验证方式

```bash
cd /Users/laisicong/quant-agent-team
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/run_cli.py --root /Users/laisicong/quant-agent-team new-kpi --win-rate 0.9 --annual-return 0.2 --max-drawdown 0.15
```

## 暂不实现

- 真实 A 股数据接入
- 真实 Backtrader 回测执行
- 飞书接口接入
- 自动调度
- 自动下单

## 目录

- `docs/`：架构、角色、流程文档
- `configs/`：项目默认配置
- `src/quant_agent_team/`：最小 Python 外壳
- `inputs/`：KPI 版本与任务输入
- `reports/`：审核与评审输出
- `third_party_review/`：第三方能力评审结果
