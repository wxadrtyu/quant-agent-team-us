# 2026-07-16 美股实盘估值日修正

## 背景

用户指出当前实盘报告估值日不应停留在 2026-07-10，而应使用更新实盘当天，即 2026-07-16。

## 执行结果

- 使用 `E:\quant-agent-team-us\data\us\raw\2026-07-12` 全量快照作为基底。
- `yfinance` 批量下载只覆盖 60/1011 只，已判定不合格，未用于估值。
- 改用 Yahoo Finance chart API 逐票补齐 2026-07-13 至 2026-07-16 价格，输出到 `E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart`。
- 新快照 2026-07-13、2026-07-14、2026-07-15、2026-07-16 均覆盖 1011/1011 只。
- 由于执行时为北京时间 2026-07-16 晚间，美股 2026-07-16 仍在盘中，本次估值定义为盘中估值，不等同于美股收盘最终估值。

## 入库与报告

- 全量重估当前 338 条策略，信号日 2026-06-30，入场日 2026-07-01，估值日 2026-07-16。
- 保留原 current 表备份：`us_live_monitoring_strategies_current_backup_20260716_225429`、`us_live_monitoring_holdings_current_backup_20260716_225429`。
- 全量重估表：`us_live_monitoring_strategies_revalued_20260716`，共 338 条。
- 当前报告口径只保留实盘超基准收益大于 0 的策略：159 条。
- 跑输基准但未删除历史记录的策略备份在：`us_live_monitoring_strategies_excluded_20260716_intraday`，共 179 条。
- 当前持仓表：`us_live_monitoring_holdings_current`，共 1359 行。
- 新报告：
  - `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0716.html`
  - `reports/us/live/current/us_simulation_formal_monitoring_simple_0630_0716.html`
  - `reports/us/live/current/us_simulation_formal_monitoring_0630_0716.json`

## 验证

- current 策略数：159。
- current 持仓数：1359。
- 估值日全部为 2026-07-16。
- 当前报告无实盘超基准收益小于等于 0 的策略。
- 持仓数分布：5 只 29 条，7 只 52 条，10 只 71 条，20 只 7 条。
- 无非法持仓数。
- 报告无 `NaN`、`Infinity`、`__PLACEHOLDER__`、`TBD`。
- 报告无 `（美股）` 兜底名。
- `python -m py_compile scripts\tmp_update_us_intraday_raw_chart.py scripts\tmp_revalue_us_current_live_20260716.py scripts\us_generate_live_html_report.py` 通过。
- `$env:PYTHONPATH='.'; pytest -q` 通过：166 passed, 8 skipped。

## 后续规则

- 后续更新实盘报告时，估值日必须使用更新当天可用的最新交易日；盘中更新必须标注为盘中估值。
- 不得使用覆盖不完整的当日快照更新 current 报告。
- 历史已进池策略不删除；当前报告口径仍需过滤实盘跑输基准的策略，并把被过滤策略写入独立备份表。
