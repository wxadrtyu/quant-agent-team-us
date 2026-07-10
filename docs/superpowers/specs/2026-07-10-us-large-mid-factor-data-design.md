# US Large/Mid-Cap Factor Data Design

Status: draft for user review
Date: 2026-07-10
Branch: `codex/strategy-v1.0-us`
Scope: US equities v1.0 factor data collection for large/mid-cap tradable universes

## 1. Purpose

This document defines the first US-equity data and factor scope for `quant-agent-team-us`.
The goal is to reuse the existing project pipeline shape:

```text
daily market data -> factor_panel -> reviewed factor library -> IC weighting / HPO -> review gates
```

Only the pipeline mechanics are reused from the A-share project. A-share factor validity,
A-share event fields, and A-share trading constraints are not assumed to transfer to US equities.

## 2. Universe

US v1.0 starts with large/mid-cap tradable universes:

- `sp500`: S&P 500 constituents
- `nasdaq100`: Nasdaq 100 constituents
- `russell1000`: Russell 1000 constituents
- `us_large_mid`: union of the above, de-duplicated by symbol

Backtests should support both single-universe runs and the merged `us_large_mid` run.
The single-universe runs are used to detect whether factor behavior differs between broad
large-cap, growth-heavy, and large/mid-cap pools.

Historical point-in-time membership is preferred. If only current constituents are available
in the first download pass, the data layer must mark the membership source as a current
snapshot and reports must explicitly flag survivorship bias.

## 3. Raw Tables To Collect

### 3.1 `us_stock_meta`

One row per tradable symbol/source snapshot.

Required fields:

- `symbol`
- `name`
- `exchange`
- `asset_type`
- `currency`
- `ipo_date`
- `delist_date`
- `status`
- `sector`
- `industry`
- `market_cap`
- `source`
- `source_updated_at`

Rules:

- Exclude non-common-stock instruments from v1.0 unless explicitly whitelisted.
- Keep ADRs, ETFs, preferred shares, warrants, and funds out of the first production universe.
- Preserve `source` so metadata from multiple providers is not silently blended.

### 3.2 `us_index_membership`

One row per symbol membership interval.

Required fields:

- `universe_name`
- `symbol`
- `effective_date`
- `end_date`
- `membership_type`
- `source`
- `source_updated_at`

Rules:

- `effective_date` and `end_date` make membership point-in-time queryable.
- If the first source only provides current membership, store `membership_type = "current_snapshot"`.
- Current-snapshot membership is acceptable for plumbing and early smoke tests, but not for
production-grade performance claims.

### 3.3 `us_market_daily`

One row per symbol and trade date.

Required fields:

- `symbol`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `adj_close`
- `volume`
- `split_factor`
- `dividend`
- `source`

Rules:

- `adj_close` is required for return calculations unless split/dividend fields are complete
and the project computes adjusted prices itself.
- Dollar volume is derived as `adj_close * volume` or `close * volume` depending on the
selected adjusted-price convention; the convention must be fixed in the implementation plan.
- One primary provider owns each field. Backup providers are failover only and must not
overwrite the same field without a source-tagged remediation step.

## 4. First Candidate Factors

The first factor set is US-specific and price/volume-first. These are candidates for review,
not accepted alpha conclusions.

### 4.1 Momentum

- `ret_20d`: 1-month return, `long_high`
- `ret_60d`: 3-month return, `long_high`
- `ret_120d`: 6-month return, `long_high`
- `mom_252_21`: 12-1 momentum, skipping the most recent month, `long_high`

### 4.2 Short-Term Reversal / Pullback

- `ret_5d`: 1-week return, `long_low`
- `drawdown_5d`: distance from 5-day high, `long_low`
- `drawdown_10d`: distance from 10-day high, `long_low`
- `boll_pct_b_20`: position inside 20-day Bollinger band, `long_low`

### 4.3 Trend

- `px_to_ma20`: price versus 20-day moving average, `long_high`
- `px_to_ma60`: price versus 60-day moving average, `long_high`
- `ma20_above_ma60`: 20-day moving average above 60-day moving average, `long_high`

### 4.4 Volatility / Tail Risk

- `vol_20d`: 20-day close-to-close volatility, `long_low`
- `vol_60d`: 60-day close-to-close volatility, `long_low`
- `atr_20d`: average true range divided by price, `long_low`
- `parkinson_vol_20d`: high-low range volatility, `long_low`
- `ret_skew_20d`: 20-day return skewness, reviewed as a risk/lottery proxy before use
- `kurtosis_20d`: 20-day excess kurtosis, reviewed as a tail-risk proxy before use

### 4.5 Volume-Price Structure

- `volume_ma_ratio_5_20`: 5-day average volume versus 20-day average volume
- `obv_change_20`: 20-day on-balance-volume change normalized by average volume
- `cmf_20`: 20-day Chaikin Money Flow
- `mfi_14`: 14-day Money Flow Index

Directions for volume-price factors are not assumed from A-share results. They enter v1.0
as factor candidates and must be validated per US universe.

### 4.6 Liquidity and Size Controls

- `dollar_volume_20d`: 20-day average dollar volume, used first as a liquidity filter
- `turnover_stability_20d`: stability of dollar volume or volume, used as a tradability/risk feature
- `log_market_cap`: size exposure, used first for grouping and diagnostics rather than alpha

Default tradability filters:

- exclude symbols below a minimum price threshold
- exclude symbols below a minimum `dollar_volume_20d` threshold
- exclude non-common-stock instruments
- exclude symbols without enough trailing history for the selected factors

### 4.7 Sector / Industry Relative Strength

- `sector_mom_20d`: average 20-day return by sector, `long_high`
- `industry_mom_20d`: average 20-day return by industry, `long_high`
- optional sector-neutral scoring if sector coverage is dense enough

## 5. Deferred Factors

The following are explicitly deferred from v1.0:

- fundamentals: PE, PB, ROE, margins, revenue growth, earnings revisions
- analyst estimates and ratings
- options data: implied volatility, put/call, skew, open interest
- news, social sentiment, and event data
- institutional ownership and 13F-derived factors
- A-share-only fields such as limit-up/down, ST, northbound flow, LHB, or A-share moneyflow

Deferred factors require point-in-time sources and separate source-discipline rules before
they can enter the reviewed factor library.

## 6. Data Quality Gates

Before a downloaded dataset can be used for factor research:

- `symbol + trade_date` must be unique in `us_market_daily`.
- `adj_close`, `close`, and `volume` must be non-null for the active universe after warmup.
- split/dividend handling must be internally consistent with return calculations.
- sector/industry coverage should be reported; sector-neutral runs are disabled if coverage is weak.
- current-snapshot membership must be labeled as survivorship-biased.
- provider source must be stored and carried through validation reports.
- no factor should mix the same field from multiple providers without an explicit failover record.

## 7. Implementation Shape

The implementation should keep US-specific logic separate from A-share-specific assumptions:

- create US raw/normalized table handling without reusing A-share ST, limit, or LHB concepts
- add a US factor library or market-scoped factor registry rather than treating the A-share
  `DEFAULT_FACTOR_LIBRARY` as globally valid
- reuse existing scoring, IC weighting, HPO, null test, holdout, and review gates after the
  US `factor_panel` has a compatible schema
- keep the first download pass focused on data needed for the factors above

## 8. Acceptance For This Design Stage

This design stage is accepted when:

- the user agrees that v1.0 starts with `sp500`, `nasdaq100`, `russell1000`, and `us_large_mid`
- the raw table list is sufficient for the first download pass
- the candidate factor list is recognized as US-specific and not copied from A-share performance
- deferred data families are intentionally excluded from v1.0

After approval, the next step is an implementation plan for source selection, schema changes,
download scripts, validation reports, and factor-panel construction.
