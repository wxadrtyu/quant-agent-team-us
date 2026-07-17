# 2026-07-17 美股 live-aware 候选生成 round234-238 记录

## 改动

- 修正 `scripts/us_marginal_strategy_exploration.py`：
  - live frame 估值日从硬编码 2026-07-10 改为 2026-07-16。
  - 候选生成加入当前实盘超基准收益过滤，要求 `live_excess > 0`。
  - 候选排序加入当前实盘超基准权重。
  - 增加近期拖累股惩罚：ARM、ON、DELL、HON、SNX、QCOM、VIRT、LBRDK、ALB、ORCL 等。
  - 保留低重叠约束，避免和 current 持仓篮子高度相似。
- 修正 `scripts/us_live_pool.py`：
  - `build_candidate_review_table` 支持空 strategies。
  - `write_report` 支持无新增批次输出空策略表，不再因空表缺列中断。

## 探索结果

- round234：live-aware 低重叠候选无新增，候选未通过随机显著性和去偏门槛。
- round235-236：live-aware 低重叠候选无新增，滚动与随机指标弱于 round234。
- round237-238：回到质量稳定小批量主线，无新增。

## 当前状态

- current 策略数：383。
- current 持仓数：3243。
- 当前跑赢基准：204。
- 当前跑输基准但保留诊断：179。
- 入库至今持续跑赢：204。
- 持仓数分布：5 只 72 条，7 只 119 条，10 只 179 条，20 只 13 条。
- 报告已重生成：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。

## 经验

- 将当前实盘相对强度加入候选生成后，可以避免明显不合格候选进入后续流程，但可新增数量暂时下降。
- 低重叠 + 拖累股惩罚的候选空间需要进一步扩展，不宜继续只跑 round234-238 同类扫描。
- 下一步建议：
  - 重新设计候选模板，增加非回调趋势、非拥挤动量的组合。
  - 加入行业/风格分散约束，减少单一半导体与硬件链暴露。
  - 尝试 20 只分散组合和 7 只强选择组合并行生成。
  - 保持旧策略不删除，继续诊断页签观察。

## 验证

- `python scripts\us_generate_live_html_report.py --raw-dir E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart` 通过。
- `python scripts\tmp_validate_us_live_20260716.py` 通过。
- `$env:PYTHONPATH='.'; pytest -q tests\test_us_live_pool.py tests\test_us_model_portfolio.py tests\test_us_overlap_aware_monitoring_review.py` 通过：11 passed。
- `python -m py_compile scripts\us_live_pool.py scripts\us_marginal_strategy_exploration.py scripts\us_explore_strategy_rounds.py scripts\us_append_promoted_rounds_to_current.py scripts\us_generate_live_html_report.py` 通过。
