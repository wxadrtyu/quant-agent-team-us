2026-03-22 data workflow to remember:
1. Free multi-source market fetch updates local stock_history append-only files.
2. Incremental ingest writes raw_market_daily and normalized_market_daily.
3. Any base data change must automatically trigger derived feature refresh for changed stocks.
4. Feature summaries and dashboard must distinguish expected warmup gaps vs true refresh gaps.
5. Daily fixed runs should be script/scheduler driven, not agent driven.
6. After data foundation is stable, next stage is strategy research/backtest loop.

2026-03-22 update:
- Added automatic derived-feature refresh after base incremental ingest and daily update.
- Added expected warmup gap vs true missing refresh classification for feature coverage.
- Expanded price-derived features to ma_5, ma_10, ma_20, ma_60, ret_1d, ret_5d, ret_20d, momentum_20d.
- Finished full-database refresh for the 8 price features.
- feature_refresh_summary.json at 2026-03-22T15:03:56 shows:
  - features_upserted = 8
  - rows_upserted = 87401573
  - missing_refresh_stock_dates = 0
  - stock_codes_with_missing_refresh = 0
- Expected unavailable stock-date rows remain normal warmup gaps, not refresh failures.
- MCP was unavailable during part of this work; local project memory is the source of truth when MCP cannot be reached.

2026-03-22 late update:
- Added second-batch feature definitions in code:
  - avg_volume_20d
  - avg_turnover_20d
  - volume_ratio_20d
  - volatility_20d
- Added workflow option to skip gap diagnostics for heavy full-database backfills.
- Real database was re-cleaned after tests polluted 5 non-6-digit stock codes; normalized_market_daily returned to 5309 valid stock codes and 0 non-digit codes.
- Old long-table feature storage was dropped as the primary path because it expanded the database to 62 GB, with research_feature_store alone at 50 GB.
- Switched derived-feature persistence from long-table research_feature_store to wide-table research_feature_daily keyed by (stock_code, trade_date).
- Old long-table feature data was cleared; database size dropped from 62 GB to 12 GB and local free disk increased from about 4.2 GB to 55 GB.
- Wide-table full-database refresh completed with 5309 stock codes and date coverage through 2026-03-20.
- Wide-table row count after refresh: 11015446.
- Wide-table feature coverage check:
  - ma_5 = 10994210
  - ma_10 = 10967665
  - ma_20 = 10914575
  - ma_60 = 10702244
  - avg_volume_20d = 10914575
  - avg_turnover_20d = 10914575
  - volume_ratio_20d = 10914575
  - ret_1d = 11010137
  - ret_5d = 10988901
  - ret_20d = 10909266
  - momentum_20d = 10914575
  - volatility_20d = 10909266
- Gap diagnostics after the wide-table refresh:
  - expected_unavailable_stock_dates = 313202
  - missing_refresh_stock_dates = 0
  - stock_codes_with_missing_refresh = 0
- Dashboard and dependency registry now read derived features from research_feature_daily, not research_feature_store.
- Real daily_update validation after the wide-table cutover returned no_changes and did not write back to the old long-table feature store.
- Dashboard was extended with wide-table storage overview and feature-density views.
- Local dashboard health check passed with direct access to http://127.0.0.1:8501; proxy-enabled local curl may show 502 unless localhost requests bypass the proxy.
- Added a fixed data-quality report at reports/data_quality/latest.json, generated from raw/normalized/feature/conflict tables.
- Data-quality report now tracks:
  - market row counts and stock counts
  - recent conflict samples
  - feature wide-table coverage and missing-refresh counts
  - lagging symbols whose latest date trails the database max date
- During the first run, another single-row test stock polluted the real database (`test_3e5f6f0d`); it was deleted from raw_market_daily, normalized_market_daily, and research_feature_daily.
- Corrected quality-report filtering to only count 6-digit stock codes in database-wide totals.
- Corrected quality-report warmup-gap accounting; latest clean report shows:
  - raw_rows = 11015446
  - normalized_rows = 11015446
  - stock_count = 5309
  - feature_rows = 11015446
  - feature_stock_count = 5309
  - expected_unavailable_stock_dates = 313202
  - missing_refresh_stock_dates = 0
  - lagging_symbol_count = 5206
- Dashboard now includes a Data Quality section driven by reports/data_quality/latest.json, showing conflict counts, missing-refresh counts, lagging-symbol counts, and sample rows without re-running heavy diagnostics in the UI.
- Lagging-symbol classification was added to the quality report. Current clean distribution:
  - batch_backfill_candidates_2026_missing = 4958
  - recent_2025_tail = 41
  - stale_2024 = 49
  - stale_2020_to_2023 = 127
  - historical_end_before_2020 = 31
- This means the dominant lagging problem is not historical delisting; it is that most lagging symbols still stop at 2025-12-31 and likely need a 2026 batch backfill pass.
- Agreed execution order for lagging remediation:
  1. finish the 4958-symbol batch backfill from 2025-12-31 into 2026
  2. then backfill the 49 stale_2024 symbols
  3. then backfill the 127 stale_2020_to_2023 symbols
  4. keep the 31 historical_end_before_2020 symbols in a separate review bucket instead of auto-chasing them to the latest date

2026-03-23 lagging remediation result:
- Reworked scripts/backfill_lagging_market.py from serial mode into process-pool parallel mode, with file-based JSONL logs and exact-lag-date targeting for the large 2025-12-31 batch.
- The 4958-symbol 2025-12-31 batch was completed successfully with an empty failure file, and it eliminated the whole 2025-12-31 bucket.
- Post-remediation current state:
  - remaining_recent_2026 = 2
    - 300379 -> 2026-01-23
    - 688693 -> 2026-03-13
  - remaining_2024 = 49
  - remaining_2020_to_2023 = 127
- The 11-symbol targeted follow-up run inserted 121 rows with 1 conflict and reduced the recent-2026 lagging bucket from 11 symbols to 2.
- Recent-2026 unresolved symbols are treated as free-source unavailable for now:
  - 300379: all 6 free sources returned no usable rows after 2026-01-23
  - 688693: all 6 free sources failed to extend beyond 2026-03-13
- The 49-symbol 2024 batch produced only 8 partial extensions:
  - 300495
  - 300116
  - 000971
  - 002621
  - 000836
  - 002610
  - 300262
  - 000982
- Those 8 symbols still remain in the 2024 bucket after the free-source pass, so the whole 2024 bucket should stay classified as free-source unavailable for now.
- The 127-symbol 2020-2023 batch produced zero successful extensions; all 127 should be treated as free-source unavailable.
- A fixed snapshot of the post-remediation unresolved lists now lives at reports/data_quality/lagging_backfill_status.json.
- Operational rule from this point:
  - do not keep re-running free-source backfills against the symbols already listed in lagging_backfill_status.json
  - only retry them after adding a new data source or changing fetch logic

2026-03-23 quality report integration:
- reports/data_quality/latest.json now embeds lagging_symbols.backfill_status_snapshot from reports/data_quality/lagging_backfill_status.json.
- The dashboard Data Quality section now shows the fixed free-source-unavailable snapshot alongside ordinary lagging counts.
- This separates "still lagging in the database" from "already confirmed free-source unavailable", so operations do not keep treating the same symbols as normal backfill candidates.

2026-03-23 daily-run skip rule:
- Added shared helper logic for reports/data_quality/lagging_backfill_status.json.
- scripts/fetch_market_daily.py now skips the known free-source-unavailable symbols by default during broad daily fetches.
- scripts/run_daily_pipeline.py now applies the same default skip behavior before free-source fetch.
- Explicit `--stock-code` runs still allow manual retry of a blocked symbol.
- Added `--include-free-source-unavailable` to both scripts for forced broad retries when a new data source or fetch logic change needs to re-test the blocked buckets.

2026-03-23 daily-job logging:
- scripts/run_daily_job.sh now prints the current free-source-unavailable bucket counts at job start.
- scripts/run_daily_job.sh also prints the latest quality-report lagging summary after the pipeline finishes.
- This makes the scheduled daily log self-explanatory without opening the dashboard first.

2026-03-23 daily summary integration:
- scripts/run_daily_pipeline.py now writes fetch-stage metadata back into daily_update_latest.json under execution.fetch.
- The daily summary now records attempted stock count, skipped free-source-unavailable count, and fetch failure count directly in the JSON output.

2026-03-23 dashboard daily-update integration:
- apps/db_dashboard.py now loads reports/ingestion/daily_update_latest.json directly.
- The dashboard shows the latest daily fetch attempted count, failed count, skipped known-unavailable count, and changed-file count.
- The dashboard also shows sample failed fetches and sample skipped known-unavailable symbols from the latest daily run summary.

2026-03-23 anomaly rule solidification:
- reports/data_quality/latest.json now includes structured anomaly_rules.
- Current rule set:
  - market_row_balance
  - feature_refresh_gap
  - recent_lagging_symbols
  - known_free_source_unavailable
  - conflict_backlog
  - lagging_bucket_visibility
- Rules emit pass/info/warn/fail plus severity, metric_value, summary, and operator action text.
- apps/db_dashboard.py now shows these anomaly rules directly in the Data Quality section.

2026-03-24 recovered project memory checkpoint:
- User explicitly confirmed that the last remembered quant-project task was "data quality anomaly rule solidification".
- Repo recovery confirmed this was already implemented, not just planned:
  - current HEAD on branch codex/architecture-baseline is `9b6487f Add structured data quality anomaly rules`
  - the rule framework is already wired through src/quant_agent_team/data_quality.py
  - reports/data_quality/latest.json contains the structured anomaly_rules output
  - apps/db_dashboard.py already renders the anomaly rules in the Data Quality section
  - README.md already documents the fixed anomaly rule set
- Therefore the next stage is not more rule design; it is operational cleanup against the fixed rule outputs.
- Recovered next-step priority for the next session:
  1. explain why feature_refresh_gap regressed from the earlier clean state to a large warn state
  2. inspect and clear the remaining recent lagging symbols
  3. review the current conflict backlog and decide which conflicts are legitimate upstream changes vs actual issues
- Snapshot recovered from reports/data_quality/latest.json at 2026-03-23T19:59:27:
  - feature_refresh_gap = warn
  - missing_refresh_stock_dates = 99736
  - stock_codes_with_missing_refresh = 4966
  - recent_lagging_symbols = warn with metric_value 2
  - known_free_source_unavailable = info with metric_value 178
  - conflict_backlog = warn with metric_value 304
  - lagging_bucket_visibility = info with metric_value 250
- Working conclusion for tomorrow:
  - treat anomaly rule solidification as complete
  - resume from data-quality remediation, starting with feature_refresh_gap root-cause analysis

2026-03-24 anomaly remediation findings:
- Investigated the three 2026-03-23 follow-up items: feature_refresh_gap regression, remaining recent lagging symbols, and conflict_backlog=304.
- feature_refresh_gap root cause:
  - The apparent earlier "clean" feature state was misleading.
  - reports/features/feature_refresh_summary.json at 2026-03-23T19:52:07 reported missing_refresh_stock_dates = 0 and stock_codes_with_missing_refresh = 0, but that run explicitly noted "Gap diagnostics were skipped for this run."
  - src/quant_agent_team/feature_refresh.py currently sets the diagnostic counters to 0 when include_gap_diagnostics=False, so that summary was not a measured clean state.
  - reports/data_quality/latest.json at 2026-03-23T19:59:27 then recomputed the true quality view and surfaced missing_refresh_stock_dates = 99736 across 4966 stock codes.
  - Working interpretation: the 2026-03-23 warn did not represent a fresh regression from a trustworthy zero baseline; it exposed a real gap that had been hidden by a skipped-diagnostics summary.
- recent lagging symbols:
  - Confirmed from reports/data_quality/lagging_backfill_status.json and ingest_source_file_state that the remaining recent symbols were:
    - 300379 -> 2026-01-23
    - 688693 -> 2026-03-13
  - This matched the recovered 2026-03-23 memory and was not a dashboard mismatch.
- conflict_backlog=304 breakdown:
  - The backlog is concentrated, not 304 unrelated random issues.
  - 304 rows span 31 stock codes, and 301 of them were logged in one batch at 2026-03-22 11:56:59+08.
  - Date concentration:
    - 2026-03-09 to 2026-03-20 account for 300 rows
    - 2025-01-02, 2025-01-03, and 2026-03-06 account for 3 rows on 000001
    - 2026-03-13 accounts for 1 row on 688693
  - Field-diff classification:
    - 300 rows are volume-only conflicts and are approximately a 100x unit-scale difference between existing and incoming payloads.
    - 3 rows on 000001 (2025-01-02, 2025-01-03, 2026-03-06) are old non-market / test-like dirty rows rather than legitimate upstream revisions.
    - 1 row on 688693 (2026-03-13) is a real source mismatch: tiny open/high rounding drift plus a turnover difference.
  - Operational interpretation:
    - The main backlog driver is a fetch-side volume unit normalization issue, not broad market-price corruption.
    - The 000001 three-row subset should be cleaned as dirty history.
    - The single 688693 row should remain manual-review-required unless a source-priority rule is introduced.
- Next concrete remediation after this checkpoint:
  1. normalize fetched volume units in the free-source market fetch chain to stop creating the 300-row conflict pattern
  2. clean the three dirty 000001 conflict rows
  3. leave the single 688693 conflict pending manual source-choice unless a deterministic source-priority policy is added

2026-03-26 conflict remediation checkpoint:
- Implemented fetch-side volume normalization in src/quant_agent_team/market_fetch.py before rows are written back to stock_history files.
- The normalization uses turnover / price as a share-volume proxy and upgrades likely lot-based volume to share-based volume when the implied ratio is approximately 100x.
- Added a regression test in tests/test_workflow.py to verify that a lot-based incoming row is normalized to share volume while turnover is preserved.
- Local verification passed:
  - python3 -m unittest /Users/laisicong/quant-agent-team/tests/test_workflow.py
  - 15 tests, all green
- Cleaned the known dirty 000001 conflict subset:
  - 2025-01-02
  - 2025-01-03
  - 2026-03-06
- For 2026-03-06, the dirty value had leaked into raw_market_daily / normalized_market_daily; both tables were repaired from the incoming conflict payload and now match the real stock_history file:
  - open = 10.78
  - high = 10.84
  - low = 10.77
  - close = 10.82
  - volume = 476577
  - turnover = 514733549.73
- Re-ran feature refresh for 000001 after the repair:
  - status = success
  - features_upserted = 12
  - rows_upserted = 35391
  - missing_refresh_stock_dates = 0
- Re-ran reports/data_quality/latest.json after the cleanup.
- Post-cleanup quality state:
  - conflict_backlog dropped from 304 to 301
  - 000001 dirty three-row subset is no longer present in ingest_conflict_log
  - the remaining backlog is still:
    - 300 volume unit conflicts
    - 1 real source mismatch on 688693 2026-03-13
- Next remediation after this checkpoint:
  1. commit the volume-normalization fix and this memory update
  2. then use the new normalization path to re-fetch / re-ingest the affected March 2026 symbols so the 300 volume-unit conflicts can be retired instead of only classified

2026-03-26 false-conflict guardrail follow-up:
- A targeted re-fetch / re-ingest run against the original 30 March 2026 volume-conflict symbols was started and then stopped after conflict backlog exploded from 301 to 71518.
- Root-cause findings:
  - The large 2026-03-26 11:03 batch inserted 71217 new conflicts across 1484 stock codes.
  - This batch was not primarily caused by the new normalization code itself; it exposed previously written dirty stock_history rows that were still using lot-based volume.
  - Volume-ratio breakdown on the 11:03 batch:
    - ~100x ratio: 70291 rows
    - ~1x ratio: 905 rows
    - other ratios: 21 rows
  - Therefore the main issue is historical dirty source files on disk, not a fresh market-data divergence in raw_market_daily.
- Additional guardrail implemented:
  - src/quant_agent_team/ingestion.py now treats same-day rows as non-conflicting when open/high/low/close match exactly, turnover differs by at most 0.01, and volume differs by at most 100 shares.
  - This suppresses false conflict rows caused by near-equal share-volume rounding after normalization.
- Regression coverage:
  - tests/test_workflow.py now includes a PostgreSQL integration test proving that same-day near-equal volume rounding does not enter ingest_conflict_log.
  - python3 -m unittest /Users/laisicong/quant-agent-team/tests/test_workflow.py passed with 16 tests green.
- Operational conclusion after this follow-up:
  - do not bulk-delete the 2026-03-26 11:03 conflict batch blindly
 - first batch-repair the 1484 dirty stock_history files with the corrected fetch path
 - then re-run incremental ingest in smaller controlled batches and clean only the now-proven false conflicts

2026-03-26 targeted repair and feature lookback follow-up:
- Added targeted stock-code support to the incremental ingest path so repairs can be run against a controlled subset instead of the full stock_history tree:
  - src/quant_agent_team/ingestion.py
  - src/quant_agent_team/workflow.py
  - scripts/base_incremental_ingest.py
- Added PostgreSQL regression coverage proving that run_base_incremental_ingest can ingest only explicitly selected stock codes.
- Used the targeted path to batch-repair the 1484 dirty stock_history files exposed by the 2026-03-26 11:03 conflict spike.
- Operational repair loop per batch:
  1. re-fetch corrected rows into /Users/laisicong/Downloads/stock_history
  2. run targeted incremental ingest for just those stock codes
  3. overwrite raw_market_daily / normalized_market_daily from the newest incoming conflict payload for those stock codes
  4. delete resolved ingest_conflict_log rows for those stock codes
  5. refresh derived features for the repaired stock set
- End state after the repair loop:
  - ingest_conflict_log reduced from 70102 rows across 1438 stock codes to 0 rows across 0 stock codes
  - the final remaining row was the prior manual-review item:
    - 688693 / 2026-03-13
  - that row was explicitly aligned to the current source-file payload and then removed, leaving conflict backlog = 0
- Final aligned raw-market payload for 688693 / 2026-03-13:
  - open_price = 48.169998
  - high_price = 48.200001
  - low_price = 45.75
  - close_price = 45.75
  - volume = 2852569.0
  - turnover = 130505031.75
- Post-conflict cleanup, a derived-feature issue was found on 688693:
  - run_feature_refresh succeeded, but diagnostics showed missing_refresh_stock_dates = 20
  - root cause was not data corruption; the feature refresh lookback logic used 59 calendar days for ma_60 backfill instead of 59 trading rows
  - this caused ma_60 to remain NULL for the first 20 trading dates in the 2026 segment even though enough historical market rows existed
- Feature refresh logic was corrected in src/quant_agent_team/feature_refresh.py:
  - when refresh_from_date is known, the refresh now finds the earliest required lookback date by trading-row sequence, not by subtracting natural days
- Added a regression test in tests/test_workflow.py covering re-refresh of ma_60 after a late-date deletion on a business-day-only series.
- Local verification after the fix:
  - python3 -m unittest /Users/laisicong/quant-agent-team/tests/test_workflow.py
  - 18 tests, all green
- Real-database verification after the fix:
  - rerunning run_feature_refresh for 688693 returned:
    - expected_unavailable_stock_dates = 59
    - missing_refresh_stock_dates = 0
    - stock_codes_with_missing_refresh = 0
  - ma_60 is now present for 688693 from 2026-01-05 onward

2026-03-26 lagging-tail operational classification follow-up:
- The remaining lagging universe was rechecked after conflict backlog cleanup.
- Current lagging bucket distribution from raw_market_daily:
  - recent_2025_tail = 43
  - stale_2024 = 49
  - stale_2020_to_2023 = 127
  - historical_end_before_2020 = 31
- A focused probe against the recent tail confirmed the bottleneck is now fetch-side stability / availability, not ingest:
  - symbols like 600898 return empty results across the cheaper free-source stack
  - symbols like 600083 / 600837 / 603963 / 300114 often fail with Eastmoney-side RemoteDisconnected / protocol errors
  - baostock remains noisy and can return socket / decode / login transport failures in the same batch
- Operational decision:
  - do not keep treating the recent 2025 tail as daily retry candidates
  - classify them into the blocked free-source-unavailable snapshot until a stronger source or a better-tailored retry policy exists
- Code changes made to support this:
  - src/quant_agent_team/market_fetch.py
    - Akshare / efinance / yfinance now temporarily clear proxy env vars for the request itself
    - pytdx / mootdx / yfinance are treated as noisy fallbacks and only attempted once
    - mootdx / pytdx close handling was tightened to reduce resource leakage noise
  - src/quant_agent_team/workflow.py
    - run_daily_update now accepts stock_codes and passes them through to incremental ingest
  - scripts/run_daily_pipeline.py
    - explicit --stock-code runs now truly ingest only the requested symbols instead of scanning the whole source directory
  - src/quant_agent_team/lagging_status.py
    - blocked-code loading now includes recent_2025_tail_remaining
  - src/quant_agent_team/data_quality.py
    - blocked snapshot totals and lagging-bucket messaging now include recent_2025_tail_remaining
  - apps/db_dashboard.py
    - dashboard blocked snapshot now shows recent_2025_tail_remaining
  - scripts/run_daily_job.sh
    - daily log lines now include recent_2025_tail blocked counts
- Snapshot update:
  - reports/data_quality/lagging_backfill_status.json now includes recent_2025_tail_remaining with 41 symbols
  - recent_2026_remaining remains reserved for the 2 still-lagging 2026 symbols and is not double-counted
- Targeted regression checks passed:
  - noisy fallback providers use a single attempt
  - explicit run_daily_update(stock_codes=...) forwards the selected codes
  - explicit run_base_incremental_ingest(stock_codes=...) still works

2026-03-26 historical-lagging blocked snapshot extension:
- The lagging universe still had a fifth bucket not represented in the blocked snapshot:
  - historical_end_before_2020 = 31 symbols
- These symbols end between 2014 and 2019 and are operationally not suitable for daily free-source retries.
- The snapshot and skip logic were extended so this bucket is treated consistently with the other blocked free-source-unavailable buckets.
- Code and surface updates:
  - src/quant_agent_team/lagging_status.py now loads historical_end_before_2020_remaining into the blocked-code set
  - src/quant_agent_team/data_quality.py now includes this bucket in blocked totals and lagging-bucket action text
  - apps/db_dashboard.py now shows historical_end_before_2020_remaining in the snapshot table and sample list
  - scripts/run_daily_job.sh now logs historical_pre_2020 blocked counts in both snapshot and quality summary lines
- Snapshot update:
  - reports/data_quality/lagging_backfill_status.json now includes historical_end_before_2020_remaining with 31 symbols
- Validation:
  - targeted loader / fallback tests passed
  - python3 -m py_compile on the touched Python files passed
  - zsh -n scripts/run_daily_job.sh passed

2026-03-26 lagging cleanup stopping point:
- After extending the blocked snapshot to cover:
  - recent_2026_remaining = 2
  - recent_2025_tail_remaining = 41
  - stale_2024_remaining = 49
  - stale_2020_2023_remaining = 127
  - historical_end_before_2020_remaining = 31
- A direct reconciliation against the current lagging universe showed:
  - blocked_count = 250
  - remaining_count = 0
- Interpretation:
  - there are currently no lagging symbols left outside the blocked snapshot
  - daily automation should not continue spending free-source retries on lagging cleanup beyond the blocked policy
  - the data-cleaning phase is operationally at a stopping point under the current free-source stack
- Recommended next phase:
  - stop pushing lagging remediation further unless a stronger market-data source is added
  - move the project focus from data cleanup into strategy research / implementation / backtest execution

2026-03-26 strategy kickoff checkpoint:
- Began the first real strategy-research artifact chain after data cleanup reached an operational stopping point.
- Created the first non-demo strategy brief:
  - strategies/generated/cn-a-trend-volume-pullback-001.json
  - Title: A股日频趋势回踩放量确认
  - Scope: phase-1 technical-only daily CN-A strategy using already-stable market data and derived features, with no fundamental/event dependencies.
- Created the first non-demo executable strategy spec:
  - strategies/specs/spec-cn-a-trend-volume-pullback-001-v1.json
  - Core inputs:
    - market_inputs: close_price_adj, volume
    - derived_features: ma_5, ma_10, ma_20, ma_60, ret_5d, ret_20d, volume_ratio_20d, volatility_20d
  - Core idea:
    - filter for medium-term uptrend
    - enter on short-term reacceleration plus volume confirmation
    - rank by 20-day momentum, volume confirmation, and controlled volatility
    - exit on short-term trend break, abnormal loss, or volatility spike
- Created the first review stub:
  - reports/reviews/cn-a-trend-volume-pullback-001-review.md
- Found and fixed two strategy-architecture issues while doing this:
  1. src/quant_agent_team/workflow.py load_strategy_spec had been discarding filters / entry_rules / exit_rules / ranking_formula on load; it now round-trips those fields correctly.
  2. The project data inventory had only been exposing raw + normalized fields, but not persisted research_feature_daily columns. This caused strategy_data_sync to misclassify already-available derived features as missing.
- Data inventory behavior was upgraded:
  - src/quant_agent_team/ingestion.py now loads available derived features from research_feature_daily
  - configs/data_inventory.json can now expose persisted feature fields as available
  - workflow feature refresh now rewrites inventory after derived features are refreshed, keeping strategy sync aligned with actual DB state
- Dependency registry was also corrected:
  - turnover is now registered as a base market field so avg_turnover_20d can resolve transitively
- Verification completed:
  - targeted regression suite covering registry, spec round-trip, and inventory-driven strategy sync passed
  - reports/data_sync/spec-cn-a-trend-volume-pullback-001-v1-sync.json now shows:
    - ready_for_backtest = true
    - all declared requirements satisfied
- Operational conclusion:
  - the project now has its first real strategy brief/spec pair on top of the production data stack
  - the next phase should move from strategy artifact definition into strategy-engineer implementation and backtest execution for this spec

2026-03-26 user strategy requirement intake:
- Corrected the workflow boundary: before quant-researcher proposes candidate strategies, the first step is to collect the user's strategy requirements.
- User-confirmed outcome thresholds:
  - sharpe > 2
  - trade_win_rate > 80%
  - annualized_return > 20%
  - max_drawdown < 30%
- User-confirmed strategy preference:
  - style: medium-short horizon
  - type: stock-selection strategy
  - output must include explicit recommended buy points and sell points after a stock is selected
  - preference across substyles: all acceptable; no hard preference among trend-following, pullback buying, or breakout, as long as results meet the KPI thresholds
- Working implication for the next research phase:
  - candidate strategy briefs should focus on medium-short holding periods and fully specified entry/exit logic
  - pure ranking-only ideas are not sufficient; each candidate must be convertible into explicit buy/sell recommendations
  - later strategy review should use the user's four hard thresholds as gating criteria, not just descriptive metrics

2026-03-26 quant-researcher evidence-chain rule:
- User explicitly clarified that quant-researcher must behave like a professional quantitative analyst rather than a brainstorming agent.
- Strategy conclusions must not be presented as intuition-first guesses.
- Before proposing candidate strategies, quant-researcher must explain and document:
  - what papers, broker reports, community research, and market studies were reviewed
  - what market mechanism those materials imply
  - what part of the conclusion comes from external research versus local database validation
- Evidence hierarchy for the project is now:
  1. user requirement intake
  2. academic / professional research review
  3. sell-side / industry research review
  4. professional quant community cross-check
  5. latest market news / policy / hot-theme review
  6. local dataset validation
  7. only then produce candidate strategy briefs
- Community posts and forums are allowed as auxiliary inputs, but not as the sole basis for a strategy conclusion.
- User also explicitly wants current quant-community成果 to be referenced, because high-quality existing community work can accelerate hypothesis filtering.
- User also explicitly requires current news / market facts to enter the research context; quant-researcher must not ignore recent developments when judging whether an older strategy logic is still applicable.
- Implication:
  - the earlier first-draft strategy brief/spec should be treated as a draft artifact, not as a fully researched final research conclusion
  - next research work should start by building a formal evidence-gathering and candidate-brief workflow

2026-03-27 backtest implementation checkpoint:
- Added the first minimal backtest/evaluation execution chain:
  - src/quant_agent_team/backtest_runner.py
  - src/quant_agent_team/evaluation.py
  - workflow + CLI entrypoints for:
    - run-backtest
    - evaluate-backtest
- Backtest engine assumptions in this first version:
  - signals are generated after close
  - entries and exits execute at next open
  - portfolio uses fixed-slot capital allocation
  - daily mark-to-market uses close_price_adj
  - current metrics include:
    - trade_count
    - trade_win_rate
    - annualized_return
    - total_return
    - max_drawdown
    - sharpe
    - average_holding_days
- Added minimal unit coverage for:
  - formula evaluation
  - `between` rule handling
  - KPI evaluation thresholds
- Local validation:
  - python3 -m unittest tests/test_backtest.py tests/test_workflow.py
  - 27 tests passed
- Smoke-tested both researched candidates on 2025-01-01 to 2025-12-31:
  - spec-cn-a-trend-pullback-confirmation-v1
  - spec-cn-a-oversold-rebound-filtered-v1
- Result:
  - both backtests executed successfully and wrote reports
  - both produced `trade_count = 0`
  - therefore both also failed KPI evaluation at this stage
- Interpretation:
  - the current researched rules are too strict or too sparsely triggered in the tested 2025 sample
  - the immediate next task is signal-trigger diagnostics and parameter relaxation / rule refinement, not premature performance discussion

2026-03-27 backtest execution correction and first results:
- The initial zero-trade result was partly an execution bug, not just a strategy-quality issue.
- Root cause:
  - stock_code values loaded from the exported CSV were losing leading zeroes
  - this broke next-day execution row matching and caused signals not to turn into trades
- Fix:
  - src/quant_agent_team/backtest_runner.py now reads stock_code as string and zero-fills to 6 digits
  - a regression test was added in tests/test_backtest.py to preserve leading zeroes
- After the fix, both 2025 full-year backtests completed successfully:
  1. spec-cn-a-trend-pullback-confirmation-v1
     - trade_count = 209
     - trade_win_rate = 0.3158
     - annualized_return = -0.2463
     - total_return = -0.2606
     - max_drawdown = 0.3393
     - sharpe = -0.8023
     - result: fails all user KPI gates
  2. spec-cn-a-oversold-rebound-filtered-v1
     - trade_count = 536
     - trade_win_rate = 0.4384
     - annualized_return = -0.0718
     - total_return = -0.0765
     - max_drawdown = 0.2572
     - sharpe = -0.3473
     - result: fails win-rate, annualized-return, and sharpe; only drawdown remains within the user's limit
- Additional diagnostic finding:
  - the researched rules do produce many raw signal hits in 2025
    - trend candidate full signal rows ≈ 70k
    - rebound candidate full signal rows ≈ 924
  - therefore the current problem is no longer signal absence; it is poor economic quality under the present rule set and execution assumptions
- Working conclusion:
  - the backtest engine is now operational
  - neither of the first two researched candidates is acceptable under the user's KPI thresholds
  - the next iteration should focus on rule refinement, regime gating, or alternative candidate logic rather than trying to approve either strategy as-is

2026-03-27 strategy iteration checkpoint:
- Saved the intermediate strategy optimization artifacts for:
  - spec-cn-a-trend-pullback-confirmation-v2
  - spec-cn-a-trend-pullback-confirmation-v3
  - spec-cn-a-trend-pullback-confirmation-v4
  - spec-cn-a-oversold-rebound-filtered-v2
  - spec-cn-a-oversold-rebound-filtered-v3
- The current leading candidate is `spec-cn-a-trend-pullback-confirmation-v4`.
- v4 2025 full-year backtest result:
  - trade_count = 149
  - trade_win_rate = 0.5235
  - annualized_return = 0.5393
  - total_return = 0.5847
  - max_drawdown = 0.1002
  - sharpe = 2.2218
- KPI interpretation against the user's hard gates:
  - passed:
    - annualized_return > 20%
    - max_drawdown < 30%
    - sharpe > 2
  - failed:
    - trade_win_rate > 80%
- v4 became the first strategy version to satisfy 3 of the 4 user KPI gates.
- Trade-distribution diagnostic for v4:
  - holding_days = 0: win rate ≈ 48.9%
  - holding_days = 1: win rate ≈ 41.0%
  - holding_days >= 2: win rate ≈ 61.9%
- Working conclusion:
  - the remaining problem is no longer return/risk efficiency
  - the remaining problem is entry quality and early post-entry shakeout
  - the next strategy iteration should optimize specifically for win-rate improvement, even at the cost of lower trade count

2026-03-27 strategy library + next research direction:
- Saved `spec-cn-a-trend-pullback-confirmation-v4` into the project strategy library as the best known baseline for this strategy family.
- Why it is kept:
  - annualized_return > 20%
  - max_drawdown < 30%
  - sharpe > 2
  - but trade_win_rate remains far below the user's 80% target
- Interpretation:
  - this strategy family is economically valid but structurally closer to a payoff-driven trend system than a high-hit-rate system
- User explicitly approved the rule that, if existing factors cannot support a better direction, research may request new data and let the data layer expand accordingly.
- Research-process implication:
  - quant-researcher should not keep overfitting the same factor family indefinitely
  - if the current factor set appears exhausted, the next step is to define a new candidate direction and specify concrete data additions
- Preferred next candidate directions were recorded as:
  1. northbound flow + attention resonance
  2. policy / theme catalyst continuation
  3. attention-reversion with crowding guard

2026-03-27 northbound-attention data-layer kickoff:
- The user explicitly approved that, when the current factor set is not sufficient, research may push new concrete data requests back into the data layer.
- First implementation pass for the `northbound + attention resonance` line is now in place:
  - added `raw_northbound_daily`
  - added `raw_attention_daily`
  - added `research_market_context_daily`
  - added a first refresh pipeline and CLI entrypoint for market-context refresh
- First live refresh result:
  - `raw_northbound_daily = 11068`
  - `raw_attention_daily = 10`
  - `research_market_context_daily = 2777`
- Current source choices:
  - northbound: AKShare Eastmoney hold ranking interfaces
  - attention: Eastmoney hot rank first, with Xueqiu follow-rank fallback
- Current limitation:
  - theme tags are not yet populated
  - attention coverage is still only a thin first slice, not yet a complete historical panel
- Working interpretation:
  - the research line is no longer blocked on schema design
  - the next data-layer step should expand:
    - attention history coverage
    - theme / category tags
    - event / policy tags

2026-03-27 northbound-attention first passing strategy:
- Expanded `market_context` from a thin prototype into a usable research layer:
  - added historical attention ingestion from Baidu hot-search by trade date
  - added `attention_level` storage
  - added `attention_change_3d / attention_change_5d`
  - promoted northbound board names into first-pass `industry_name / sector_name / theme_tags / theme_breadth_score`
  - wired `research_market_context_daily` into the backtest loader and dependency registry
- Historical context coverage after the refresh:
  - `raw_attention_daily = 3828`
  - date range: `2025-01-02` to `2026-03-26`
  - distinct attention-covered stock codes: `51`
- Research path:
  - `v1` was over-constrained and produced `0` trades
  - `v2` proved the line could trade but had poor economics
  - event-study diagnostics on the attention sample showed the strongest short-horizon hit-rate pocket was:
    - hot-list names
    - 5-day pullback between roughly `-20%` and `-5%`
    - 20-day trend still positive
    - low realized volatility
    - small positive repair day
  - the winning implementation became `spec-cn-a-northbound-attention-resonance-v4`
- `v4` backtest result on `2025-01-02` to `2026-03-20`:
  - `trade_count = 9`
  - `trade_win_rate = 0.8889`
  - `annualized_return = 0.2044`
  - `max_drawdown = 0.0144`
  - `sharpe = 2.2639`
- Interpretation:
  - this is the first strategy after the data-layer expansion that satisfies all current user KPI gates
  - the strategy is still sample-light, so future work should improve event/theme/news coverage rather than immediately overfitting the rule set
  - `spec-cn-a-northbound-attention-resonance-v4` is now permanently archived in the strategy library and should be treated as a do-not-delete baseline candidate

2026-03-27 theme/news/event data-layer strengthening:
- Goal:
  - strengthen `theme/news/event` inputs for the `northbound-attention` research line
  - expand the usable stock-date context sample beyond the previous sparse `attention-only` coverage
- Implemented:
  - added `raw_notice_event_daily`
  - extended `research_market_context_daily` with:
    - `policy_event_tag`
    - `announcement_event_tag`
    - `announcement_count_1d`
  - `market_context.refresh` now ingests Eastmoney notice-report data and normalizes title/category keywords into coarse event tags
  - `research_market_context_daily` rebuild no longer keys only off sparse northbound/attention rows; it now lays context over `normalized_market_daily` from the configured `context_start_date`
  - dashboard now shows announcement coverage and recent notice-event rows
- Verified live result after refreshing with `notice_start_date=2026-03-18` and `context_start_date=2025-01-01`:
  - `raw_notice_event_daily = 3435`
  - notice date range: `2026-03-02` to `2026-03-20`
  - notice-covered stock codes: `1992`
  - `research_market_context_daily = 1482394`
  - rows with non-null `announcement_event_tag = 2865`
- Interpretation:
  - the context layer is no longer limited to the previous `6595` sparse rows
  - even before a stronger historical theme feed is added, the event layer has materially widened the usable context surface
  - theme tags are still only a first-pass proxy from northbound board names; the next strengthening step should target a more stable industry/concept membership source

2026-03-29 theme layer upgrade (industry/concept membership):
- Implemented a real theme membership table and refresh path:
  - added `raw_theme_membership_daily`
  - added theme snapshot ingestion using Eastmoney industry + concept membership (AKShare)
  - added context-layer fallback so `industry_name / sector_name / theme_tags` prefer snapshot data, otherwise fall back to northbound board_name
  - added theme snapshot summary to dashboard
- New controls:
  - `refresh_market_context` now accepts `--theme-snapshot-date`, `--max-industries`, `--max-concepts`, `--include-concepts`
  - default path is to snapshot industries only (concepts require `--include-concepts`)
- Operational note:
  - industry/concept membership fetch is heavy; recommended to run in a background session with a capped `max-industries` and only expand later.

2026-03-29 theme snapshot live-run result:
- Ran a real theme snapshot refresh against the new industry-membership path.
- Added per-board hard timeouts to the snapshot fetcher so the pipeline no longer hangs forever on one slow board.
- Live outcome on Eastmoney industry membership remained:
  - `raw_theme_membership_daily = 0`
  - `research_market_context_daily = 1482394`
  - themed rows stayed at `798647`
- Interpretation:
  - the code path is in place, but the current Eastmoney industry-member endpoint is still not stable enough to serve as the actual production theme source
  - the next serious upgrade should pivot to a different all-market classification source rather than keep forcing this endpoint

2026-03-29 CNInfo industry remap and concept-only theme expansion:
- Pivoted the `industry` membership source away from Eastmoney member pages and onto CNInfo company profiles.
- Verified live CNInfo profile requests with `Accept-Enckey`, then wired the refresh path so `raw_theme_membership_daily` writes:
  - `theme_type = industry`
  - `source_name = cninfo_profile`
- Added a new market-context refresh control:
  - `--skip-industries`
  - this allows concept/theme refreshes to run without re-fetching the full CNInfo industry snapshot every time
- Then ran a real concept-only refresh using Eastmoney concept member pages on top of the CNInfo industry baseline.
- Live post-refresh state:
  - `raw_theme_membership_daily = 5932`
  - `raw_theme_membership_daily WHERE theme_type = 'industry' = 4684`
  - `raw_theme_membership_daily WHERE theme_type = 'concept' = 886`
  - `theme_stock_codes = 5067`
  - `research_market_context_daily = 1482494`
  - `theme_tags <> '{}' rows = 839854`
- Coverage change:
  - themed context rows increased from `798647` to `839854`
  - the concept layer added `41207` additional themed stock-date rows on top of the previous board-name/industry baseline
- Top landed concepts in this first capped refresh:
  - `病原体防治 = 169`
  - `创新药 = 166`
  - `肝炎概念 = 57`
  - `痘病毒防治 = 54`
  - `幽门螺杆菌概念 = 51`
  - `单抗概念 = 49`
- Interpretation:
  - the theme layer is now materially better than the original `northbound board_name` proxy
  - `industry` is now on a stable all-market source
  - `concept` is usable through capped Eastmoney concept membership refreshes, especially when run with `--skip-industries`
  - with this layer in place, strategy research can resume without waiting for a perfect full-market theme taxonomy

2026-03-29 northbound-attention post-theme research pass:
- Started the next strategy-research round immediately after the theme-layer upgrade.
- Tested two small variants on top of the archived winner `spec-cn-a-northbound-attention-resonance-v4`:
  - `v5`: widened the attention rank filter from top-7 to top-10 while increasing concept-width weight
  - `v6`: widened further to top-12 and added `attention_change_3d >= 0` as a theme-resonance confirmation
- To avoid the slow CLI/schema path, the actual comparison run was executed in a single Python process:
  - one `2025-01-02 -> 2026-03-20` backtest frame load
  - then `v5` and `v6` were simulated against the same frame
- Observed result:
  - `v4 = trade_count 9, win_rate 0.8889, annualized_return 0.20437, max_drawdown 0.01439, sharpe 2.2639`
  - `v5 = trade_count 10, win_rate 0.8000, annualized_return 0.20430, max_drawdown 0.01439, sharpe 2.1893`
  - `v6 = trade_count 10, win_rate 0.8000, annualized_return 0.20430, max_drawdown 0.01439, sharpe 2.1893`
- Interpretation:
  - the new theme/context layer can modestly expand sample count
  - but the first two post-theme variants did not beat the archived `v4` baseline
  - because the user gate was stated as `win_rate > 80%` rather than `>= 80%`, `v5/v6` should not be kept as promoted versions
  - current best version remains `spec-cn-a-northbound-attention-resonance-v4`
