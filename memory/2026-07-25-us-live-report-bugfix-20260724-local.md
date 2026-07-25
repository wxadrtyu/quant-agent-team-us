# 2026-07-25 美股实盘报告 2026-07-24 修复

- summary: 修复 2026-07-24 美股 current 实盘报告生成链路。报告生成脚本不再默认使用固定 2026-07-17 行情目录，改为按 current 表估值日自动选择对应 raw-dir；生成前强制检查缺价、策略收益与持仓贡献一致性、策略展示编号唯一性和空持仓；验证脚本同步增加这些硬检查。已重生成 2026-07-24 current 报告。
- stage: monitoring-observation
- kpi_version: v1.1
- tags: project:quant-agent-team-us, market:us, freq:daily, stage:live-report-bugfix, status:fixed
- verification:
  - `python -m unittest tests.test_us_live_report_integrity -v`: 4 passed.
  - `python scripts\us_generate_live_html_report.py --out-dir <temp>` without `--raw-dir`: generated 430-strategy 2026-07-24 report and passed validation.
  - Explicit stale `--raw-dir E:\quant-agent-team-us\data\us\raw\2026-07-17-intraday-chart`: correctly rejected with 3636 missing price rows and 430 contribution mismatches.
  - `python scripts\us_validate_live_current.py --report ...0630_0724.html --json ...0630_0724.json`: missing price 0, contribution mismatch 0, duplicate strategy display 0, empty holding strategy 0.
  - `python -m unittest discover -s tests -v`: 189 passed, 9 skipped.
- next_step: 后续继续策略探索前，仍建议把其它探索/审计脚本里硬编码的 2026-07-17 raw-dir 统一改成显式参数或自动最新交易日解析。
