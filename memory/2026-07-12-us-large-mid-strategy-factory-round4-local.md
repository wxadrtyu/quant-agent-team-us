# 2026-07-12 US large/mid strategy factory round 4

- stage: strategy-research
- kpi_version: us-daily-v1
- tags: project:quant-agent-team-us, market:us, freq:daily, strategy:factory-loop, status:candidate
- data: `E:\quant-agent-team-us\data\us\raw\2026-07-12`, price max date 2026-07-10
- output: `E:\quant-agent-team-us\research\2026-07-12-factory-round4`

## Result

The first 100-candidate round failed all live gates because the candidate generator filled the batch with momentum-heavy `qm` combinations. The 2026-06-30 to 2026-07-10 live proxy rewarded short-term pullback/oscillator/volume-price factors and punished intermediate momentum/trend factors.

After changing candidate generation to round-robin across templates, round 4 evaluated 720 hypotheses / 2,160 rows and found 297 qualified candidates. MDD was used as a soft penalty only, not a hard rejection. Live proxy gating is relative: absolute live return may be negative during a falling tape, but live excess return versus the equal-weight tradable universe must be positive.

Top candidate: `balanced_ret_20d_ret_5d_px_to_ma20_obv_change_20_vol_60d_turnover_stability_20d`, top_n 10, rebalance 20d. Dev excess +47.4%, dev IR 1.192, holdout excess +69.9%, holdout IR 2.660, live excess +0.89%.

Rolling validation on top 20 round4 candidates recomputed factor weights monthly using only the prior two years. Rolling champion became `balanced_ret_20d_ret_5d_px_to_ma20_cmf_10_vol_60d_turnover_stability_20d`: rolling excess +228.8%, rolling IR 2.547, rolling average IR 3.058, rolling MDD 9.9%, win excess 75%. Its fixed factory live excess was +0.38%.

Null/overfit check on the top 10 rolling candidates used 2,000 random same-period same-top_n baskets per strategy. All 10 passed automated gates (`pvalue_ir <= 0.05`, `pvalue_excess <= 0.05`, `deflated_ir_z >= 2`, positive factory live excess). They were exported to `reports/us/export/strategy_table_20260712.csv` and `reports/us/export/paper_live_pool_strategies_20260712.csv`; latest signal holdings were exported to `reports/us/export/paper_live_pool_latest_signals_20260712.csv`. Status remains `paper_live_ready_pending_human_review` because active monitoring requires human review.

Diversification check showed the 10 paper-live strategies are same-family variants, not independent strategies: pairwise rolling-return correlation reached 0.997 and latest-holdings Jaccard overlap reached 1.0. The diversified paper-live pool keeps only `US-AUTO-001` as primary and treats the other nine as alternates. Latest 2026-07-10 signal for `US-AUTO-001`: RARE, FOUR, MRNA, CCC, BILL, ACHC, ELF, AXON, TECH, CERT.

A follow-up family-diversity pass tested top non-balanced candidates from pulltrend, mr, qmv, and defensive families. Seven non-balanced strategies passed null/deflated checks; after appending them to the strategy table, there are 16 automated-pass strategies. Diversified paper-live primaries are now: `US-AUTO-001` balanced (`rolling_ir=2.547`), `US-AUTO-011` pulltrend (`rolling_ir=2.295`), and `US-AUTO-016` qmv (`rolling_ir=1.358`). Latest 2026-07-10 primary signals: US-AUTO-001 = RARE, FOUR, MRNA, CCC, BILL, ACHC, ELF, AXON, TECH, CERT; US-AUTO-011 = MRNA, ALAB, PANW, RARE, OKTA, AAL, DELL, AMAT, W, HOOD; US-AUTO-016 = NVDA, AAPL, TSLA, AMD, MSFT, AMZN, META, MRVL, GOOGL, AVGO.

Second-source price cross-check was implemented with Yahoo chart API after Stooq returned missing data for the 2026-07 window. Final Yahoo cross-check passed for all 51 unique latest signal symbols over 2026-07-01..2026-07-10. Survivorship audit found `us_index_membership.parquet` has 2,629 rows / 1,019 symbols / 4 universes, all `current_snapshot`, so active monitoring remains blocked pending PIT universe remediation. Round5 added microstructure factors (`overnight_gap_1d`, `intraday_ret_1d`, `close_pos_20d`, `range_pct_5d`) and found a low-correlation microrev primary: `US-AUTO-017` (`rolling_ir=1.348`, `deflated_ir_z=2.742`, `rolling_mdd=11.7%`). Strategy table now has 17 automated-pass strategies and 4 diversified primaries.

Paper-live model portfolio export `reports/us/export/paper_live_model_portfolio_20260712.csv` combines the four diversified primaries with equal sleeves, aggregates duplicate symbols, and applies an 8% single-name cap. The current portfolio has 48 symbols, total target weight 100.0%, and largest single-name weight 5.0%; status remains `paper_live_ready_pending_human_review` and `blocked_pending_pit_universe`.

Dynamic-liquidity universe support was added through `scripts/us_universe.py` and `--universe-mode dynamic_liquidity|pit` on the factory, rolling, and null-check scripts. PIT mode expects `symbol`, `universe_name`, `start_date`, and `end_date` and filters each signal date by active intervals. Dynamic-liquidity mode rebuilds daily membership from price >= 5 and 20-day dollar volume >= 10M, and is labeled `survivorship_reduced_not_pit`.

Dynamic-liquidity rerun output: `E:\quant-agent-team-us\research\2026-07-12-factory-dynamic-liquidity`, `E:\quant-agent-team-us\research\2026-07-12-rolling-dynamic-liquidity`, and `E:\quant-agent-team-us\research\2026-07-12-null-dynamic-liquidity`. The panel had 814,599 rows / 985 symbols / 36 factors; the factory evaluated 2,160 rows and found 246 qualified candidates. Rolling OOS top strategy stayed `balanced_ret_20d_ret_5d_px_to_ma20_cmf_10_vol_60d_turnover_stability_20d` with rolling excess +228.8%, rolling IR 2.547, avg IR 3.058, MDD 9.9%, and win-excess 75%. Top 10 same-period random-basket null checks passed with p(IR) <= 0.005 and deflated IR z >= 2.63.

## Next Step

Acquire true PIT membership plus delisted-price coverage before active monitoring. Until then, use dynamic-liquidity results as a bias-reduced research cross-check, not production PIT evidence. Keep paper-live candidates pending human review until explicitly approved.
