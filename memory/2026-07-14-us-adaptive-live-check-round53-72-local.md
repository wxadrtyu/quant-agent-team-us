# 2026-07-14 美股自适应实盘检查探索第 53-72 轮本地记忆

summary: 在第 23-52 轮之后先复盘经验，再分两批各 10 轮探索。第 53-62 轮先验证“中期趋势 + 短回调 + 成交稳定 + 资金流/低波动”结构，10 轮后检查实盘，只新增 8 个策略、65 条持仓。随后根据实盘通过组进一步收窄到 `cmf_10/cmf_20 + vol_20d/parkinson_vol_20d/atr_20d + px_to_ma20/macd_hist`，第 63-72 轮新增 42 个策略、336 条持仓，说明先检查实盘再收窄搜索空间有效。

stage: adaptive-live-checked-exploration
kpi_version: us_daily_live_v1_2026-07-14
tags:
- project:quant-agent-team-us
- market:us
- freq:daily
- stage:adaptive-live-check
- status:live-outperformance-filtered

lessons:
- 不要盲目扩大历史高信息比率结构。第 23、27、38、44、49、51 等轮次历史和随机检验都强，但实盘未跑赢基准，应作为反过拟合样本。
- 实盘有效组更多来自 `ret_120d + ret_5d + px_to_ma60 + turnover_stability_20d`，再叠加 `cmf_10/cmf_20` 和低波动类因子。
- `mfi_7`、`obv_change_20`、`ret_skew_20d`、`rsi_14` 在第 53-62 轮里稳定性较弱，后续不应作为优先扩展方向。
- 每跑 10 轮必须做一次实盘通过率检查，再决定是继续扩展、收窄，还是停止该族。

round_results:
- 第 53-62 轮: 10 轮，3 轮入库，新增 8 个策略、65 条持仓。
- 第 63-72 轮: 10 轮，7 轮入库，新增 42 个策略、336 条持仓。

current_monitoring:
- 当前监控表: `us_live_monitoring_strategies_current`，268 个策略。
- 当前持仓表: `us_live_monitoring_holdings_current`，2711 条持仓。
- 当前持仓分布: 5 持仓 42 个，7 持仓 73 个，10 持仓 107 个，20 持仓 46 个。
- 当前池最小实盘超基准收益: 0.0003172228817951428。
- 当前池平均信息比率: 2.078247823533504。
- 当前池最大回撤中位数: 0.1499797430769009。

validated_outputs:
- 第 53-62 轮汇总: `E:\quant-agent-team-us\research\2026-07-14-adaptive-live-learned-round53-62-summary.csv`。
- 第 63-72 轮汇总: `E:\quant-agent-team-us\research\2026-07-14-adaptive2-live-checked-round63-72-summary.csv`。
- 当前报告: `reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`。
- 当前明细页: `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`。

verification:
- `pytest tests\test_us_live_pool.py tests\test_us_rolling_validation.py tests\test_us_null_overfit_check.py tests\test_us_research_db_ingest.py tests\test_us_universe.py tests\test_us_model_portfolio.py -q` 通过，17 passed。
- `python -m py_compile scripts\us_explore_strategy_rounds.py scripts\us_live_pool.py scripts\us_rolling_validation.py scripts\us_null_overfit_check.py scripts\us_generate_live_html_report.py` 通过。
- 报告校验: `non_outperform=0`，`bad_bracket=0`，`bad_fallback=0`，`bad_tokens=[]`。

next_step: 下一轮先不要继续扩大轮数。应围绕第 63-72 轮实盘通过组做持仓重叠、行业集中度、个股贡献和 2026-06-30 至 2026-07-10 实盘失败/成功分解，再决定是否开第三批 10 轮。
