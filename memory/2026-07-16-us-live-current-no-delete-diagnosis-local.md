# 2026-07-16 美股 current 不删除跑输策略与诊断页签修正

## 背景

用户纠正：不能因为策略阶段性跑输基准就从 current 或报告中删除。正确做法是保留监控样本，分析为什么跑输，并推动后续探索产生更多能持续跑赢基准的策略。

## 修正内容

- 恢复 current 全量 338 条策略。
- 当前跑赢基准策略：159 条。
- 当前跑输基准策略：179 条，全部保留在 current 和报告中，不删除。
- current 持仓恢复为 2907 行。
- 新增字段：
  - `入库日期`
  - `入库天数`
  - `当前是否跑赢基准`
  - `入库后可用估值次数`
  - `入库至今持续跑赢`
  - `当前诊断`
- 报告新增页签：
  - `入库至今持续跑赢`
  - `当前跑赢基准`
  - `跑输诊断`
- `跑输诊断` 页签展示跑输基准策略的超基准收益、基准收益、入库多久、最大拖累个股和诊断原因。

## 数据口径

- 入库日期从重估前 current 表的 `current_run_id` 解析。
- 入库天数按 `估值日期 - 入库日期` 计算。
- 当前可用的入库后估值快照只有 2026-07-16 这一版，因此 `入库至今持续跑赢` 目前等价于“截至 2026-07-16 仍跑赢基准”。后续每日更新后，该字段应扩展为按入库后全部可用估值快照连续判断。

## 文件与表

- 恢复脚本：`scripts/tmp_restore_us_current_with_age_20260716.py`
- 报告生成器：`scripts/us_generate_live_html_report.py`
- 校验脚本：`scripts/tmp_validate_us_live_20260716.py`
- 新报告：`reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`
- JSON：`reports/us/live/current/us_simulation_formal_monitoring_0630_0716.json`

## 验证

- current 策略数：338。
- current 持仓数：2907。
- 当前跑赢基准：159。
- 当前跑输基准但保留：179。
- 入库至今持续跑赢：159。
- 估值日全部为 2026-07-16。
- 持仓数分布：5 只 63 条，7 只 96 条，10 只 166 条，20 只 13 条。
- 报告 JSON 策略数与 current 策略数一致。
- 报告无 `NaN`、`Infinity`、`__PLACEHOLDER__`、`TBD`。
- 报告无 `（美股）` 兜底名。
- `python -m py_compile scripts\tmp_restore_us_current_with_age_20260716.py scripts\us_generate_live_html_report.py scripts\tmp_validate_us_live_20260716.py` 通过。
- `$env:PYTHONPATH='.'; pytest -q` 通过：166 passed, 8 skipped。

## 后续规则

- 已进入 current/实盘池/监控池的策略不得因阶段性跑输基准被删除。
- 跑输基准策略必须进入诊断页签，用于分析因子、持仓、风格、集中度、个股拖累和市场环境。
- 新增策略仍必须通过滚动样本外、随机检验、实盘超基准为正后才能追加到 current。
- 当前报告必须全量保留 current，同时提供当前跑赢、当前跑输诊断、入库至今持续跑赢三个筛选视角。
