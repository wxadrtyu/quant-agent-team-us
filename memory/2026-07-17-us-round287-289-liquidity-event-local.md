# 2026-07-17 美股策略探索 round287-289 本地记忆

## summary

- 新增两个候选结构分支：
  - `liquidity`：流动性质量低拥挤，要求流动性/换手稳定、低波或波动平衡、耐用趋势强度，并排除上一轮已接近上限的资金流 qmv 核心。
  - `eventtrend`：事件期成交确认与趋势保持，要求成交事件代理、趋势保持和失败保护。
- 新增测试覆盖分支隔离，先观察到导入失败红灯，再实现后通过。
- round287 使用 `liquidity` 分支追加 4 条 5 只持仓策略；新增平均实盘超基准约 +1.47%，最低约 +1.47%。
- round289 使用 `eventtrend` 分支无新增；最优滚动信息比率仅 1.26，随机显著性概率约 0.098，暂不值得继续原样硬扫。
- round287 的实际有效结构集中在“长期强度 + 20日收盘位置 + 低波风险 + 换手稳定”，比上一批 qmv 资金流结构更稳健。

## stage

strategy-exploration

## kpi_version

us-live-current-compact-2026-07-16-intraday

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:strategy-exploration
- status:round287-added

## validation

- current 策略数：425
- current 持仓数：3611
- 当前跑赢：246
- 跑输诊断保留：179
- 入库至今持续跑赢：246
- 持仓数分布：5=94, 7=123, 10=188, 20=20
- 报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`
- 模型组合：`reports/us/live/current/us_current_model_portfolio_20260716_v10.csv`，20 只，拖累股 0，未替代 current。
- 测试：`178 passed, 8 skipped`

## next_step

- 从 round290 或 round291 继续时，不要原样扩大 `eventtrend`；它当前信息比率和随机显著性都弱。
- 优先沿 round287 的有效结构扩展：`close_pos_20d + px_to_ma20 + ret_120d + 低波风险 + turnover_stability_20d`，但要控制与新增 4 条的持仓重叠，避免只复制同一批 5 只股票。
- 可尝试将 `liquidity` 分支拆成“长期强度收盘位置”和“防御质量趋势”两个子方向，分别提高低重叠约束和候选多样性。
