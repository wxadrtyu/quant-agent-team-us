# 2026-07-16 美股策略探索心跳 round199-202

## 阶段结论

- 本批从 round199 运行到 round202，小规模质量稳定探索完成。
- round199、round200、round201 有策略通过滚动样本外、随机检验、实盘超基准为正，并追加进入当前紧凑监控池。
- round202 没有新增可追加策略。
- 本次只增量追加，不删除任何已进入实盘池或监控池的策略。

## 新增结果

- round199：新增 7 个策略，35 条持仓。
- round200：新增 4 个策略，20 条持仓。
- round201：新增 16 个策略，148 条持仓。
- round202：新增 0 个策略，0 条持仓。
- 本批合计新增：27 个策略，203 条持仓。

## 当前状态

- 当前紧凑监控池策略数：338
- 当前紧凑监控池持仓数：2907
- 持仓数量分布：5 只策略 63 条，7 只策略 96 条，10 只策略 166 条，20 只策略 13 条。
- 当前池平均信息比率：2.075423
- 当前池最大回撤中位数：0.139403
- 当前池平均实盘超基准收益：0.017754
- 当前池最小实盘超基准收益：0.000317
- 当前池最大实盘超基准收益：0.048372

## 报告与校验

- 已重生成：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`
- 已重生成：`reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`
- JSON 结果数与数据库 current 策略数一致：338 / 338。
- 实盘超基准收益小于等于 0 的策略数：0。
- 美股兜底中文名数量：0。
- 股票展示缺少中文括号格式数量：0。
- 非法持仓数量：0，仅包含 5、7、10、20。
- 测试：19 passed。

## 验证命令

- `python scripts\us_generate_live_html_report.py`
- `python -m py_compile scripts\us_explore_strategy_rounds.py scripts\us_live_pool.py scripts\us_generate_live_html_report.py scripts\us_marginal_strategy_exploration.py`
- `pytest tests\test_us_live_pool.py tests\test_us_rolling_validation.py tests\test_us_null_overfit_check.py tests\test_us_research_db_ingest.py tests\test_us_universe.py tests\test_us_model_portfolio.py tests\test_us_overlap_aware_monitoring_review.py -q`

## 下一步

- 下一批从 round203 继续。
- round201 的短中期收益、均线距离、资金流、高阶波动与成交稳定组合新增较多，后续可继续探索非重复变体。
- 新增策略仍需同时满足滚动样本外、随机检验、实盘超基准为正，才允许追加进入 current。
