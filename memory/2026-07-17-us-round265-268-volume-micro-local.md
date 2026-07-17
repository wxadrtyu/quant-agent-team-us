# 2026-07-17 美股 round265-268 成交确认与微结构保护本地记忆

## summary

- 在 `scripts/us_live_strength_strategy_exploration.py` 中新增两类候选结构：
  - `is_volume_confirmed_low_vol_extension_set`：成交确认 + 低波动/稳定 + 延续强度。
  - `is_micro_reversal_protected_momentum_set`：微结构反转失败保护 + 中期动量 + 风险保护。
- 新增测试覆盖这两类结构，避免候选生成回到旧回调核心。
- round265-266 追加 3 条新策略，新增平均实盘超基准约 +3.11%，最低约 +2.74%；current 从 408 条增至 411 条。
- round267-268 无新增，主要卡在随机检验概率，说明该方向有效但边际空间不宜连续硬扫。
- 报告重生成到 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。
- 模型组合 v5 输出到 `reports/us/live/current/us_current_model_portfolio_20260716_v5.csv`，20 只、单股约 8%、最大行业约 25.54%、拖累股数量降到 0，不修改 current。

## stage

us_live_strategy_monitoring_round265_268

## kpi_version

us_live_monitoring_intraday_2026_07_16_compact_no_delete_volume_micro

## verification

- `python scripts\tmp_validate_us_live_20260716.py`：411 策略、3466 持仓、232 跑赢、179 跑输保留、持仓数量只含 5/7/10/20、报告 JSON 为 411。
- `$env:PYTHONPATH='.'; pytest -q`：172 passed, 8 skipped。
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_build_current_model_portfolio.py scripts\us_generate_live_html_report.py`：通过。

## lessons

- 成交确认 + 低波动延续、微结构保护 + 中期动量能产生新入池策略，优于继续只调 live-strength 阈值。
- round267-268 未新增，说明该方向已经开始遇到随机检验边界；下一批不应继续原样扫同一空间。
- 模型组合 v5 已能完全避开当前拖累股清单，说明新增 5/7 策略来源开始改善组合层可选股票质量。

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:live_monitoring
- strategy:volume_confirmed_low_vol_extension
- strategy:micro_reversal_protected_momentum
- status:no_delete_underperformers

## next_step

- 从 round269 继续；优先做方向切换而不是重复 round265-268 参数。
- 可尝试“低拥挤 5/7 强选择”和“20 只组合专用候选”，但必须继续保持滚动样本外、随机检验、实盘超基准为正三重门槛。
- 组合层 v6 应保持拖累股为 0，同时观察行业和单股上限是否稳定。
