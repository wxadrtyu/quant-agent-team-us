# 2026-07-17 美股 round247-250 与模型组合候选记录

## 单策略探索

- round247：无新增。
- round248：追加 8 条，新增平均超基准 +2.50%，新增最小超基准 +0.35%。
- round249-250：无新增。

## 当前状态

- current 策略数：395。
- current 持仓数：3303。
- 当前跑赢基准：216。
- 当前跑输基准但保留诊断：179。
- 入库至今持续跑赢：216。
- 持仓分布：5 只 84 条，7 只 119 条，10 只 179 条，20 只 13 条。
- 报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。

## 20 只模型组合候选

- 新增脚本：`scripts/us_build_current_model_portfolio.py`。
- 输出：`reports/us/live/current/us_current_model_portfolio_20260716.csv`。
- 该组合从持续跑赢的 5/7 策略聚合，目标 20 只，单票上限 8%。
- 当前版本只是候选组合，未替代 current，也未进入正式策略池。

## 问题

- 模型组合头部仍集中在 CAR、HON、JEF、ON 等拥挤或曾经拖累的股票。
- 说明“从强策略持仓简单聚合”会继承单策略的拥挤暴露。
- 不能把这版模型组合直接当作实盘组合。

## 下一步

- 模型组合聚合层也需要加入：
  - 拖累股权重上限。
  - 行业权重上限。
  - 贡献策略数上限或去拥挤惩罚。
  - 个股当前收益/贡献的负面过滤。
- 单策略继续小批量探索，但当前更重要的是把 20 只组合做成真正风险分散的候选。

## 验证

- `$env:PYTHONPATH='.'; pytest -q` 通过：166 passed, 8 skipped。
- `python -m py_compile scripts\us_build_current_model_portfolio.py scripts\us_model_portfolio.py scripts\us_explore_strategy_rounds.py scripts\us_generate_live_html_report.py scripts\us_append_promoted_rounds_to_current.py` 通过。
