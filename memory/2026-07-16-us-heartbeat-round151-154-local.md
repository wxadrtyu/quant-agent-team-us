# 2026-07-16 美股策略探索心跳 round151-154

## 阶段结论

- 本批从 round151 继续到 round154，小规模质量稳定探索完成。
- round151 有 3 个策略通过滚动样本外、随机检验、实盘超基准为正筛选，并追加进入当前紧凑监控池。
- round152、round153、round154 有候选通过随机检验，但没有新增去重后可追加策略。
- 严格保持已进入实盘池/监控池策略不删除，本次只做增量追加。

## 当前状态

- 当前紧凑监控池策略数：151
- 当前紧凑监控池持仓数：1397
- 持仓数量分布：5 只策略 24 条，7 只策略 41 条，10 只策略 73 条，20 只策略 13 条。
- 当前池平均信息比率：2.059766
- 当前池最大回撤中位数：0.147571
- 当前池平均实盘超基准收益：0.015180
- 当前池最小实盘超基准收益：0.000317

## 报告与校验

- 已重生成：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`
- 已重生成：`reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`
- JSON 结果数与数据库 current 策略数一致：151 / 151。
- 实盘超基准收益小于等于 0 的策略数：0。
- 美股兜底中文名数量：0。
- 股票展示缺少中文括号格式数量：0。
- 非法持仓数量：0，仅包含 5、7、10、20。

## 验证命令

- `python scripts\us_generate_live_html_report.py`
- `python -m py_compile scripts\us_explore_strategy_rounds.py scripts\us_live_pool.py scripts\us_generate_live_html_report.py scripts\us_marginal_strategy_exploration.py`
- `pytest tests\test_us_live_pool.py tests\test_us_rolling_validation.py tests\test_us_null_overfit_check.py tests\test_us_research_db_ingest.py tests\test_us_universe.py tests\test_us_model_portfolio.py tests\test_us_overlap_aware_monitoring_review.py -q`

## 下一步

- 下一批从 round155 继续。
- 继续优先探索 5、7、10 持仓，保留 20 只作为稳定分散参考。
- 新策略仍需同时满足滚动样本外、随机检验、实盘超基准为正，才允许追加进入 current。
