# 2026-07-17 美股 round269-272 低拥挤探索本地记忆

## summary

- 在 `scripts/us_live_strength_strategy_exploration.py` 中新增 current 持仓拥挤度惩罚：
  - `current_symbol_counts`
  - `holding_congestion_metrics`
- 候选打分新增 `holding_congestion_score` 惩罚和 `portfolio_breadth_bonus`，让低拥挤 5/7 强选择和 20 只分散候选优先于重复热门持仓。
- round269-270 追加 5 条新策略，新增平均实盘超基准约 +1.94%，最低约 +1.68%；current 从 411 条增至 416 条。
- round271-272 无新增，随机检验概率未过线，说明低拥挤方向一批后边际快速衰减，不宜继续原样硬扫。
- 报告重生成到 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。
- 模型组合 v6 输出到 `reports/us/live/current/us_current_model_portfolio_20260716_v6.csv`，20 只、单股约 8%、最大行业约 25.54%、拖累股数量 0，不修改 current。

## stage

us_live_strategy_monitoring_round269_272

## kpi_version

us_live_monitoring_intraday_2026_07_16_compact_no_delete_low_congestion

## verification

- `python scripts\tmp_validate_us_live_20260716.py`：416 策略、3521 持仓、237 跑赢、179 跑输保留、持仓数量只含 5/7/10/20、报告 JSON 为 416。
- `$env:PYTHONPATH='.'; pytest -q`：173 passed, 8 skipped。
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_build_current_model_portfolio.py scripts\us_generate_live_html_report.py`：通过。

## lessons

- 低拥挤惩罚能产生新增，但新增实盘超基准低于 round257-266，属于组合质量补充，不是主力收益来源。
- round271-272 无新增，说明同一低拥挤空间继续扫会浪费计算，下一步应换结构。
- 模型组合 v5/v6 能维持拖累股为 0，说明组合层已经从“压权重”进化到“避开拖累股”，后续重点应放在增加非拖累候选来源。

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:live_monitoring
- strategy:low_congestion_live_strength
- status:no_delete_underperformers

## next_step

- 从 round273 继续；不要继续原样跑低拥挤参数。
- 优先探索“20 只组合专用候选”的独立结构，或引入更强的行业/风格轮动代理，但仍需三重门槛。
- 继续保持 current 不删除跑输策略，报告保留跑输诊断页签。
