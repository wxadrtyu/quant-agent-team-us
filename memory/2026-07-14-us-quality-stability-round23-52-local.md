# 2026-07-14 美股质量稳定性探索第 23-52 轮本地记忆

summary: 完成第 23-52 轮共 30 轮美股日频策略探索，主攻更高样本外表现、更低最大回撤、更稳定信息比率和更好的 2026-06-30 至 2026-07-10 实盘超基准表现。候选持仓只使用 5、7、10，当前池仍允许既有 20 持仓策略。入库门槛比前序更严格：滚动样本外信息比率至少 1.50，随机检验显著性概率不高于 0.04，去偏标准分至少 1.85，且实盘超基准收益必须大于 0。

stage: quality-stability-strategy-exploration
kpi_version: us_daily_live_v1_2026-07-14
tags:
- project:quant-agent-team-us
- market:us
- freq:daily
- stage:quality-stability-exploration
- status:live-outperformance-filtered

round_results:
- 完成轮数: 30，范围第 23 轮至第 52 轮。
- 有策略入库的轮数: 15。
- 本轮批量新增入库策略: 99。
- 本轮批量新增持仓记录: 718。
- 第 51 轮历史滚动和随机检验极强，最好信息比率 3.9566、最大回撤 0.0840、随机检验显著性概率 0.0005，但 2026-06-30 至 2026-07-10 实盘未跑赢基准，入库为 0，应记录为“历史强但实盘窗口失败”的反过拟合样本。
- 第 52 轮历史滚动通过一批候选，但最大回撤偏高且实盘未跑赢，入库为 0。

current_monitoring:
- 当前监控表: `us_live_monitoring_strategies_current`，218 个策略。
- 当前持仓表: `us_live_monitoring_holdings_current`，2310 条持仓。
- 当前持仓分布: 5 持仓 36 个，7 持仓 50 个，10 持仓 86 个，20 持仓 46 个。
- 当前池最小实盘超基准收益: 0.0003172228817951428。
- 当前池平均信息比率: 2.0279805945255767。
- 当前池最大回撤中位数: 0.14739128725454095。

validated_outputs:
- 批量探索脚本: `scripts/us_explore_strategy_rounds.py`。
- 30 轮汇总: `E:\quant-agent-team-us\research\2026-07-13-quality-stability-round23-52-summary.csv`。
- 当前报告: `reports/us/live/current/us_simulation_formal_monitoring_0630_0710.json`。
- 当前明细页: `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0710.html`。
- 当前简版页: `reports/us/live/current/us_simulation_formal_monitoring_simple_0630_0710.html`。

verification:
- `pytest tests\test_us_live_pool.py tests\test_us_rolling_validation.py tests\test_us_null_overfit_check.py tests\test_us_research_db_ingest.py tests\test_us_universe.py tests\test_us_model_portfolio.py -q` 通过，17 passed。
- `pytest tests\test_us_live_pool.py tests\test_us_rolling_validation.py tests\test_us_null_overfit_check.py -q` 通过，11 passed。
- `python -m py_compile scripts\us_explore_strategy_rounds.py scripts\us_live_pool.py scripts\us_rolling_validation.py scripts\us_null_overfit_check.py scripts\us_generate_live_html_report.py` 通过。
- 报告校验: `non_outperform=0`，`bad_bracket=0`，`bad_fallback=0`，`bad_tokens=[]`。

next_step: 下一轮不要简单扩大 balanced/mom_252_21/px_to_ma60/turnover_stability_20d 家族，因为第 51 轮证明其历史和随机检验可能很强但实盘窗口失败。应优先研究这些策略在 2026-06-30 至 2026-07-10 的失败共性，增加实盘窗口稳健性过滤或市场状态分层，再继续生产。
