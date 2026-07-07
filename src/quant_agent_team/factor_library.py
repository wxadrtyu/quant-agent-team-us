"""A17 — Curated, human-reviewed factor library.

Locked decision (2026-06-28): the tight quant loop does NOT call an LLM to invent
factors per iteration. It draws factors from THIS reviewed library. New factor ideas
are proposed offline (offline_factor_suggester) and only enter here after human review
(`reviewed=True`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .hypothesis import FactorDef, FactorHypothesis


@dataclass(frozen=True)
class FactorSpec:
    name: str
    source_field: str   # column in factor_panel
    direction: str      # long_high / long_low
    category: str       # momentum / reversal / volatility / liquidity / technical / value / quality
    rationale: str
    reviewed: bool = True
    needs_fundamentals: bool = False


DEFAULT_FACTOR_LIBRARY: List[FactorSpec] = [
    FactorSpec("ret_20d", "ret_20d", "long_high", "momentum", "1-month price momentum"),
    FactorSpec("ret_60d", "ret_60d", "long_high", "momentum", "3-month price momentum"),
    FactorSpec("mom_120_20", "mom_120_20", "long_high", "momentum", "12-1 momentum, skips last month to avoid short reversal"),
    FactorSpec("ret_5d", "ret_5d", "long_low", "reversal", "short-term reversal: recent losers bounce"),
    FactorSpec("vol_20d", "vol_20d", "long_low", "volatility", "low-volatility premium (1m)"),
    FactorSpec("vol_60d", "vol_60d", "long_low", "volatility", "low-volatility premium (3m)"),
    FactorSpec("turnover_rate", "turnover_rate", "long_low", "liquidity", "low-turnover / illiquidity premium"),
    FactorSpec("amt_20d", "amt_20d", "long_low", "liquidity", "low-amount illiquidity premium"),
    FactorSpec("px_to_ma20", "px_to_ma20", "long_high", "technical", "price above 20d MA = trend"),
    FactorSpec("px_to_ma60", "px_to_ma60", "long_high", "technical", "price above 60d MA = trend"),
    # intraday volatility (uses high-low range, more efficient than close-to-close)
    FactorSpec("parkinson_vol_20d", "parkinson_vol_20d", "long_low", "volatility", "Parkinson intraday vol: low-vol premium via high-low range"),
    # industry momentum (cross-sectional industry avg return)
    FactorSpec("industry_mom_20d", "industry_mom_20d", "long_high", "industry", "industry 20d momentum: sector rotation signal"),
    # value/quality require the fundamentals tables (B1) joined into factor_panel
    FactorSpec("ep", "ep", "long_high", "value", "earnings yield 1/PE: cheap = high", needs_fundamentals=True),
    FactorSpec("bp", "bp", "long_high", "value", "book yield 1/PB: cheap = high", needs_fundamentals=True),
    FactorSpec("size_inv", "size_inv", "long_high", "size", "inverse market cap: small-size premium (controlled)", needs_fundamentals=True),
    FactorSpec("roe", "roe", "long_high", "quality", "return on equity: profitable firms", needs_fundamentals=True),
    # Strategy D: volume-price microstructure factors
    FactorSpec("vol_price_corr_20d", "vol_price_corr_20d", "long_low", "volume_price", "vol-price corr: negative = quiet accumulation (bullish)"),
    FactorSpec("turnover_change_5_20", "turnover_change_5_20", "long_low", "volume_price", "turnover acceleration: fading attention = contrarian buy"),
    FactorSpec("amplitude_avg_20d", "amplitude_avg_20d", "long_low", "volume_price", "low amplitude = institutional control, high = retail driven"),
    # Strategy E: classic technical indicators (from reference project)
    FactorSpec("bias_20", "bias_20", "long_low", "technical", "20d BIAS: price deviation from MA, low = oversold reversal"),
    FactorSpec("rsi_14", "rsi_14", "long_low", "technical", "14d RSI: low = oversold, mean-reversion signal"),
    FactorSpec("turnover_std_20d", "turnover_std_20d", "long_low", "liquidity", "turnover volatility: stable turnover = institutional"),
    FactorSpec("volume_ma_ratio_5_20", "volume_ma_ratio_5_20", "long_low", "volume_price", "vol surge ratio: low = volume drying up (contrarian)"),
    FactorSpec("rsv_9", "rsv_9", "long_low", "technical", "9d RSV (raw stochastic): low = oversold"),
    # Strategy P: RSV at alternative lookback windows (oversold pullback filter)
    FactorSpec("rsv_5", "rsv_5", "long_low", "technical", "5d RSV: short-term oversold pullback"),
    FactorSpec("rsv_3", "rsv_3", "long_low", "technical", "3d RSV: very short-term oversold pullback"),
    FactorSpec("rsv_7", "rsv_7", "long_low", "technical", "7d RSV: short-term oversold pullback"),
    FactorSpec("rsv_14", "rsv_14", "long_low", "technical", "14d RSV: medium-term oversold pullback"),
    FactorSpec("rsv_20", "rsv_20", "long_low", "technical", "20d RSV: monthly oversold pullback"),
    FactorSpec("dif", "dif", "long_high", "technical", "MACD DIF: EMA12-EMA26, trend direction"),
    FactorSpec("macd_hist", "macd_hist", "long_high", "technical", "MACD histogram: momentum strength"),
    FactorSpec("k_value", "k_value", "long_low", "technical", "KD K-value: low = oversold"),
    FactorSpec("d_value", "d_value", "long_low", "technical", "KD D-value: low = oversold, slower signal"),
    # Strategy L: higher-moment & true-range factors (new Alpha dimensions)
    FactorSpec("ret_10d", "ret_10d", "long_high", "momentum", "2-week price momentum (intermediate window)"),
    FactorSpec("ret_15d", "ret_15d", "long_high", "momentum", "3-week price momentum (intermediate window)"),
    FactorSpec("ret_skew_20d", "ret_skew_20d", "long_low", "volatility", "return skewness: low skew = stable uptrend, high skew = lottery-like"),
    FactorSpec("atr_20d", "atr_20d", "long_low", "volatility", "ATR/price: true-range vol incl overnight gaps, low = controlled"),
    # Strategy S: Bollinger & higher-moment factors (new Alpha exploration)
    FactorSpec("boll_pct_b_20", "boll_pct_b_20", "long_low", "technical", "20d Bollinger %B: low = below lower band = oversold (mean-reversion)"),
    FactorSpec("boll_pct_b_10", "boll_pct_b_10", "long_low", "technical", "10d Bollinger %B: short-term oversold via stddev bands"),
    FactorSpec("drawdown_5d", "drawdown_5d", "long_low", "technical", "5d drawdown from peak: deep pullback = buy-the-dip signal"),
    FactorSpec("kurtosis_20d", "kurtosis_20d", "long_low", "volatility", "20d excess kurtosis: low = thin tails = predictable, institutional"),
    FactorSpec("boll_width_20", "boll_width_20", "long_low", "volatility", "20d Bollinger width: narrow = consolidation, low = quiet before breakout"),
    # Strategy T: window variants for deep-dive
    FactorSpec("boll_width_5", "boll_width_5", "long_low", "volatility", "5d Bollinger width: very short-term vol squeeze"),
    FactorSpec("boll_width_10", "boll_width_10", "long_low", "volatility", "10d Bollinger width: short-term vol squeeze"),
    FactorSpec("boll_pct_b_5", "boll_pct_b_5", "long_low", "technical", "5d Bollinger %B: very short-term oversold"),
    FactorSpec("boll_pct_b_7", "boll_pct_b_7", "long_low", "technical", "7d Bollinger %B: short-term oversold"),
    FactorSpec("drawdown_3d", "drawdown_3d", "long_low", "technical", "3d drawdown from peak: very short-term pullback"),
    FactorSpec("drawdown_7d", "drawdown_7d", "long_low", "technical", "7d drawdown from peak: short-term pullback"),
    FactorSpec("drawdown_10d", "drawdown_10d", "long_low", "technical", "10d drawdown from peak: medium-term pullback"),
    # Strategy Z: fine-tuned windows around champion dd3_rsv7 (IR=1.370)
    FactorSpec("rsv_6", "rsv_6", "long_low", "technical", "6d RSV: fine-tuned around rsv7/rsv9 sweet spot"),
    FactorSpec("rsv_8", "rsv_8", "long_low", "technical", "8d RSV: fine-tuned around rsv7/rsv9 sweet spot"),
    FactorSpec("drawdown_2d", "drawdown_2d", "long_low", "technical", "2d drawdown from peak: very short-term pullback"),
    FactorSpec("drawdown_4d", "drawdown_4d", "long_low", "technical", "4d drawdown from peak: short-term pullback"),
    # Strategy LL: drawdown_6d (fill gap between dd5 and dd7)
    FactorSpec("drawdown_6d", "drawdown_6d", "long_low", "technical", "6d drawdown from peak: medium-term pullback (between dd5 MDD champion and dd7)"),
    # Strategy MM: drawdown_8d (longer pullback for even lower MDD)
    FactorSpec("drawdown_8d", "drawdown_8d", "long_low", "technical", "8d drawdown from peak: longer-term pullback (test if dd8 further reduces MDD vs dd6)"),
    # Strategy BB: volume-weighted oscillators (new Alpha dimension)
    FactorSpec("mfi_14", "mfi_14", "long_low", "volume_price", "14d MFI: volume-weighted RSI, low = money outflow = oversold with volume confirmation"),
    FactorSpec("obv_change_20", "obv_change_20", "long_low", "volume_price", "20d OBV change / avg volume: low = distribution/selling pressure"),
    FactorSpec("rsi_7", "rsi_7", "long_low", "technical", "7d RSI: shorter window, more responsive oversold signal than rsi_14"),
    # Strategy CC: MFI and OBV window variants
    FactorSpec("mfi_7", "mfi_7", "long_low", "volume_price", "7d MFI: shorter window, more responsive money flow signal"),
    FactorSpec("mfi_10", "mfi_10", "long_low", "volume_price", "10d MFI: medium window money flow signal"),
    FactorSpec("mfi_20", "mfi_20", "long_low", "volume_price", "20d MFI: longer window, smoother money flow signal"),
    FactorSpec("obv_change_10", "obv_change_10", "long_low", "volume_price", "10d OBV change / avg volume: shorter distribution signal"),
    # Strategy DD: Fine-tune MFI windows around champion mfi_7 (IR=1.384)
    FactorSpec("mfi_5", "mfi_5", "long_low", "volume_price", "5d MFI: very short-term money flow, most responsive oversold signal"),
    FactorSpec("mfi_6", "mfi_6", "long_low", "volume_price", "6d MFI: fine-tuned around mfi_7 sweet spot"),
    FactorSpec("mfi_8", "mfi_8", "long_low", "volume_price", "8d MFI: fine-tuned around mfi_7 sweet spot"),
    # Strategy EE: Chaikin Money Flow (CMF) — volume-weighted CLV, alternative to MFI
    FactorSpec("cmf_7", "cmf_7", "long_low", "volume_price", "7d CMF: Chaikin Money Flow, CLV-weighted volume signal (short window)"),
    FactorSpec("cmf_10", "cmf_10", "long_low", "volume_price", "10d CMF: medium window Chaikin Money Flow"),
    FactorSpec("cmf_14", "cmf_14", "long_low", "volume_price", "14d CMF: standard window Chaikin Money Flow"),
    FactorSpec("cmf_20", "cmf_20", "long_low", "volume_price", "20d CMF: long window Chaikin Money Flow"),
]


def library_index(library: List[FactorSpec] | None = None) -> Dict[str, FactorSpec]:
    return {f.name: f for f in (library or DEFAULT_FACTOR_LIBRARY)}


def build_hypothesis(
    names: List[str],
    market: str = "cn",
    sector_neutral: bool = False,
    library: List[FactorSpec] | None = None,
) -> FactorHypothesis:
    """Construct a FactorHypothesis from reviewed library factors selected by name."""
    idx = library_index(library)
    factors: List[FactorDef] = []
    for n in names:
        spec = idx.get(n)
        if spec is None:
            raise KeyError(f"factor {n!r} not in library")
        if not spec.reviewed:
            raise ValueError(f"factor {n!r} is not human-reviewed yet; cannot enter the loop")
        factors.append(FactorDef(name=spec.name, source_field=spec.source_field, direction=spec.direction))
    return FactorHypothesis(market=market, factors=factors, sector_neutral=sector_neutral)


def available_factors(include_fundamentals: bool = True, library: List[FactorSpec] | None = None) -> List[str]:
    return [
        f.name for f in (library or DEFAULT_FACTOR_LIBRARY)
        if f.reviewed and (include_fundamentals or not f.needs_fundamentals)
    ]
