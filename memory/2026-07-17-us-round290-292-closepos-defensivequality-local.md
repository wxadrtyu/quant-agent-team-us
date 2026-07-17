# 2026-07-17 美股策略探索 round290-292 本地记忆

## summary

- 基于 round287 的有效结构继续拆分两个子方向：
  - `closepos`：长期强度 + 20日收盘位置 + 均线位置 + 低波/稳定。
  - `defensivequality`：长期强度 + 趋势位置 + 防御低波 + 换手稳定 + 尾部保护。
- 按测试先行新增 `is_long_strength_close_position_set` 和 `is_defensive_quality_trend_set`，并接入分支选择。
- round290 `closepos` 无新增：最优滚动信息比率约 1.52，随机收益显著性较好，但去偏标准分约 1.65，未达 1.85。
- round292 `defensivequality` 无新增：最优滚动信息比率约 1.52，但随机显著性概率约 0.061，未达 0.04。
- 并行跑两条分支时出现 DuckDB 写锁，已串行补跑 closepos 并完成总结文件。后续 DuckDB 写库步骤避免并行。

## stage

strategy-exploration

## kpi_version

us-live-current-compact-2026-07-16-intraday

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:strategy-exploration
- status:no-new-current-round290-292

## validation

- current 策略数：425
- current 持仓数：3611
- 当前跑赢：246
- 跑输诊断保留：179
- 入库至今持续跑赢：246
- 持仓数分布：5=94, 7=123, 10=188, 20=20
- 报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`
- 模型组合：`reports/us/live/current/us_current_model_portfolio_20260716_v11.csv`，20 只，拖累股 0，未替代 current。
- 测试：`179 passed, 8 skipped`

## next_step

- 不要继续原样硬扫 `closepos` 或 `defensivequality`，它们已接近但未通过随机去偏。
- 下一轮应转向更低相关结构：
  - 5/7 只组合：去掉 `ret_120d + px_to_ma20 + turnover_stability_20d` 共同核心，尝试相对强度扩散、短周期成交确认失败保护、或低拥挤行业内排序。
  - 20 只组合：尝试组合层相关性控制，而非单策略排序继续加参数。
- DuckDB 写库和报告生成必须串行执行，避免再次与策略提升写库并发。
