# 2026-07-17 美股隔夜探索阶段状态

## 本轮新增

- 从 round203 到 round233 共探索 31 个编号段，其中通过严格门槛并追加到 current 的新增策略合计 45 条。
- 新增来源：
  - round203-206：20 条。
  - round207-210：6 条。
  - round211-214：11 条。
  - round215-218：6 条。
  - round223：1 条。
  - round227：1 条。
- round219-222、round224-226、round228-233 未新增，主要原因是最终 2026-07-16 实盘超基准未通过。

## 当前报告状态

- current 策略数：383。
- current 持仓数：3243。
- 当前跑赢基准：204。
- 当前跑输基准但保留诊断：179。
- 入库至今持续跑赢：204。
- 估值日全部为 2026-07-16。
- 持仓数分布：5 只 72 条，7 只 119 条，10 只 179 条，20 只 13 条。
- 当前报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。

## 跑输原因总结

- 回调趋势型是主要拖累，跑赢率低、平均超基准显著落后。
- 单纯历史滚动样本外强不够，多个 round 的候选随机检验也通过，但当天实盘超基准未过。
- 反复拖累股票包括 ARM、ON、DELL、HON、SNX、QCOM、VIRT、LBRDK、ALB、ORCL。
- 二十日均线相对六十日均线、五日与二十日成交量比、二十日收益峰度等因子组合近期表现偏弱。

## 后续建议

- 不继续盲目扫同一候选空间。
- 下一步从 round234 之后开始，但先改候选生成或排序：
  - 增加近期拖累股暴露惩罚。
  - 提高当前实盘相对强度在候选排序中的权重。
  - 优先 7 只和强选择 5 只持仓。
  - 保留 20 只持仓作为分散对照，但不扩大 10 只拥挤组合。
  - 跑输策略不删除，继续进入诊断页签观察。

## 验证

- `python scripts\tmp_validate_us_live_20260716.py` 通过。
- `python -m py_compile scripts\us_explore_strategy_rounds.py scripts\us_marginal_strategy_exploration.py scripts\us_append_promoted_rounds_to_current.py scripts\us_generate_live_html_report.py scripts\tmp_analyze_us_live_underperformance_20260716.py scripts\tmp_validate_us_live_20260716.py` 通过。
- `$env:PYTHONPATH='.'; pytest -q` 通过：166 passed, 8 skipped。
