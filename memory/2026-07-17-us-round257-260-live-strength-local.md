# 2026-07-17 美股 round257-260 live-strength 探索本地记忆

## summary

- 新增 `scripts/us_live_strength_strategy_exploration.py`，候选生成从旧回调/分散模板改为当前实盘相对强度优先。
- 新增测试 `tests/test_us_live_strength_strategy_exploration.py`，覆盖拖累股暴露、弱命中率、短期反转失败惩罚。
- round257-258 共生成 11 条可追加策略，追加后 current 从 395 条增至 406 条；新增策略平均实盘超基准约 +5.53%，最低约 +4.85%。
- round259 有 2 条 promoted，但追加阶段去重后为 0，current 保持 406 条；round260 无新增。
- 模型组合 v3 输出到 `reports/us/live/current/us_current_model_portfolio_20260716_v3.csv`，不修改 current；拖累股数量从 v2 的 9 个降到 5 个，单股最高 8%，最大行业权重约 25.45%。
- 当前报告重生成到 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`，仍保留跑输诊断策略。

## stage

us_live_strategy_monitoring_round257_260

## kpi_version

us_live_monitoring_intraday_2026_07_16_compact_no_delete_live_strength

## verification

- `python scripts\tmp_validate_us_live_20260716.py`：406 策略、3411 持仓、227 跑赢、179 跑输保留、持仓数量只含 5/7/10/20、无兜底名、报告 JSON 为 406。
- `$env:PYTHONPATH='.'; pytest -q`：170 passed, 8 skipped。
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_build_current_model_portfolio.py scripts\us_generate_live_html_report.py`：通过。

## lessons

- 当前强度优先明显好于继续硬扫旧回调/分散模板；round257-258 一次小批就新增 11 条，说明前一阶段瓶颈在候选排序而不是验证门槛。
- 追加脚本会去重，round259 promoted 但未追加，说明继续同一 live-strength 空间会较快出现重复，需要下一步扩大 alpha 结构或提高低重叠约束。
- 模型组合层可以减少拖累股数量，但在 20 只目标下当前干净候选不足，不能为了完全剔除拖累股而破坏 20 只持仓要求。

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:live_monitoring
- strategy:live_strength
- status:no_delete_underperformers

## next_step

- 从 round261 继续；优先在 live-strength 结构上提高去重和低重叠要求，增加非重复因子组合，例如质量趋势、盈利稳定代理、成交确认和短期失败保护。
- 继续生成模型组合 v4：优先补充更多非拖累候选来源，目标进一步减少拖累股数量，而不是只压权重。
