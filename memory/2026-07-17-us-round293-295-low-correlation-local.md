# 2026-07-17 美股策略探索 round293-295 本地记忆

## summary

- 新增两个低相关单策略结构：
  - `diffusion`：相对强度扩散，避开 `ret_120d + px_to_ma20 + turnover_stability_20d` 共同核心。
  - `industrylowcrowd`：行业内低拥挤排序，强调相对趋势、成交/流动性确认、风险控制，也避开 round287 共同核心。
- 按测试先行新增 `is_relative_strength_diffusion_set`、`is_industry_low_congestion_relative_set` 和分支路由。
- round293 `diffusion` 无新增：最优滚动信息比率约 1.19，随机显著性概率约 0.083。
- round295 `industrylowcrowd` 无新增：最优滚动信息比率约 1.26，随机显著性概率约 0.101。
- 经验：去掉 round287 的共同核心后，单策略 alpha 明显变弱。低相关不能靠简单剔除核心因子获得，需要组合层控制或新数据维度。

## stage

strategy-exploration

## kpi_version

us-live-current-compact-2026-07-16-intraday

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:strategy-exploration
- status:no-new-current-round293-295

## validation

- current 策略数：425
- current 持仓数：3611
- 当前跑赢：246
- 跑输诊断保留：179
- 入库至今持续跑赢：246
- 持仓数分布：5=94, 7=123, 10=188, 20=20
- 报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`
- 模型组合：`reports/us/live/current/us_current_model_portfolio_20260716_v12.csv`，20 只，拖累股 0，未替代 current。
- 测试：`180 passed, 8 skipped`

## next_step

- 不要继续硬扫 `diffusion` 或 `industrylowcrowd` 当前结构；它们单策略信号不够强。
- 下一轮优先做组合层相关性控制：从 current 持续跑赢策略中构建 20 只组合，加入单股/行业/策略簇相关性约束，再作为候选组合报告输出；不要直接修改 current。
- 若继续单策略探索，需要引入新维度或新因子族，而不是只重排现有价格量价因子。
