# 2026-07-13 美股 10 以下持仓探索第 13-22 轮本地记忆

summary: 第 13-22 轮共完成 10 轮美股日频策略探索，全部候选只使用 5 或 7 持仓。第 14 轮和第 22 轮在历史滚动、随机检验、实盘超基准过滤后各保留 8 个策略；第 15、17、21 轮存在历史或随机检验通过项，但 2026-06-30 至 2026-07-10 实盘超基准过滤后为 0；第 13、16、18、19、20 轮未通过随机检验门槛。

stage: sub10-strategy-exploration
kpi_version: us_daily_live_v1_2026-07-13
tags:
- project:quant-agent-team-us
- market:us
- freq:daily
- stage:sub10-exploration
- status:live-outperformance-filtered

validated_outputs:
- 当前监控表: `us_live_monitoring_strategies_current`，119 个策略。
- 当前持仓表: `us_live_monitoring_holdings_current`，1592 条持仓。
- 当前持仓分布: 5 持仓 5 个，7 持仓 11 个，10 持仓 57 个，20 持仓 46 个。
- 当前报告: `reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`
- 当前明细页: `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`
- 当前简版页: `reports/us/live/current/us_simulation_formal_monitoring_simple_0630_0710.html`

hard_filters:
- 当前监控和报告只允许 `实盘超基准收益 > 0`。
- 当前监控和报告只允许持仓数量为 5、7、10、20。
- 本轮新增探索主攻 5 和 7 持仓。

verification:
- `pytest tests\test_us_live_pool.py tests\test_us_rolling_validation.py tests\test_us_null_overfit_check.py tests\test_us_research_db_ingest.py tests\test_us_universe.py tests\test_us_model_portfolio.py -q` 通过，17 passed。
- `python -m py_compile scripts\us_live_pool.py scripts\us_rolling_validation.py scripts\us_null_overfit_check.py scripts\us_generate_live_html_report.py` 通过。
- 报告校验: `non_outperform=0`，`bad_bracket=0`，`bad_fallback=0`，`bad_tokens=[]`。
- 当前池最小实盘超基准收益为 0.0003172228817951428，最大为 0.035336245584348。

next_step: 后续继续主攻 10 以下持仓时，优先扩展第 22 轮有效结构：短期回调或微观趋势、相对六十日均线位置、中期收益、收益尾部分布、成交稳定度组合；第 21 轮长期动量结构历史强但实盘过滤失败，应先调整实盘窗口稳健性再复测。
