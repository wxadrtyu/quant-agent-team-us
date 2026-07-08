"""A1 — Multi-factor panel builder.

Computes cross-sectional factor inputs from `market_daily` (price/volume) and,
when available, valuation/financials (value/quality). Output table `factor_panel`
is the unified `frame` consumed by scoring/backtest/IC.

Design rules (locked 2026-06-28):
- NO look-ahead: every factor at date t uses only data with date <= t. Price
  factors use trailing windows; fundamentals are as-of (point-in-time) joined.
- Stores RAW factor values; cross-sectional z-scoring / ranking happens
  downstream (factor_scoring, ic_weighting) per trade_date.

Factors (raw):
  momentum : ret_20d, ret_60d, mom_120_20 (12-1 momentum, skips last ~month)
  reversal : ret_5d
  volatility: vol_20d, vol_60d (stddev of daily returns; low-vol => long_low)
  liquidity: turnover_rate, amt_20d (low-liquidity premium => long_low)
  technical: px_to_ma20, px_to_ma60 (distance from moving average)
  value    : ep = 1/pe_ttm, bp = 1/pb        (present only if valuation_daily exists)
  quality  : roe                              (present only if financials exists)
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

PRICE_FACTOR_SQL = """
CREATE OR REPLACE TABLE factor_panel AS
WITH base AS (
    SELECT
        stock_code,
        trade_date,
        close_adj,
        high,
        low,
        volume,
        amplitude,
        turnover_rate,
        amount,
        lag(close_adj, 1) OVER (PARTITION BY stock_code ORDER BY trade_date) AS prev_close,
        close_adj / NULLIF(lag(close_adj, 1) OVER (PARTITION BY stock_code ORDER BY trade_date), 0) - 1.0 AS daily_ret,
        -- Strategy BB: volume-weighted oscillators (new Alpha dimension)
        -- Typical price for MFI calculation
        (high + low + close_adj) / 3.0 AS tp,
        lag((high + low + close_adj) / 3.0, 1) OVER (PARTITION BY stock_code ORDER BY trade_date) AS prev_tp
    FROM {src}
), feat AS (
    SELECT
        stock_code,
        trade_date,
        turnover_rate,
        -- momentum / reversal
        close_adj / NULLIF(lag(close_adj, 5)  OVER w, 0) - 1.0 AS ret_5d,
        close_adj / NULLIF(lag(close_adj, 20) OVER w, 0) - 1.0 AS ret_20d,
        close_adj / NULLIF(lag(close_adj, 60) OVER w, 0) - 1.0 AS ret_60d,
        lag(close_adj, 20) OVER w / NULLIF(lag(close_adj, 120) OVER w, 0) - 1.0 AS mom_120_20,
        -- volatility (sample stddev of daily returns)
        stddev_samp(daily_ret) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_20d,
        stddev_samp(daily_ret) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS vol_60d,
        -- Parkinson volatility: uses intraday high-low range, more efficient than close-to-close.
        sqrt(avg(CASE WHEN high > low AND low > 0 THEN power(ln(high / low), 2) ELSE NULL END)
             OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) / (4 * ln(2))) AS parkinson_vol_20d,
        -- liquidity
        avg(amount) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amt_20d,
        -- technical: distance from moving average
        close_adj / NULLIF(avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) - 1.0 AS px_to_ma20,
        close_adj / NULLIF(avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 59 PRECEDING AND CURRENT ROW), 0) - 1.0 AS px_to_ma60,
        -- Strategy D: volume-price structure factors
        -- 1. vol_price_corr_20d: corr(daily_ret, ln(volume)) over 20d window.
        --    Negative = price up on declining volume (quiet accumulation, bullish).
        --    Positive = price up on rising volume (may signal exhaustion).
        corr(daily_ret, ln(volume + 1)) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_price_corr_20d,
        -- 2. turnover_change_5_20: ratio of recent 5d avg turnover to 20d avg turnover.
        --    >1 = turnover accelerating (attention surge); <1 = turnover fading.
        NULLIF(avg(turnover_rate) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) /
        NULLIF(avg(turnover_rate) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS turnover_change_5_20,
        -- 3. amplitude_avg_20d: mean intraday amplitude (high-low/close).
        --    Low amplitude = controlled price action (institutional dominance).
        avg(amplitude) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amplitude_avg_20d,
        -- Strategy E: classic technical indicators (from reference project)
        -- 4. bias_20: 20-day BIAS = (close - MA20) / MA20. Price deviation from MA.
        (close_adj - avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)) /
        NULLIF(avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS bias_20,
        -- 5. rsi_14: 14-day Relative Strength Index.
        --    RSI = 100 - 100/(1+RS), RS = avg_gain / avg_loss over 14d.
        100.0 - 100.0 / NULLIF(1.0 +
            avg(CASE WHEN daily_ret > 0 THEN daily_ret ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)
            / NULLIF(-avg(CASE WHEN daily_ret < 0 THEN daily_ret ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW), 0)
        , 0) AS rsi_14,
        -- 6. turnover_std_20d: 20-day stddev of turnover_rate. Turnover volatility.
        stddev_samp(turnover_rate) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS turnover_std_20d,
        -- 7. volume_ma_ratio_5_20: ratio of 5d avg volume to 20d avg volume.
        --    >1 = volume surge; <1 = volume drying up.
        NULLIF(avg(volume) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) /
        NULLIF(avg(volume) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS volume_ma_ratio_5_20,
        -- 8. rsv_9: Raw Stochastic Value = (close - lowest_low_9) / (highest_high_9 - lowest_low_9) * 100
        --    This is the raw input for KD calculation. Low RSV = oversold.
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 8 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 8 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 8 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_9,
        -- Strategy P: RSV at alternative lookback windows (oversold pullback filter).
        -- rsv_9 is the champion 2-factor filter (IR=1.004 with ret_20d). Test wider/narrower.
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_5,
        -- rsv_3 / rsv_7: even shorter windows (5d was the champion IR=1.074; test the trend)
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_3,
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_7,
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_14,
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_20,
        -- Strategy L: higher-moment & true-range factors (new Alpha dimensions)
        -- L1. ret_10d / ret_15d: intermediate momentum windows (fill gap 5d..20d)
        close_adj / NULLIF(lag(close_adj, 10) OVER w, 0) - 1.0 AS ret_10d,
        close_adj / NULLIF(lag(close_adj, 15) OVER w, 0) - 1.0 AS ret_15d,
        -- L2. ret_skew_20d: skewness of daily returns over 20d.
        --    Low skew = stable controlled uptrend; high skew = lottery-like spikes (retail driven).
        skewness(daily_ret) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ret_skew_20d,
        -- L3. atr_20d: 20d Average True Range / close. True range includes overnight
        --    gaps, more comprehensive than amplitude. Low ATR = institutional control.
        avg(greatest(high - low, abs(high - prev_close), abs(low - prev_close)))
            OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
            / NULLIF(close_adj, 0) AS atr_20d,
        -- Strategy S: Bollinger & higher-moment factors (new Alpha exploration)
        -- S1. boll_pct_b_20: Bollinger %B = (close - MA20) / (2 * stddev_20).
        --    Standardized price position. Low %B = below lower band = oversold (mean-reversion).
        --    Different from RSV: uses mean+stddev (Gaussian) vs range (non-parametric).
        (close_adj - avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)) /
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS boll_pct_b_20,
        -- S2. boll_pct_b_10: 10-day Bollinger %B (shorter window, more responsive)
        (close_adj - avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)) /
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0) AS boll_pct_b_10,
        -- S3. drawdown_5d: close / 5-day-high - 1. Always <= 0.
        --    Direct pullback measure from recent peak. More negative = deeper pullback.
        --    long_low = deep pullback (same "buy the dip" logic as RSV).
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_5d,
        -- S4. kurtosis_20d: excess kurtosis of daily returns over 20d.
        --    Low kurtosis = thin tails = predictable, institutional-controlled.
        --    High kurtosis = fat tails = black-swan prone, retail-driven.
        kurtosis(daily_ret) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS kurtosis_20d,
        -- S5. boll_width_20: Bollinger band width = 2*stddev / MA.
        --    Narrow bands = consolidation (volatility squeeze), wide = trending.
        --    Low width = quiet, potential breakout setup.
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) /
        NULLIF(avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS boll_width_20,
        -- Strategy T: window variants for Bollinger/drawdown (deep-dive on Batch S breakthroughs)
        -- Bollinger width at 5d / 10d (20d was IR=0.663/MDD=9.8%, test shorter)
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) /
        NULLIF(avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) AS boll_width_5,
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0) /
        NULLIF(avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0) AS boll_width_10,
        -- Bollinger %B at 5d / 7d (10d was IR=0.804, test shorter)
        (close_adj - avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)) /
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0) AS boll_pct_b_5,
        (close_adj - avg(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)) /
        NULLIF(2.0 * stddev_samp(close_adj) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) AS boll_pct_b_7,
        -- Drawdown at 3d / 7d / 10d (5d was BJ50 IR=0.969, test window effect)
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_3d,
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_7d,
        -- Strategy MM: drawdown_8d (longer pullback window for even lower MDD)
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_8d,
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_10d,
        -- Strategy Z: fine-tuned windows around champion dd3_rsv7 (IR=1.370)
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_6,
        (close_adj - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 7 PRECEDING AND CURRENT ROW)) /
        NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 7 PRECEDING AND CURRENT ROW)
         - min(low) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0) * 100.0 AS rsv_8,
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 1 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_2d,
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_4d,
        -- Strategy LL: drawdown_6d (fill gap between dd5 MDD champion and dd7)
        close_adj / NULLIF(max(high) OVER (PARTITION BY stock_code ORDER BY trade_date
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW), 0) - 1.0 AS drawdown_6d,
        -- Strategy BB: volume-weighted oscillators (new Alpha dimension)
        -- BB1. MFI_14: Money Flow Index (volume-weighted RSI).
        --   Measures buying/selling pressure using typical price * volume.
        --   Low MFI = money flowing out (oversold), High = money flowing in (overbought).
        --   long_low = oversold (same logic as RSV/RSI but incorporates volume).
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_14,
        -- BB2. OBV_change_20: On-Balance Volume change normalized by avg volume.
        --   sum(+volume on up days, -volume on down days) / avg(volume).
        --   Low = distribution/selling pressure. High = accumulation.
        --   long_low = selling pressure = potential oversold reversal.
        sum(CASE WHEN daily_ret > 0 THEN volume ELSE -volume END)
            OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
            / NULLIF(avg(volume) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS obv_change_20,
        -- BB3. RSI_7: 7-day RSI (shorter window than rsi_14, more responsive).
        --   long_low = oversold. Tests if shorter RSI window works better at n10.
        100.0 - 100.0 / NULLIF(1.0 +
            avg(CASE WHEN daily_ret > 0 THEN daily_ret ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
            / NULLIF(-avg(CASE WHEN daily_ret < 0 THEN daily_ret ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0)
        , 0) AS rsi_7,
        -- Strategy CC: MFI and OBV window variants
        -- CC1. MFI_7: 7-day MFI (shorter, more responsive)
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_7,
        -- CC2. MFI_10: 10-day MFI
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_10,
        -- CC3. MFI_20: 20-day MFI (longer, smoother)
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_20,
        -- CC4. OBV_change_10: 10-day OBV change normalized by avg volume
        sum(CASE WHEN daily_ret > 0 THEN volume ELSE -volume END)
            OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)
            / NULLIF(avg(volume) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0) AS obv_change_10,
        -- Strategy DD: Fine-tune MFI windows around champion mfi_7
        -- DD1. MFI_5: 5-day MFI (even shorter)
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_5,
        -- DD2. MFI_6: 6-day MFI
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_6,
        -- DD3. MFI_8: 8-day MFI
        100.0 - 100.0 / NULLIF(1.0 +
            sum(CASE WHEN tp > prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 7 PRECEDING AND CURRENT ROW)
            / NULLIF(sum(CASE WHEN tp <= prev_tp THEN tp * volume ELSE 0 END)
                OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0)
        , 0) AS mfi_8,
        -- Strategy EE: Chaikin Money Flow (CMF) — volume-weighted CLV, alternative to MFI
        -- CLV = ((close-low)-(high-close))/(high-low) measures where close is in day's range
        -- CMF_n = sum(CLV * volume) / sum(volume) over n days
        -- CMF_7: 7-day CMF (short window, matching mfi_7 optimal)
        sum(CASE WHEN high > low THEN ((close_adj - low) - (high - close_adj)) / (high - low) * volume ELSE 0 END)
            OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
        / NULLIF(sum(volume) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) AS cmf_7,
        -- CMF_14: 14-day CMF (standard window)
        sum(CASE WHEN high > low THEN ((close_adj - low) - (high - close_adj)) / (high - low) * volume ELSE 0 END)
            OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)
        / NULLIF(sum(volume) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW), 0) AS cmf_14,
        -- CMF_20: 20-day CMF (long window)
        sum(CASE WHEN high > low THEN ((close_adj - low) - (high - close_adj)) / (high - low) * volume ELSE 0 END)
            OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
        / NULLIF(sum(volume) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS cmf_20,
        -- CMF_10: 10-day CMF (medium window)
        sum(CASE WHEN high > low THEN ((close_adj - low) - (high - close_adj)) / (high - low) * volume ELSE 0 END)
            OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)
        / NULLIF(sum(volume) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0) AS cmf_10
    FROM base
    WINDOW w AS (PARTITION BY stock_code ORDER BY trade_date)
)
SELECT * FROM feat
"""


def build_factor_panel(
    db_path: str | Path = "quant.duckdb",
    source_table: str = "market_daily",
    add_fundamentals: bool = True,
) -> dict:
    """Build/refresh the `factor_panel` table. Returns a summary dict."""
    con = duckdb.connect(str(db_path))
    con.execute(PRICE_FACTOR_SQL.format(src=source_table))

    tables = {r[0] for r in con.execute("show tables").fetchall()}
    joined = []
    if add_fundamentals and "valuation_daily" in tables:
        # as-of join: latest valuation on/before each trade_date (point-in-time)
        con.execute("""
            CREATE OR REPLACE TABLE factor_panel AS
            SELECT fp.*,
                   1.0 / NULLIF(v.pe_ttm, 0) AS ep,
                   1.0 / NULLIF(v.pb, 0)     AS bp,
                   1.0 / NULLIF(v.total_mv, 0) AS size_inv
            FROM factor_panel fp
            ASOF LEFT JOIN valuation_daily v
              ON fp.stock_code = v.stock_code AND fp.trade_date >= v.trade_date
        """)
        joined.append("value(ep,bp)")
        joined.append("size(size_inv)")
    if add_fundamentals and "financials" in tables:
        con.execute("""
            CREATE OR REPLACE TABLE factor_panel AS
            SELECT fp.*, f.roe
            FROM factor_panel fp
            ASOF LEFT JOIN financials f
              ON fp.stock_code = f.stock_code AND fp.trade_date >= f.report_date
        """)
        joined.append("quality(roe)")

    n, stocks, mn, mx = con.execute(
        "SELECT count(*), count(DISTINCT stock_code), min(trade_date), max(trade_date) FROM factor_panel"
    ).fetchone()

    # Industry momentum: industry_mom_20d = mean(ret_20d) across stocks in same industry
    # on the same trade_date. Industry membership is static (slowly-varying approximation).
    tables = {r[0] for r in con.execute("show tables").fetchall()}
    if "industry" in tables:
        con.execute("""
            CREATE OR REPLACE TABLE factor_panel AS
            WITH ind_mom AS (
                SELECT f.trade_date, i.industry,
                       avg(f.ret_20d) AS industry_mom_20d
                FROM factor_panel f
                JOIN industry i ON f.stock_code = i.stock_code
                WHERE f.ret_20d IS NOT NULL
                GROUP BY f.trade_date, i.industry
            )
            SELECT fp.*, m.industry_mom_20d
            FROM factor_panel fp
            JOIN industry i ON fp.stock_code = i.stock_code
            LEFT JOIN ind_mom m
              ON m.trade_date = fp.trade_date AND m.industry = i.industry
        """)
        joined.append("industry_mom(industry_mom_20d)")

    # Strategy FF: 资金流向 + 龙虎榜因子 (新 Alpha 维度, 抗跌 + 事件驱动)
    # 所有因子用 trailing window (含当日), 与 ret_20d/rsv_9 同口径, 无额外前视偏差。
    tables = {r[0] for r in con.execute("show tables").fetchall()}

    # FF-1: 个股资金流向 (moneyflow_daily 全市场, 每股每天)
    if "moneyflow_daily" in tables:
        con.execute("""
            CREATE OR REPLACE TABLE factor_panel AS
            SELECT fp.*,
                mf.net_mf_amount,
                mf.buy_lg_amount, mf.sell_lg_amount,
                mf.buy_elg_amount, mf.sell_elg_amount,
                -- 个股5日主力净流入额 (trailing 5d, 含当日)
                sum(coalesce(mf.net_mf_amount, 0)) OVER w AS net_mf_amount_5d,
                -- 个股20日主力净流入额
                sum(coalesce(mf.net_mf_amount, 0)) OVER w20 AS net_mf_amount_20d,
                -- 大单+超大单5日净额 (主力大资金动向)
                sum(coalesce(mf.buy_lg_amount, 0) + coalesce(mf.buy_elg_amount, 0)
                    - coalesce(mf.sell_lg_amount, 0) - coalesce(mf.sell_elg_amount, 0)) OVER w AS lg_net_amount_5d
            FROM factor_panel fp
            LEFT JOIN moneyflow_daily mf
              ON fp.stock_code = mf.stock_code AND fp.trade_date = mf.trade_date
            WINDOW w AS (PARTITION BY fp.stock_code ORDER BY fp.trade_date
                         ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
                   w20 AS (PARTITION BY fp.stock_code ORDER BY fp.trade_date
                           ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
        """)
        joined.append("moneyflow(net_mf_amount_5d,net_mf_amount_20d,lg_net_amount_5d)")

    # FF-2: 龙虎榜因子 (lhb_daily 稀疏, 仅上榜股票; 缺失=未上榜)
    if "lhb_daily" in tables:
        con.execute("""
            CREATE OR REPLACE TABLE factor_panel AS
            SELECT fp.*,
                -- 当日是否上榜 (0/1)
                CASE WHEN lhb.net_amount IS NOT NULL THEN 1 ELSE 0 END AS lhb_flag,
                -- 近20日上榜次数 (关注度热度)
                sum(CASE WHEN lhb.net_amount IS NOT NULL THEN 1 ELSE 0 END) OVER w20 AS lhb_count_20d,
                -- 近5日龙虎榜净买入额 (游资/机构资金认可)
                sum(coalesce(lhb.net_amount, 0)) OVER w AS lhb_net_amount_5d,
                -- 近20日龙虎榜净买入额
                sum(coalesce(lhb.net_amount, 0)) OVER w20 AS lhb_net_amount_20d,
                -- 近20日机构席位净买入 (只统计"机构专用"席位, 抗跌信号)
                sum(coalesce(li.inst_net_buy, 0)) OVER w20 AS lhb_inst_net_buy_20d
            FROM factor_panel fp
            LEFT JOIN lhb_daily lhb
              ON fp.stock_code = lhb.stock_code AND fp.trade_date = lhb.trade_date
            LEFT JOIN (
                -- 机构席位: exalter 含"机构专用", 按 stock+date 聚合净买入
                SELECT stock_code, trade_date, sum(net_buy) AS inst_net_buy
                FROM lhb_inst_daily
                WHERE exalter LIKE '%机构%'
                GROUP BY stock_code, trade_date
            ) li
              ON fp.stock_code = li.stock_code AND fp.trade_date = li.trade_date
            WINDOW w AS (PARTITION BY fp.stock_code ORDER BY fp.trade_date
                         ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
                   w20 AS (PARTITION BY fp.stock_code ORDER BY fp.trade_date
                           ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
        """)
        joined.append("lhb(lhb_count_20d,lhb_net_amount_5d,lhb_net_amount_20d,lhb_inst_net_buy_20d)")

    # FF-3: 行业资金流向 (需 industry + moneyflow; 个股净流入按行业聚合)
    tables = {r[0] for r in con.execute("show tables").fetchall()}
    if "industry" in tables and "moneyflow_daily" in tables:
        con.execute("""
            CREATE OR REPLACE TABLE factor_panel AS
            WITH ind_flow AS (
                -- 每日行业资金净流入 = 行业内个股 net_mf_amount 之和
                SELECT fp.trade_date, i.industry,
                       sum(coalesce(fp.net_mf_amount, 0)) AS ind_net_inflow
                FROM factor_panel fp
                JOIN industry i ON fp.stock_code = i.stock_code
                GROUP BY fp.trade_date, i.industry
            ),
            ind_flow_roll AS (
                SELECT trade_date, industry,
                       sum(ind_net_inflow) OVER (PARTITION BY industry ORDER BY trade_date
                           ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ind_net_inflow_5d
                FROM ind_flow
            )
            SELECT fp.*, r.ind_net_inflow_5d
            FROM factor_panel fp
            JOIN industry i ON fp.stock_code = i.stock_code
            LEFT JOIN ind_flow_roll r
              ON r.trade_date = fp.trade_date AND r.industry = i.industry
        """)
        joined.append("ind_flow(ind_net_inflow_5d)")

    # MACD and KD require recursive EMA (not expressible in pure SQL window functions).
    # Compute them in Python, reading close_adj from the source market_daily table.
    try:
        src_df = con.execute(
            f"SELECT stock_code, trade_date, close_adj FROM {source_table} ORDER BY stock_code, trade_date"
        ).fetchdf()
        fp_df = con.execute("SELECT stock_code, trade_date, rsv_9 FROM factor_panel").fetchdf()
        if not src_df.empty and not fp_df.empty:
            merged = src_df.merge(fp_df, on=["stock_code", "trade_date"], how="inner")
            # MACD: DIF = EMA12 - EMA26, DEA = EMA(DIF, 9), MACD = 2*(DIF-DEA)
            def _macd(group):
                close = group["close_adj"]
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                dif = ema12 - ema26
                dea = dif.ewm(span=9, adjust=False).mean()
                return pd.DataFrame({"dif": dif, "macd_hist": 2 * (dif - dea)}, index=group.index)
            macd_df = merged.groupby("stock_code", group_keys=False).apply(_macd)
            merged["dif"] = macd_df["dif"]
            merged["macd_hist"] = macd_df["macd_hist"]

            # KD: K = EMA(RSV, 1/3), D = EMA(K, 1/3)
            def _kd(group):
                rsv = group["rsv_9"]
                k = rsv.ewm(alpha=1.0/3.0, adjust=False).mean()
                d = k.ewm(alpha=1.0/3.0, adjust=False).mean()
                return pd.DataFrame({"k_value": k, "d_value": d}, index=group.index)
            kd_df = merged.groupby("stock_code", group_keys=False).apply(_kd)
            merged["k_value"] = kd_df["k_value"]
            merged["d_value"] = kd_df["d_value"]

            # Write back: add columns and update
            for col in ["dif", "macd_hist", "k_value", "d_value"]:
                con.execute(f"ALTER TABLE factor_panel ADD COLUMN IF NOT EXISTS {col} DOUBLE")
            con.execute("""
                UPDATE factor_panel AS fp
                SET dif = src.dif, macd_hist = src.macd_hist,
                    k_value = src.k_value, d_value = src.d_value
                FROM (SELECT stock_code, trade_date, dif, macd_hist, k_value, d_value FROM merged) AS src
                WHERE fp.stock_code = src.stock_code AND fp.trade_date = src.trade_date
            """)
            joined.append("macd(dif,macd_hist)")
            joined.append("kd(k_value,d_value)")
    except Exception as e:
        print(f"WARNING: MACD/KD post-processing failed: {e}")

    cols = [r[0] for r in con.execute("describe factor_panel").fetchall()]
    con.close()
    return {
        "rows": n, "stocks": stocks, "date_min": str(mn), "date_max": str(mx),
        "columns": cols, "fundamentals_joined": joined,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_factor_panel(), ensure_ascii=False, indent=2))
