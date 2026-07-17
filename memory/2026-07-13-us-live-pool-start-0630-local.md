# 2026-07-13 美股实盘池按 2026-06-30 起点重算

- summary: 将美股实盘池口径修正为 2026-06-30 收盘信号、2026-07-01 开盘入场、估值到最新可用交易日 2026-07-10，并重新生成中文实盘报告。
- stage: live-pool-report-regeneration
- kpi_version: us_v1
- tags: project:quant-agent-team-us, market:us_equity, freq:daily, strategy:live_pool, status:paper_live
- decision:
  - 30 个已完成滚动样本外和随机检验的策略全部纳入纸面实盘池。
  - 216 个工厂合格但未完成同级别滚动样本外和随机检验的候选写入候选复核表，状态为待滚动验证。
  - 持仓生成改为使用 2026-06-30 信号日打分，不再使用 2026-07-10 最新日打分，避免时点错误。
  - 实盘收益使用下一交易日开盘入场、最新可用交易日收盘估值，并与同一动态流动性股票池等权基准比较。
- evidence:
  - 数据库运行标识: 2026-07-13-live-all-worthy-dynamic-liquidity
  - 入库策略数: 30
  - 入库持仓行数: 350
  - 候选复核行数: 246
  - 报告: reports/us/live/2026-07-13-美股实盘池策略报告.md
  - 测试: pytest tests/test_us_live_pool.py tests/test_us_research_db_ingest.py tests/test_us_universe.py tests/test_us_model_portfolio.py -q, 9 passed
- next_step: 后续继续补历史时点成分和退市覆盖；待候选完成滚动样本外与随机检验后，再决定是否纳入纸面实盘池。
