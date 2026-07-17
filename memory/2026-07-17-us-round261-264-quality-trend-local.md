# 2026-07-17 美股 round261-264 quality-trend 探索本地记忆

## summary

- round261-262 使用更严格 live-strength 低重叠参数，round261 有 1 条 promoted，但追加去重后为 0；round262 无新增。结论：单纯调低重叠阈值已经不够，需要改变候选因子族。
- 在 `scripts/us_live_strength_strategy_exploration.py` 中新增质量趋势判定 `is_quality_trend_factor_set`，强调中长期强度、流动性/风险稳定、成交确认，并过滤旧的 `ret_5d + ret_120d + px_to_ma60` 回调核心。
- 新增测试覆盖质量趋势优先级；`tests/test_us_live_strength_strategy_exploration.py` 从 2 个测试增至 3 个测试。
- round263-264 使用质量趋势/成交确认结构，round264 追加 2 条新策略，新增平均实盘超基准约 +2.30%，最低约 +2.25%；current 从 406 条增至 408 条。
- 报告重生成到 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`；模型组合 v4 输出到 `reports/us/live/current/us_current_model_portfolio_20260716_v4.csv`，不修改 current。

## stage

us_live_strategy_monitoring_round261_264

## kpi_version

us_live_monitoring_intraday_2026_07_16_compact_no_delete_quality_trend

## verification

- `python scripts\tmp_validate_us_live_20260716.py`：408 策略、3436 持仓、229 跑赢、179 跑输保留、持仓数量只含 5/7/10/20、报告 JSON 为 408。
- `$env:PYTHONPATH='.'; pytest -q`：171 passed, 8 skipped。
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_build_current_model_portfolio.py scripts\us_generate_live_html_report.py`：通过。

## lessons

- live-strength 第一版已经接近重复边界；继续用同一空间只会出现 promoted 后被 current 去重的候选。
- 质量趋势/成交确认能重新打开少量新空间，但新增超基准低于 round257-258，说明质量趋势目前是补充 alpha，不是主力 alpha。
- 目前没有真实基本面字段，不能把日频技术/流动性代理写成真正的盈利质量或财务质量；报告和记忆里应明确这是代理。

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:live_monitoring
- strategy:quality_trend_live_strength
- status:no_delete_underperformers

## next_step

- 从 round265 继续；不要继续只调 live-strength 阈值。优先新开“成交确认 + 低波动延续”或“微结构反转失败保护 + 中期动量”两个方向。
- 继续模型组合 v5，但如果 current 新增仍少，组合层不会有实质变化，应优先生产更多非拖累、非重复的 5/7 策略来源。
