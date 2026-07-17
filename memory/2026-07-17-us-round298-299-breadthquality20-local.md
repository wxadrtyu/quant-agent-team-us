# 2026-07-17 US round298-299 breadthquality20

## Summary

Stage: new-branch-exploration

Implemented and tested a true `breadthquality20` exploration branch. Unlike the v13 post-hoc model portfolio, this branch creates 20-stock candidates before rolling out-of-sample and random/null validation.

No strategy was appended to `current`. Existing current strategies were not deleted or filtered.

## Branch logic

`breadthquality20` accepts 20-stock candidates only. It requires:

- medium strength: `ret_20d`, `ret_60d`, `mom_252_21`, `macd_hist`, or `ma20_above_ma60`
- liquidity quality: `dollar_volume_20d` or `turnover_stability_20d`
- risk balance: `vol_20d`, `vol_60d`, `atr_20d`, or `parkinson_vol_20d`
- confirmation: `obv_change_20`, `volume_ma_ratio_5_20`, `cmf_20`, or `close_pos_20d`

It rejects the weak pullback cores diagnosed in round296:

- `ret_5d + ret_120d + px_to_ma60`
- `ret_120d + ret_5d + turnover_stability_20d`
- `ret_120d + px_to_ma60 + turnover_stability_20d`

## Run result

Command:

`python scripts\us_live_strength_strategy_exploration.py --start-round 298 --rounds 2 --candidates-per-round 36 --candidate-limit 3000 --branch breadthquality20 --rolling-top-k 18 --null-top-k 18 --null-iter 700 --max-signal-overlap 0.70`

Result:

- round298 candidate file: `E:\quant-agent-team-us\research\2026-07-17-round298-live-strength-candidates.csv`
- best rolling information ratio: 1.0539
- best random significance probability: 0.1612
- promoted strategies: 0
- promoted holdings: 0

Interpretation: `breadthquality20` is more coherent than `cleanmomentum`, but the first batch is not statistically strong enough. It should not be added to current. Further work should either add a stronger symbol-level loser-exposure penalty into candidate generation or blend persistent winner support before scoring.

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
- `$env:PYTHONPATH='.'; pytest -q`: 183 passed, 8 skipped

## Next step

Do not add `breadthquality20` to current yet. Next exploration should improve the branch by using round296 diagnostics directly in scoring:

- penalize symbols with high loser-minus-winner exposure
- reward symbols supported by persistent winners
- keep sector and strategy-cluster diversity
- then rerun as a true 20-stock candidate branch, not as a post-hoc portfolio
