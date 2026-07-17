# 2026-07-17 美股策略探索 round278-286 本地记忆

## summary

- round278 增加行业轮动代理后追加 1 条 20 只持仓策略，current 从 420 到 421。
- round280 曾有 2 条提升候选，但追加 current 后去重为 0；round281 无新增。
- 本轮新增 `--branch` 分支探索参数：`strong` 只验证 5/7 强选择，`portfolio20` 只验证 20 只稳定组合，`mixed` 保留原混合池。
- 新增 `--revisit-historical-candidates`，只排除已入池或已提升的策略键，不再让历史候选文件阻断新的分支再排序。
- round282-283 强选择分支、round284-285 20 只组合分支、round286 扩大强选择滚动覆盖后均无新增入库。
- 失败主因不是当前实盘收益弱，而是随机去偏检验没有同时达到提升门槛：强选择最接近，超基准随机概率很好，但去偏标准分约 1.60-1.66，未达 1.85；20 只组合更稳但信息比率与去偏更弱。

## stage

strategy-exploration

## kpi_version

us-live-current-compact-2026-07-16-intraday

## tags

- project:quant-agent-team-us
- market:us
- freq:daily
- stage:strategy-exploration
- status:no-new-current-round282-286

## validation

- current 策略数：421
- current 持仓数：3591
- 当前跑赢：242
- 跑输诊断保留：179
- 入库至今持续跑赢：242
- 持仓数分布：5=90, 7=123, 10=188, 20=20
- 报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`
- 模型组合：`reports/us/live/current/us_current_model_portfolio_20260716_v9.csv`，20 只，拖累股 0，未替代 current。
- 测试：`177 passed, 8 skipped`

## next_step

- 不要继续硬扫当前 `qmv + 60日强度 + 均线 + 资金流 + 风险/稳定` 空间；它已经接近随机去偏上限。
- 下一轮应新开 alpha 结构，例如：
  - 事件期成交确认与趋势保持的组合，但减少对同一 `qmv` 模板的依赖。
  - 纯流动性质量与低拥挤风格的 5/7 强选择，避免复用已接近上限的收益偏态组合。
  - 20 只组合若继续，需要引入更强的组合层相关性或风格轮动代理，否则单策略信息比率难过门槛。
