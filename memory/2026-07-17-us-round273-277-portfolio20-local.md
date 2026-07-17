# 2026-07-17 美股 round273-277 二十只组合专用候选本地记忆

## summary

- 在 `scripts/us_live_strength_strategy_exploration.py` 中新增 `is_portfolio20_specialized_set` 和 `passes_factor_structure_screen`。
- 二十只候选不再强制套用 5/7 强选择的两个强度因子要求，而是允许“中期强度 + 成交确认 + 风险平衡 + 流动性稳定”的组合结构独立进入候选池。
- round273 首次尝试未新增，候选池仅 35 行且随机检验未过。
- 放宽候选结构来源后，round274 追加 1 条二十只策略，实盘超基准约 +1.72%。
- round276-277 追加 3 条新策略，平均实盘超基准约 +1.81%；current 从 416 条增至 420 条。
- 报告重生成到 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。
- 模型组合 v7 输出到 `reports/us/live/current/us_current_model_portfolio_20260716_v7.csv`，20 只、单股约 8%、最大行业约 25.54%、拖累股数量 0，不修改 current。

## stage

us_live_strategy_monitoring_round273_277

## kpi_version

us_live_monitoring_intraday_2026_07_16_compact_no_delete_portfolio20

## verification

- `python scripts\tmp_validate_us_live_20260716.py`：420 策略、3571 持仓、241 跑赢、179 跑输保留、持仓数量只含 5/7/10/20、报告 JSON 为 420。
- `$env:PYTHONPATH='.'; pytest -q`：175 passed, 8 skipped。
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_build_current_model_portfolio.py scripts\us_generate_live_html_report.py`：通过。

## lessons

- 二十只组合专用结构可以新增策略，但收益弹性低于 5/7 强选择，适合作为组合稳定性和分散来源，不是主力收益来源。
- 候选池仍偏窄，说明基于现有日频价量因子的二十只组合空间有限；下一批不应只扩大 candidate-limit。
- 模型组合 v7 保持拖累股为 0，组合层约束稳定。

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:live_monitoring
- strategy:portfolio20_specialized
- status:no_delete_underperformers

## next_step

- 从 round278 继续；不要只扩大二十只候选池。
- 优先做行业/风格轮动代理，或把 5/7 强选择和二十只稳定组合分成两个候选分支分别验证。
- 继续保持 current 不删除跑输策略，报告保留跑输诊断页签。
