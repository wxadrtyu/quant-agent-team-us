# 2026-07-17 美股 round251-256 与模型组合 v2 本地记忆

## summary

- 当前正式 current/监控池不删减：`us_live_monitoring_strategies_current` 保持 395 条，持仓 3303 条；当前跑赢 216 条，跑输诊断保留 179 条，入库至今持续跑赢 216 条。
- 估值日期保持 `2026-07-16`，报告重生成到 `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`。
- round251-252 质量稳定探索无新增；虽然样本外滚动指标高，但最终没有通过入池门槛。
- round253-254 边际低重叠探索无新增；best rolling IR 约 1.46/1.36，随机检验边际不足或未形成可追加策略。
- round255-256 分散实盘探索无新增；说明单纯加分散约束不是 alpha 来源。
- 新增 `scripts/us_build_current_model_portfolio.py` 的组合层聚合 v2：只生成候选 20 只模型组合文件，不修改 current；加入拖累股单股上限、单行业上限、拥挤度惩罚。

## stage

us_live_strategy_monitoring_round251_256

## kpi_version

us_live_monitoring_intraday_2026_07_16_compact_no_delete

## verification

- `python scripts\tmp_validate_us_live_20260716.py`：395 策略、3303 持仓、216 跑赢、179 跑输保留、持仓数量只含 5/7/10/20、无兜底名、报告存在。
- `$env:PYTHONPATH='.'; pytest -q`：167 passed, 8 skipped。
- `python scripts\us_build_current_model_portfolio.py --date 20260716 --target-symbols 20 --max-symbol-weight 0.08 --max-drag-weight 0.02 --max-sector-weight 0.30`：20 只、总权重 100%、单股最大 8%、单行业最大 30%。

## lessons

- 历史样本外表现很高但无法入池，主要说明当前 live-aware 门槛正在筛掉旧模板的过拟合或阶段失效组合，不能降低门槛硬加。
- 分散约束只能控制风险，不创造 alpha；下一批不应继续重复 round239-256 的行业分散/低重叠扫描。
- 20 只持仓更适合做组合层聚合，而不是直接套单策略排名。候选组合要继续控制拖累股、行业、拥挤度和单一策略来源贡献。

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:live_monitoring
- strategy:current_compact_pool
- status:no_delete_underperformers

## next_step

- 从 round257 继续，但优先改候选生成逻辑：减少回调趋势旧模板重复，增加当前相对强度、收益质量、非拖累暴露、短期反转失败保护。
- 组合层继续做 v3：减少拖累股数量本身，而不只是压权重；加入候选股票当前贡献、行业贡献、策略来源贡献的报告解释。
