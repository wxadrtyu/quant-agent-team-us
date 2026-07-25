# 2026-07-25 US live update to 2026-07-24

## Summary

- Updated US live monitoring data to valuation date 2026-07-24.
- Raw data output:
  - `E:\quant-agent-team-us\data\us\raw\2026-07-24-intraday-chart`
- Report output:
  - `reports/us/live/current/us_simulation_formal_monitoring_detail_0630_0724.html`
  - `reports/us/live/current/us_simulation_formal_monitoring_0630_0724.json`

## Data Refresh

- Source: Yahoo Finance chart API incremental append.
- Base raw dir: `E:\quant-agent-team-us\data\us\raw\2026-07-17-intraday-chart`.
- Max trade date: 2026-07-24.
- Symbols requested: 1011.
- Symbols refreshed: 1010.
- Error: NSA returned empty result.
- Latest daily coverage from 2026-07-20 through 2026-07-24 is 1010 symbols.

## Revaluation

- Signal date: 2026-06-30.
- Entry date: 2026-07-01.
- Valuation date: 2026-07-24.
- Benchmark return: 0.4049935844%.
- Current strategies retained: 430.
- Current holdings retained: 3636.
- Current outperformers: 360.
- Underperformers retained for diagnosis: 70.
- Persistent outperformers since admission: 207.
- Holding distribution:
  - 5: 99
  - 7: 123
  - 10: 188
  - 20: 20

## Validation

- `scripts/us_validate_live_current.py` passed.
- Invalid holding count: 0.
- No fallback US names in report.
- Report has age fields.
- JSON has persistent outperformer tab data.
- Underperformers are retained in current and report diagnostics.

## Next Step

- Use 2026-07-24 as the latest live valuation date for further monitoring and strategy diagnostics.
- Before further exploration, update hardcoded default raw-dir constants in research scripts if they should use 2026-07-24 by default; otherwise pass `--raw-dir` explicitly.
