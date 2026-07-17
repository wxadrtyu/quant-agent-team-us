# 2026-07-17 US round296-297 cleanmomentum

## Summary

Stage: new-branch-exploration

Implemented and tested a `cleanmomentum` branch after the round296 diagnosis showed that weak live performance was concentrated in old pullback clusters. The branch keeps medium-term trend logic but requires current confirmation, volume confirmation, and failure protection while rejecting weak pullback cores.

No strategy was appended to `current`. Existing current strategies were not deleted or filtered.

## Branch logic

`cleanmomentum` accepts 5/7-stock candidates only. It requires:

- medium trend: at least two of `ret_20d`, `ret_60d`, `mom_252_21`, `macd_hist`, `ma20_above_ma60`
- current confirmation: `close_pos_20d`, `px_to_ma20`, or `ma20_above_ma60`
- volume confirmation: `volume_ma_ratio_5_20`, `obv_change_20`, or `cmf_20`
- failure protection: `range_pct_5d`, `vol_20d`, `atr_20d`, or `parkinson_vol_20d`

It rejects weak pullback cores observed in round296:

- `ret_5d + ret_120d + px_to_ma60`
- `ret_120d + ret_5d + turnover_stability_20d`
- `ret_120d + ret_5d + ret_skew_20d`
- `ret_120d + px_to_ma60 + turnover_stability_20d`

## Run result

Command:

`python scripts\us_live_strength_strategy_exploration.py --start-round 296 --rounds 2 --candidates-per-round 36 --candidate-limit 2400 --branch cleanmomentum --rolling-top-k 18 --null-top-k 18 --null-iter 700 --max-signal-overlap 0.70`

Result:

- candidate structures: 36
- evaluated top/rebalance combinations: 216
- live failures due drag symbols: 130
- live failures due hit-rate: 49
- live screen pass: 37
- overlap failures: 18
- final live excess failures: 19
- final pool pass: 0

Interpretation: clean momentum as initially defined is not a directly useful new alpha branch. It either recreates crowded megacap/hardware exposure or fails to beat the live benchmark after overlap control. This branch should not be hard-scanned again without a new ingredient.

## Current report state

The live report was regenerated after the batch:

- current strategies: 425
- outperformers: 246
- underperformers retained: 179
- persistent outperformers: 246
- valuation date: 2026-07-16
- holding counts: 5/7/10/20 only

## Validation

- `python scripts\tmp_validate_us_live_20260716.py`: passed
- `python -m py_compile scripts\us_live_strength_strategy_exploration.py scripts\us_generate_live_html_report.py`: passed
- `$env:PYTHONPATH='.'; pytest -q`: 182 passed, 8 skipped

## Next step

Do not continue hard-scanning `cleanmomentum`. The better next direction is `breadthquality20`: a true 20-stock candidate branch built before backtest, not a post-hoc model portfolio, using persistent winner support, loser-exposure penalty, sector cap, and cluster diversity.
