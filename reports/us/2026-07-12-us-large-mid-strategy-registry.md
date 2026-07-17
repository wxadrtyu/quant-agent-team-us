# US Large/Mid Strategy Registry

> Last updated: 2026-07-12
> Market: US large/mid tradable universe, current S&P 500 / Nasdaq 100 / Russell 1000 snapshot
> Data: `E:\quant-agent-team-us\data\us\raw\2026-07-12`, price max date 2026-07-10
> Research output: `E:\quant-agent-team-us\research\2026-07-12-factory-round4`

## Gate

| Gate | Rule | Status |
|---|---:|---|
| Development window | 2023-06-30 to 2025-06-29 | Required |
| OOS holdout | 2025-06-30 to 2026-06-29 | Required |
| Live proxy | 2026-06-30 signal, 2026-07-01 open entry, 2026-07-10 close mark | Required; relative gate only |
| Relative IR | Dev IR > 0.5 and holdout IR > 0.5 | Required |
| Excess return | Dev, holdout, and live excess return > 0 | Required; absolute live return may be negative |
| MDD | Soft penalty only | Not a hard reject |
| Factor concentration | Max factor weight reported; no single-factor strategy accepted | Required for review |

## Round 4 Summary

| Metric | Value |
|---|---:|
| Candidate hypotheses | 720 |
| Evaluated rows | 2,160 |
| Qualified rows | 297 |
| Factor count | 32 |
| Panel rows | 814,599 |
| Tradable symbols after filters | 985 |

The first 100-candidate round failed because the generator filled the batch with momentum-heavy `qm` combinations before it reached reversal and volume-price templates. The 2026-06-30 to 2026-07-10 live proxy favored short-term pullback and oscillator factors (`rsi_14`, `mfi_14`, `ret_10d`, `obv_change_20`) and punished intermediate momentum/trend (`ret_20d`, `px_to_ma20`, `ret_60d`). Candidate generation was changed to round-robin templates.

## Candidate Strategies

| ID | Strategy | Factors | Top N | Rebalance | Dev excess | Dev IR | Dev avg IR | Dev MDD | OOS excess | OOS IR | OOS avg IR | OOS MDD | Live excess | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| US-BAL-001 | balanced_pullback_obv_vol60_stability | ret_20d, ret_5d, px_to_ma20, obv_change_20, vol_60d, turnover_stability_20d | 10 | 20d | +47.4% | 1.192 | 1.177 | 17.6% | +69.9% | 2.660 | 2.634 | 8.4% | +0.89% | pending_review |
| US-BAL-002 | balanced_pullback_mfi14_atr_liq | ret_20d, ret_5d, px_to_ma20, mfi_14, atr_20d, dollar_volume_20d | 10 | 20d | +61.2% | 1.403 | 1.312 | 19.1% | +60.6% | 2.525 | 2.639 | 7.3% | +0.94% | pending_review |
| US-BAL-003 | balanced_pullback_mfi7_vol60_liq | ret_20d, ret_5d, px_to_ma20, mfi_7, vol_60d, dollar_volume_20d | 10 | 20d | +40.1% | 0.838 | 0.594 | 19.4% | +65.5% | 2.854 | 3.035 | 6.0% | +0.94% | pending_review |
| US-BAL-004 | balanced_pullback_obv_vol20_stability | ret_20d, ret_5d, px_to_ma20, obv_change_20, vol_20d, turnover_stability_20d | 10 | 20d | +36.8% | 0.998 | 0.998 | 17.3% | +72.1% | 2.692 | 2.644 | 8.4% | +0.15% | pending_review |
| US-BAL-005 | balanced_pullback_cmf20_vol20_stability | ret_20d, ret_5d, px_to_ma20, cmf_20, vol_20d, turnover_stability_20d | 10 | 20d | +22.6% | 0.727 | 0.482 | 15.4% | +74.3% | 2.661 | 2.691 | 11.8% | +1.26% | pending_review |

## Rolling Validation

Rolling validation uses the top 20 round4 candidates. For each month from 2025-06-30 to 2026-06-29, factor weights are recomputed using only the prior two years of data; structural parameters (`top_n`, `rebalance_days`) remain fixed from the factory result.

| Rank | Strategy | Rolling excess | Rolling IR | Rolling avg IR | Rolling MDD | Win excess | Factory live excess | Status |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | balanced_pullback_cmf10_vol60_stability | +228.8% | 2.547 | 3.058 | 9.9% | 75% | +0.38% | pending_review |
| 2 | balanced_pullback_cmf20_vol20_stability | +207.5% | 2.468 | 3.009 | 8.6% | 80% | +1.26% | pending_review |
| 3 | balanced_pullback_obv_vol20_stability | +205.3% | 2.426 | 2.836 | 8.6% | 75% | +0.15% | pending_review |
| 4 | balanced_pullback_obv_vol60_stability | +198.5% | 2.391 | 2.854 | 9.0% | 80% | +0.89% | pending_review |

Rolling validation currently favors the `cmf_10` volume-pressure variant over the factory final-score leader. This should be treated as stronger evidence than the fixed holdout ranking, but still requires null/deflated overfit checks and survivorship-bias remediation before monitoring.

## Null And Pool Status

Null test uses the same signal dates, entry dates, exit dates, and `top_n` as each rolling curve. For every period it randomly samples the same number of names from the tradable universe and builds a 2,000-run null distribution.

| ID | Strategy | Rolling IR | Null p(IR) | Null p(excess) | Deflated IR z | Pool status |
|---|---|---:|---:|---:|---:|---|
| US-AUTO-001 | balanced_pullback_cmf10_vol60_stability | 2.547 | 0.0020 | 0.0005 | 2.992 | paper_live_ready_pending_human_review |
| US-AUTO-002 | balanced_pullback_cmf20_vol20_stability | 2.468 | 0.0015 | 0.0005 | 3.010 | paper_live_ready_pending_human_review |
| US-AUTO-003 | balanced_pullback_obv_vol20_stability | 2.426 | 0.0025 | 0.0005 | 2.871 | paper_live_ready_pending_human_review |
| US-AUTO-004 | balanced_pullback_obv_vol60_stability | 2.391 | 0.0015 | 0.0005 | 2.755 | paper_live_ready_pending_human_review |
| US-AUTO-005 | balanced_pullback_mfi14_vol20_stability | 2.387 | 0.0035 | 0.0005 | 2.786 | paper_live_ready_pending_human_review |

Exports:

- Strategy table: `reports/us/export/strategy_table_20260712.csv`
- Paper live pool: `reports/us/export/paper_live_pool_strategies_20260712.csv`
- Latest 2026-07-10 signal holdings: `reports/us/export/paper_live_pool_latest_signals_20260712.csv`
- Diversified pool view: `reports/us/export/paper_live_pool_diversified_20260712.csv`

After adding non-balanced families and rerunning rolling/null checks, the strategy table contains 16 automated-pass strategies. Pairwise rolling-return correlation still reaches 0.997 and latest-holdings Jaccard overlap reaches 1.0 among same-family variants, so the diversified paper-live view keeps three primary strategies and treats the rest as alternates:

| Primary ID | Family | Strategy | Rolling IR | Null p(IR) | Deflated IR z | Latest signal theme |
|---|---|---|---:|---:|---:|---|
| US-AUTO-001 | balanced | balanced_pullback_cmf10_vol60_stability | 2.547 | 0.0020 | 2.992 | pullback repair basket |
| US-AUTO-011 | pulltrend | pulltrend_ret5_ma20trend_ret20_parkinson_stability | 2.295 | 0.0030 | 2.700 | trend names after short pullback |
| US-AUTO-016 | qmv | qmv_ret20_pxma20_mfi7_skew_liq | 1.358 | 0.0145 | 2.098 | mega-cap tech / AI basket |
| US-AUTO-017 | microrev | overnight_gap_ret10_mfi14_vol20_liq | 1.348 | 0.0045 | 2.742 | 30-name gap/short-reversal basket |

Latest `US-AUTO-001` signal from 2026-07-10 close for next open execution:

| Rank | Symbol | Weight |
|---:|---|---:|
| 1 | RARE | 10% |
| 2 | FOUR | 10% |
| 3 | MRNA | 10% |
| 4 | CCC | 10% |
| 5 | BILL | 10% |
| 6 | ACHC | 10% |
| 7 | ELF | 10% |
| 8 | AXON | 10% |
| 9 | TECH | 10% |
| 10 | CERT | 10% |

Latest primary-strategy signal files include all four primary baskets in `reports/us/export/paper_live_pool_latest_signals_20260712.csv`.

## Model Portfolio

The paper-live model portfolio combines the four diversified primary strategies with equal strategy sleeves, aggregates duplicate symbols, and applies an 8% single-name cap. The 2026-07-12 export has 48 symbols, total target weight 100.0%, and largest single-name weight 5.0%, so no cap redistribution was needed.

Output:

- Model portfolio: `reports/us/export/paper_live_model_portfolio_20260712.csv`
- Manifest: `reports/us/export/paper_live_model_portfolio_20260712.manifest.json`

Top weights:

| Rank | Symbol | Target weight | Contributing strategies |
|---:|---|---:|---|
| 1 | MRNA | 5.00% | US-AUTO-001; US-AUTO-011 |
| 2 | RARE | 5.00% | US-AUTO-001; US-AUTO-011 |
| 3 | AAPL | 3.33% | US-AUTO-016; US-AUTO-017 |
| 4 | AMAT | 3.33% | US-AUTO-011; US-AUTO-017 |
| 5 | AMD | 3.33% | US-AUTO-016; US-AUTO-017 |

The model portfolio remains `paper_live_ready_pending_human_review` and `blocked_pending_pit_universe`; it is not an active trading monitor.

## Price And Survivorship Checks

Yahoo price cross-check passed for all 51 symbols in the latest primary/alternate signal set over 2026-07-01 to 2026-07-10. Output: `E:\quant-agent-team-us\research\2026-07-12-price-crosscheck-yahoo-final`.

Survivorship audit remains blocked: `us_index_membership.parquet` contains 2,629 rows, 1,019 symbols, and all rows are `current_snapshot`; there are no historical constituent intervals. Active monitoring remains blocked pending PIT universe remediation, even though the paper-live pool is populated.

## Dynamic Liquidity Recheck

As a survivorship-bias reduction step, the factory, rolling validation, and null/deflated checks now support `--universe-mode dynamic_liquidity`. This mode rebuilds the tradable universe from daily price and 20-day dollar-volume filters instead of treating the current index membership snapshot as a historical membership table. It is still not full PIT because the current price dataset may not contain delisted historical names.

Dynamic-liquidity rerun outputs:

- Factory: `E:\quant-agent-team-us\research\2026-07-12-factory-dynamic-liquidity`
- Rolling OOS: `E:\quant-agent-team-us\research\2026-07-12-rolling-dynamic-liquidity`
- Null/deflated: `E:\quant-agent-team-us\research\2026-07-12-null-dynamic-liquidity`
- Rolling top 20 export: `reports/us/export/dynamic_liquidity_rolling_top20_20260712.csv`
- Null top 10 export: `reports/us/export/dynamic_liquidity_null_top10_20260712.csv`

Dynamic-liquidity panel status: 814,599 rows, 985 symbols, 36 factors, `survivorship_reduced_not_pit`. The factory evaluated 2,160 rows and found 246 qualified candidates. Rolling OOS top strategy remained `balanced_ret_20d_ret_5d_px_to_ma20_cmf_10_vol_60d_turnover_stability_20d` with rolling excess +228.8%, rolling IR 2.547, average IR 3.058, MDD 9.9%, and win-excess 75%. The top 10 rolling candidates passed same-period random-basket null checks with p(IR) <= 0.005 and deflated IR z >= 2.63.

PIT support has been added at the script level through `--universe-mode pit`, `--pit-membership`, and `--pit-universes`. Required membership format is `symbol`, `universe_name`, `start_date`, `end_date`; optional fields are normalized to `membership_type`, `source`, and `as_of_date`.

## Top Live Holdings

For `US-BAL-001`, the live proxy basket selected from the 2026-06-30 signal was:

| Symbol | Live return after cost |
|---|---:|
| HON | -0.59% |
| NWL | -16.00% |
| VIRT | +4.15% |
| JEF | +3.96% |
| DUOL | +6.08% |
| WWD | -4.35% |
| BWXT | -4.15% |
| IBKR | +6.68% |
| LNC | +11.59% |
| MS | +6.17% |

Basket return was +1.35% after cost, benchmark equal-weight universe return was +0.46%, and live proxy excess was +0.89%.

## Review Notes

- These are candidate strategies, not approved monitoring strategies.
- The current universe is a current-snapshot universe; survivorship bias is still possible until historical constituents are added.
- Prices are Nasdaq historical OHLCV, with Yahoo chart API cross-check passed for the latest signal symbols over the live-proxy window.
- Dynamic liquidity recheck reduces current-index snapshot bias but does not replace a true PIT membership plus delisted-price database.
- The live proxy is short and should remain a gate, not a guarantee of future live profit.
- The paper live pool is not an active trading monitor until human review explicitly approves it.
- Next research loop should prioritize survivorship-bias remediation before active monitoring.
