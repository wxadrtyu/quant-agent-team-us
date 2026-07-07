---
name: refresh-quant-data
description: "Use when the user wants to bring the A-share quant dataset up to date / fill data gaps after being away (e.g. 'update the data', 'catch up the data to today', '补数据', '把数据补到最新'). Runs the incremental refresh engine and applies the multi-source playbook to handle throttling, switch providers, and validate."
---

# Refresh Quant Data (A-share dataset catch-up)

Bring every dataset in `quant.duckdb` up to today and rebuild derived tables, the way it was
done on 2026-06-28. The point is judgment, not just running a script: free data providers
throttle, so you must monitor, switch sources per the roster, and validate.

## 1. Quick start

```
python scripts/refresh_all_data.py            # full catch-up to today
python scripts/refresh_all_data.py --only price index panel
python scripts/refresh_all_data.py --skip valuation roe
```

It prints a BEFORE/AFTER state (rows + max_date per table) and per-step OK/ERR. Steps:
`price, index, valuation, roe, meta(industry/ST/delisted), suspension, panel`.

Run long network steps in the BACKGROUND (price ~24min; valuation/roe hours) and monitor by
counting output parquet files. Network-free steps (suspension, panel, index) are fast.

## 2. Iron rules (multi-source data discipline)

- **One consistent source per factor, whole universe.** Never blend providers within one
  field's cross-section (baidu PE-TTM vs eastmoney PE-动态 are different definitions → distorts).
- **Backups = failover, not concurrent blending.** A backup only fills stocks the primary
  ENTIRELY failed. Partition by "not yet fetched"; never double-fetch the same field.
- **Tag every row with its `source`.** Keep provenance; different sources write different paths.
- **No look-ahead.** Fundamentals are point-in-time: annual ROE effective (Y+1)-04-30, etc.

## 3. Data-source roster (primary → backups). Full table: docs/2026-06-28-data-source-roster.md

| Field | Primary | Backups | Throttle note |
|---|---|---|---|
| price OHLCV (qfq) | eastmoney `stock_zh_a_hist` | sina `stock_zh_a_daily` | use **qfq not hfq** (hfq makes negative prices for ~300 stocks) |
| index benchmark | **sina `stock_zh_index_daily`** | csindex, eastmoney | sina is fast & unthrottled |
| valuation PE/PB (history) | baidu `stock_zh_valuation_baidu` | eastmoney spot snapshot (current floor) | baidu throttles ~1800 calls → drop to 3 workers |
| valuation (bulk, fastest) | tushare `daily_basic` | — | needs token w/ 2000 points (.secrets/tushare_token.txt) |
| ROE / quality | **THS `stock_financial_abstract_ths`** | sina `stock_financial_analysis_indicator` | THS ~6s/stock, different provider |
| ROE (bulk, fastest) | tushare `fina_indicator` | — | needs 2000 points |
| industry / ST | eastmoney boards + spot; tushare `stock_basic` | — | tushare stock_basic = 1/hour at low points |
| delisted | sse `stock_info_sh_delist` | eastmoney | **szse SSL broken** → SZ delist needs alt source |
| suspension | derive from calendar gaps (local) | — | network-free |
| dividend (verify adj) | cninfo `stock_dividend_cninfo` | THS | — |

## 4. Throttle playbook (what actually happened 2026-06-28)

1. **A provider starts failing en masse** (e.g. baidu after ~1800 calls): STOP the run (it's
   counterproductive to hammer a throttled endpoint), drop workers (8 → 3), resume (resumable
   skips done files). A single test call after stopping confirms cooldown.
2. **A field's only source is slow** (per-stock ROE 10s): switch to a DIFFERENT provider for
   that field (sina ROE → THS). Don't run two ROE sources at once (discipline §2).
3. **eastmoney gets stressed** from heavy pulls (ChunkedEncodingError / slow pagination): back
   off eastmoney, prefer sina/THS/cninfo/csindex for a while.
4. **An endpoint hangs** (no timeout): set `socket.setdefaulttimeout(25)` so hangs become
   retryable errors.
5. **tushare available?** If the user has a token with ≥2000 points, `daily_basic`+`fina_indicator`
   replace the slow per-stock baidu/THS entirely (minutes vs hours). Token in `.secrets/` (gitignored).

## 5. Validate after refresh

- Each table's `max_date` advanced toward today (the BEFORE/AFTER report shows this).
- Price adjustment clean: the old "impossible >10% main-board move" heuristic is OBSOLETE for
  2022+ data (registration-system IPOs + restructuring resumptions are legit) — cross-check any
  large move against akshare's own `pct_chg` (≈99% agree = real).
- `factor_panel` rebuilt and recent-year null rate ≈ 0.
- Report to the user what was filled and any gaps (e.g. SZ delisted still missing).

## 6. Key files
- Engine: `scripts/refresh_all_data.py`
- Fetchers: `fetch_akshare_history.py` (price), `fetch_akshare_fundamentals.py --skip-roe`
  (valuation), `fetch_roe_ths.py` (ROE), `fetch_valuation_snapshot.py` (valuation floor),
  `fetch_industry_st_delist.py` (meta), `build_tradability.py` (suspension)
- Ingest: `ingest_akshare_to_duckdb.py`, `ingest_fundamentals.py`, `ingest_meta.py`, `build_factor_panel.py`
- Roster: `docs/2026-06-28-data-source-roster.md`
