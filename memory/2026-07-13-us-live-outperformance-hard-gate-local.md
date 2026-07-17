# 2026-07-13 美股实盘超基准硬门槛修正

- stage: monitoring-rule-fix
- kpi_version: us_daily_dynamic_liquidity_v1
- tags: project:quant-agent-team-us, market:us, freq:daily, review-decision, monitoring-observation
- summary: 用户纠正当前监控池口径：实盘绝对收益可以为负，但实盘超基准收益必须大于 0；实盘跑不过同口径基准的策略都不要进入当前实盘池、正式监控主表或当前报告。
- decision: 已将 `实盘超基准收益 > 0` 写入 `us_live_pool.py` 后续入池过滤逻辑，并重建当前正式监控主表。当前监控从 125 个策略降为 103 个策略，持仓从 1810 条降为 1490 条，最小实盘超基准收益为 0.000317。
- validation: 单元测试 16 passed；当前报告策略数 103，持仓数 1490，持仓档位仅为 10 和 20，报告中实盘超基准收益不大于 0 的策略数为 0。
- next_step: 后续策略探索继续允许绝对实盘收益为负，但凡实盘超基准收益不大于 0，一律只保留研究记录，不进入当前监控和当前报告。
