# Memory Policy

## 固定标签

- `project:quant-agent-team`
- `market:cn_a`
- `freq:daily`

## 推荐扩展标签

- `stage:<stage>`
- `kpi:<slug>`
- `topic:<topic>`
- `strategy:<strategy_id>`
- `status:<state>`

## 写入时机

- KPI 变更后
- 研究结论形成后
- 数据口径确认后
- 回测完成后
- 风控审核完成后
- 失败实验判定后
- 监控出现零信号或异常时

## 结构建议

```json
{
  "summary": "简要结论",
  "stage": "market-research",
  "kpi_version": "kpi-2026-03-15-001",
  "details": {},
  "next_step": "下一步动作"
}
```

