# 2026-07-17 美股分散候选 round239-246 记录

## 改动

- 新增 `scripts/us_diversified_strategy_exploration.py`，用于生成行业更分散、低重叠、当前实盘跑赢、近期拖累股暴露较低的候选。
- `scripts/us_marginal_strategy_exploration.py` 已修正估值日到 2026-07-16，并加入当前实盘超基准、拖累股惩罚和低重叠排序。
- `scripts/us_live_pool.py` 修复空 strategies 下候选复核表和报告生成的兼容性。
- `scripts/us_explore_strategy_rounds.py` 的 promote 阶段允许 20 只持仓进入候选筛选。

## 探索结果

- round239-240：分散 live-aware 候选无新增，滚动样本外为负。
- round241-242：放宽分散约束后无新增，随机显著性不达标。
- round243：质量稳定主线无新增。
- round244：追加 4 条，新增平均超基准 +5.36%，新增最小超基准 +3.68%。
- round245-246：无新增，说明历史强不等于当前实盘可用。

## 当前状态

- current 策略数：387。
- current 持仓数：3263。
- 当前跑赢基准：208。
- 当前跑输基准但保留诊断：179。
- 入库至今持续跑赢：208。
- 估值日全部为 2026-07-16。
- 持仓数分布：5 只 76 条，7 只 119 条，10 只 179 条，20 只 13 条。
- 当前报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。

## 经验

- 分散约束本身不是 alpha 来源；约束太强会生成当前好看但历史不稳的候选。
- 允许 20 只入池后，新增仍来自 5 只强选择，说明当前有效 alpha 仍偏集中。
- 20 只持仓需要单独设计候选模板或组合层聚合，而不是直接套用同一批单策略排序。
- 实盘超基准门槛继续有效，round245 证明历史滚动强但当前实盘不过的候选不能放入 current。

## 验证

- `python scripts\tmp_validate_us_live_20260716.py` 通过。
- `python -m py_compile scripts\us_diversified_strategy_exploration.py scripts\us_marginal_strategy_exploration.py scripts\us_live_pool.py scripts\us_explore_strategy_rounds.py scripts\us_append_promoted_rounds_to_current.py scripts\us_generate_live_html_report.py` 通过。
- `$env:PYTHONPATH='.'; pytest -q` 通过：166 passed, 8 skipped。
