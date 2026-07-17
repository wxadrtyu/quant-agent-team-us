# 2026-07-16 美股策略探索心跳 round183-186

## 阶段结论

- 本批从 round183 运行到 round186，小规模质量稳定探索完成。
- round183 与 round186 有策略通过滚动样本外、随机检验、实盘超基准为正，并追加进入当前紧凑监控池。
- round184 与 round185 随机检验通过数量为 0，没有新增策略。
- 本次只增量追加，不删除任何已进入实盘池或监控池的策略。

## 新增结果

- round183：新增 4 个策略，20 条持仓。
- round184：新增 0 个策略，0 条持仓。
- round185：新增 0 个策略，0 条持仓。
- round186：新增 8 个策略，40 条持仓。
- 本批合计新增：12 个策略，60 条持仓。

## 当前状态

- 当前紧凑监控池策略数：288
- 当前紧凑监控池持仓数：2526
- 持仓数量分布：5 只策略 50 条，7 只策略 78 条，10 只策略 147 条，20 只策略 13 条。
- 当前池平均信息比率：2.069860
- 当前池最大回撤中位数：0.141209
- 当前池平均实盘超基准收益：0.017777
- 当前池最小实盘超基准收益：0.000317
- 当前池最大实盘超基准收益：0.048372

## 报告与校验

- 已重生成：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`
- 已重生成：`reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`
- JSON 结果数与数据库 current 策略数一致：288 / 288。
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

- 下一批从 round187 继续。
- 继续优先探索 5、7、10 持仓组合，重点关注短中期收益、资金流、波动稳定和成交稳定组合。
- 新增策略仍需同时满足滚动样本外、随机检验、实盘超基准为正，才允许追加进入 current。
