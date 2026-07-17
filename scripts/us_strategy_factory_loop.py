from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import us_universe


@dataclass(frozen=True)
class FactorSpec:
    name: str
    direction: str
    category: str


@dataclass(frozen=True)
class EvalContext:
    dates: pd.Series
    by_date: dict[pd.Timestamp, pd.DataFrame]


@dataclass(frozen=True)
class PeriodSlice:
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    data: pd.DataFrame
    benchmark_ret: float


FACTOR_LIBRARY = [
    FactorSpec("ret_20d", "high", "momentum"),
    FactorSpec("ret_60d", "high", "momentum"),
    FactorSpec("ret_120d", "high", "momentum"),
    FactorSpec("mom_252_21", "high", "momentum"),
    FactorSpec("px_to_ma20", "high", "trend"),
    FactorSpec("px_to_ma60", "high", "trend"),
    FactorSpec("ma20_above_ma60", "high", "trend"),
    FactorSpec("macd_hist", "high", "trend"),
    FactorSpec("ret_5d", "low", "reversal"),
    FactorSpec("ret_10d", "low", "reversal"),
    FactorSpec("drawdown_5d", "low", "reversal"),
    FactorSpec("drawdown_10d", "low", "reversal"),
    FactorSpec("drawdown_20d", "low", "reversal"),
    FactorSpec("boll_pct_b_10", "low", "oscillator"),
    FactorSpec("boll_pct_b_20", "low", "oscillator"),
    FactorSpec("rsi_7", "low", "oscillator"),
    FactorSpec("rsi_14", "low", "oscillator"),
    FactorSpec("rsv_9", "low", "oscillator"),
    FactorSpec("mfi_7", "low", "volume_price"),
    FactorSpec("mfi_14", "low", "volume_price"),
    FactorSpec("cmf_10", "low", "volume_price"),
    FactorSpec("cmf_20", "low", "volume_price"),
    FactorSpec("obv_change_20", "low", "volume_price"),
    FactorSpec("volume_ma_ratio_5_20", "low", "volume_price"),
    FactorSpec("overnight_gap_1d", "low", "microstructure"),
    FactorSpec("intraday_ret_1d", "low", "microstructure"),
    FactorSpec("close_pos_20d", "low", "microstructure"),
    FactorSpec("range_pct_5d", "low", "microstructure"),
    FactorSpec("vol_20d", "low", "risk"),
    FactorSpec("vol_60d", "low", "risk"),
    FactorSpec("atr_20d", "low", "risk"),
    FactorSpec("parkinson_vol_20d", "low", "risk"),
    FactorSpec("ret_skew_20d", "low", "risk"),
    FactorSpec("kurtosis_20d", "low", "risk"),
    FactorSpec("dollar_volume_20d", "high", "liquidity"),
    FactorSpec("turnover_stability_20d", "high", "liquidity"),
]


def zscore_by_date(frame: pd.DataFrame, column: str) -> pd.Series:
    g = frame.groupby("trade_date")[column]
    mean = g.transform("mean")
    std = g.transform("std").replace(0, np.nan)
    return ((frame[column] - mean) / std).fillna(0.0)


def max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    dd = values / values.cummax() - 1.0
    return abs(float(dd.min()))


def annualized(total_return: float, start: str, end: str) -> float:
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    if days <= 0 or total_return <= -1:
        return float("nan")
    return (1.0 + total_return) ** (365.25 / days) - 1.0


def information_ratio(excess_returns: pd.Series, periods_per_year: float) -> float:
    s = pd.to_numeric(excess_returns, errors="coerce").dropna()
    sd = s.std(ddof=0)
    if len(s) < 2 or sd <= 0:
        return 0.0
    return float(s.mean() / sd * math.sqrt(periods_per_year))


def spearman_corr(left: pd.Series, right: pd.Series) -> float:
    frame = pd.concat([left, right], axis=1).dropna()
    if len(frame) < 3:
        return 0.0
    ranked = frame.rank(method="average")
    corr = ranked.iloc[:, 0].corr(ranked.iloc[:, 1])
    return float(corr) if np.isfinite(corr) else 0.0


def average_year_ir(rows: pd.DataFrame, periods_per_year: float) -> float:
    if rows.empty:
        return 0.0
    tmp = rows.copy()
    tmp["year"] = pd.to_datetime(tmp["entry_date"]).dt.year
    values = [information_ratio(group["excess_ret"], periods_per_year) for _, group in tmp.groupby("year") if len(group) >= 3]
    return float(np.mean(values)) if values else 0.0


def load_panel(
    raw_dir: Path,
    universe_mode: str = "current_snapshot",
    pit_membership_path: Path | None = None,
    pit_universes: list[str] | None = None,
) -> tuple[pd.DataFrame, set[str], dict, pd.DataFrame | None]:
    prices = pd.read_parquet(raw_dir / "us_market_daily.parquet")
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])
    prices = prices.sort_values(["symbol", "trade_date"]).dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce").fillna(0.0)
    prices["dollar_volume"] = prices["close"] * prices["volume"]
    g = prices.groupby("symbol", group_keys=False)
    prices["ret_1d"] = g["close"].pct_change()
    previous_close = g["close"].shift(1)
    prices["overnight_gap_1d"] = prices["open"] / previous_close - 1.0
    prices["intraday_ret_1d"] = prices["close"] / prices["open"] - 1.0
    bad_symbols = set(prices.loc[prices["ret_1d"].abs() > 0.8, "symbol"].unique())

    for window in [5, 10, 20, 60, 120]:
        prices[f"ret_{window}d"] = g["close"].pct_change(window)
    prices["mom_252_21"] = g["close"].shift(21) / g["close"].shift(252) - 1.0
    for window in [7, 10, 14, 20, 60]:
        if window in [20, 60]:
            prices[f"vol_{window}d"] = g["ret_1d"].rolling(window, min_periods=window).std().reset_index(level=0, drop=True) * math.sqrt(252)
            prices[f"ma_{window}"] = g["close"].rolling(window, min_periods=window).mean().reset_index(level=0, drop=True)
    prices["ma_12"] = g["close"].ewm(span=12, adjust=False).mean().reset_index(level=0, drop=True)
    prices["ma_26"] = g["close"].ewm(span=26, adjust=False).mean().reset_index(level=0, drop=True)
    prices["macd_hist"] = prices["ma_12"] - prices["ma_26"]
    prices["px_to_ma20"] = prices["close"] / prices["ma_20"] - 1.0
    prices["px_to_ma60"] = prices["close"] / prices["ma_60"] - 1.0
    prices["ma20_above_ma60"] = prices["ma_20"] / prices["ma_60"] - 1.0
    prices["dollar_volume_20d"] = g["dollar_volume"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
    prices["turnover_stability_20d"] = -g["volume"].rolling(20, min_periods=20).std().reset_index(level=0, drop=True) / (
        g["volume"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True).replace(0, np.nan)
    )

    true_range = pd.concat(
        [prices["high"] - prices["low"], (prices["high"] - previous_close).abs(), (prices["low"] - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    prices["atr_20d"] = true_range.groupby(prices["symbol"]).rolling(20, min_periods=20).mean().reset_index(level=0, drop=True) / prices["close"]
    prices["parkinson_vol_20d"] = (
        (np.log(prices["high"] / prices["low"]) ** 2)
        .groupby(prices["symbol"])
        .rolling(20, min_periods=20)
        .mean()
        .reset_index(level=0, drop=True)
        .pow(0.5)
        * math.sqrt(252 / (4 * math.log(2)))
    )
    prices["ret_skew_20d"] = g["ret_1d"].rolling(20, min_periods=20).skew().reset_index(level=0, drop=True)
    prices["kurtosis_20d"] = g["ret_1d"].rolling(20, min_periods=20).kurt().reset_index(level=0, drop=True)

    for window in [5, 10, 20]:
        high = g["high"].rolling(window, min_periods=window).max().reset_index(level=0, drop=True)
        low = g["low"].rolling(window, min_periods=window).min().reset_index(level=0, drop=True)
        prices[f"drawdown_{window}d"] = prices["close"] / high - 1.0
        if window == 5:
            prices["range_pct_5d"] = (high - low) / prices["close"]
        ma = g["close"].rolling(window, min_periods=window).mean().reset_index(level=0, drop=True)
        sd = g["close"].rolling(window, min_periods=window).std().reset_index(level=0, drop=True)
        prices[f"boll_pct_b_{window}"] = (prices["close"] - (ma - 2 * sd)) / (4 * sd.replace(0, np.nan))
        if window == 10:
            prices["rsv_9"] = (prices["close"] - low) / (high - low).replace(0, np.nan)
        if window == 20:
            prices["close_pos_20d"] = (prices["close"] - low) / (high - low).replace(0, np.nan)

    for window in [7, 14]:
        delta = g["close"].diff()
        gain = delta.clip(lower=0).groupby(prices["symbol"]).rolling(window, min_periods=window).mean().reset_index(level=0, drop=True)
        loss = (-delta.clip(upper=0)).groupby(prices["symbol"]).rolling(window, min_periods=window).mean().reset_index(level=0, drop=True)
        prices[f"rsi_{window}"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    typical = (prices["high"] + prices["low"] + prices["close"]) / 3.0
    raw_flow = typical * prices["volume"]
    tp_delta = typical.groupby(prices["symbol"]).diff()
    for window in [7, 14]:
        pos = raw_flow.where(tp_delta > 0, 0.0).groupby(prices["symbol"]).rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        neg = raw_flow.where(tp_delta < 0, 0.0).groupby(prices["symbol"]).rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        prices[f"mfi_{window}"] = 100 - 100 / (1 + pos / neg.replace(0, np.nan))

    clv = ((prices["close"] - prices["low"]) - (prices["high"] - prices["close"])) / (prices["high"] - prices["low"]).replace(0, np.nan)
    mfv = clv.fillna(0.0) * prices["volume"]
    for window in [10, 20]:
        prices[f"cmf_{window}"] = mfv.groupby(prices["symbol"]).rolling(window, min_periods=window).sum().reset_index(level=0, drop=True) / (
            prices["volume"].groupby(prices["symbol"]).rolling(window, min_periods=window).sum().reset_index(level=0, drop=True).replace(0, np.nan)
        )
    direction = np.sign(g["close"].diff()).fillna(0.0)
    obv = (direction * prices["volume"]).groupby(prices["symbol"]).cumsum()
    prices["obv_change_20"] = obv.groupby(prices["symbol"]).diff(20) / (
        g["volume"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True).replace(0, np.nan)
    )
    prices["volume_ma_ratio_5_20"] = (
        g["volume"].rolling(5, min_periods=5).mean().reset_index(level=0, drop=True)
        / g["volume"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True).replace(0, np.nan)
    )

    factor_names = [f.name for f in FACTOR_LIBRARY]
    mask = prices[factor_names + ["open", "close"]].notna().all(axis=1)
    mask &= (
        (prices["close"] >= 5)
        & (prices["dollar_volume_20d"] >= 10_000_000)
        & (~prices["symbol"].isin(bad_symbols))
    )
    for column in ["ret_5d", "ret_10d", "ret_20d", "ret_60d", "ret_120d", "mom_252_21"]:
        mask &= prices[column].between(-0.8, 3.0)
    for column in ["open", "close", *factor_names]:
        prices[column] = prices[column].astype("float32")
    base_universe_membership: pd.DataFrame | None = None
    if universe_mode == "dynamic_liquidity":
        base_universe_membership = us_universe.build_dynamic_liquidity_membership(
            prices.loc[mask, ["symbol", "trade_date", "close", "dollar_volume_20d"]].copy(),
            min_price=5.0,
            min_dollar_volume_20d=10_000_000,
        )

    panel = prices.loc[mask, ["symbol", "trade_date", "open", "close", *factor_names]].copy()
    pit_rows = 0
    if universe_mode == "pit":
        if pit_membership_path is None:
            raise ValueError("pit_membership_path is required when universe_mode=pit")
        membership = us_universe.load_pit_membership(
            pit_membership_path,
            source=pit_membership_path.stem,
            as_of_date=pd.Timestamp.now(tz="UTC").date().isoformat(),
        )
        pit_rows = int(len(membership))
        panel = us_universe.filter_panel_by_pit(panel, membership, universe_names=pit_universes)
        base_universe_membership = membership
    numeric_cols = ["open", "close", *factor_names]
    panel[numeric_cols] = panel[numeric_cols].astype("float32")

    for spec in FACTOR_LIBRARY:
        signed = panel[spec.name] if spec.direction == "high" else -panel[spec.name]
        grouped = signed.groupby(panel["trade_date"])
        mean = grouped.transform("mean")
        std = grouped.transform("std").replace(0, np.nan)
        panel[f"score_{spec.name}"] = ((signed - mean) / std).fillna(0.0).astype("float32")
    score_cols = [f"score_{name}" for name in factor_names]
    panel = panel[["symbol", "trade_date", "open", "close", *score_cols]].copy()
    manifest = {
        "rows": int(len(panel)),
        "symbols": int(panel["symbol"].nunique()),
        "bad_symbols": sorted(bad_symbols),
        "factor_count": len(factor_names),
        "universe_mode": universe_mode,
        "universe_status": {
            "current_snapshot": "blocked_current_snapshot_only",
            "dynamic_liquidity": "survivorship_reduced_not_pit",
            "pit": "pit_ready",
        }[universe_mode],
        "pit_membership_rows": pit_rows,
        "pit_universes": pit_universes or [],
    }
    return panel, bad_symbols, manifest, base_universe_membership


def candidate_hypotheses(limit: int) -> list[tuple[str, tuple[FactorSpec, ...]]]:
    by_cat: dict[str, list[FactorSpec]] = {}
    for factor in FACTOR_LIBRARY:
        by_cat.setdefault(factor.category, []).append(factor)
    templates = [
        ("qm", ["momentum", "momentum", "trend", "risk", "liquidity"]),
        ("qmv", ["momentum", "trend", "volume_price", "risk", "liquidity"]),
        ("mr", ["reversal", "oscillator", "volume_price", "risk", "liquidity"]),
        ("pulltrend", ["reversal", "trend", "momentum", "risk", "liquidity"]),
        ("balanced", ["momentum", "reversal", "trend", "volume_price", "risk", "liquidity"]),
        ("defensive", ["momentum", "risk", "risk", "liquidity", "trend"]),
        ("microrev", ["microstructure", "reversal", "volume_price", "risk", "liquidity"]),
        ("microtrend", ["microstructure", "trend", "momentum", "risk", "liquidity"]),
    ]
    out: list[tuple[str, tuple[FactorSpec, ...]]] = []
    seen = set()
    iterators = []
    for prefix, cats in templates:
        pools = [by_cat[c] for c in cats]
        iterators.append((prefix, iter(itertools.product(*pools))))
    while len(out) < limit and iterators:
        next_iterators = []
        for prefix, iterator in iterators:
            picked = False
            for combo in iterator:
                names = tuple(dict.fromkeys(f.name for f in combo))
                if len(names) < 3 or len(names) > 8 or names in seen:
                    continue
                seen.add(names)
                idx = {f.name: f for f in combo}
                out.append((f"{prefix}_{'_'.join(names)}", tuple(idx[n] for n in names)))
                picked = True
                break
            if len(out) >= limit:
                return out
            if picked:
                next_iterators.append((prefix, iterator))
        iterators = next_iterators
    return out


def precompute_factor_ics(panel: pd.DataFrame, start: str, end: str, horizons: list[int]) -> dict[int, dict[str, float]]:
    dev = panel[(panel["trade_date"] >= pd.Timestamp(start)) & (panel["trade_date"] <= pd.Timestamp(end))].copy()
    out: dict[int, dict[str, float]] = {}
    for horizon in horizons:
        fwd = dev.groupby("symbol")["close"].shift(-horizon) / dev["close"] - 1.0
        values = {}
        for factor in FACTOR_LIBRARY:
            corr = spearman_corr(dev[f"score_{factor.name}"], fwd)
            values[factor.name] = max(0.0, float(corr) if np.isfinite(corr) else 0.0)
        out[horizon] = values
    return out


def ic_weights_from_values(factors: tuple[FactorSpec, ...], ic_values: dict[str, float]) -> dict[str, float]:
    values = {}
    for factor in factors:
        values[factor.name] = ic_values.get(factor.name, 0.0)
    if sum(values.values()) <= 0:
        return {factor.name: 1.0 / len(factors) for factor in factors}
    total = sum(values.values())
    equal = 1.0 / len(factors)
    weights = {name: 0.70 * (value / total) + 0.30 * equal for name, value in values.items()}
    return cap_weights(weights, max_weight=0.45)


def cap_weights(weights: dict[str, float], max_weight: float) -> dict[str, float]:
    capped = dict(weights)
    for _ in range(len(capped) + 1):
        excess = sum(max(0.0, value - max_weight) for value in capped.values())
        if excess <= 1e-12:
            break
        capped = {name: min(value, max_weight) for name, value in capped.items()}
        receivers = [name for name, value in capped.items() if value < max_weight - 1e-12]
        if not receivers:
            break
        receiver_total = sum(capped[name] for name in receivers)
        if receiver_total <= 0:
            add = excess / len(receivers)
            for name in receivers:
                capped[name] += add
        else:
            for name in receivers:
                capped[name] += excess * capped[name] / receiver_total
    total = sum(capped.values())
    return {name: value / total for name, value in capped.items()}


def score_panel(panel: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    total = pd.Series(0.0, index=panel.index)
    for name, weight in weights.items():
        total += weight * panel[f"score_{name}"]
    return total


def make_eval_context(panel: pd.DataFrame) -> EvalContext:
    dates = pd.Series(sorted(pd.Timestamp(d) for d in panel["trade_date"].unique()))
    by_date = {pd.Timestamp(date): frame for date, frame in panel.groupby("trade_date", sort=False)}
    return EvalContext(dates=dates, by_date=by_date)


def make_period_slices(context: EvalContext, rebalance_days: int, start: str, end: str, live: bool = False) -> list[PeriodSlice]:
    dates = context.dates
    signal_dates = [pd.Timestamp(d) for d in dates[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))].iloc[::rebalance_days]]
    all_dates = context.dates
    score_cols = [f"score_{factor.name}" for factor in FACTOR_LIBRARY]
    periods = []
    for idx, signal_date in enumerate(signal_dates):
        future = all_dates[all_dates > signal_date]
        if future.empty:
            continue
        entry_date = pd.Timestamp(future.iloc[0])
        if live:
            exit_date = pd.Timestamp("2026-07-10")
            if entry_date > exit_date:
                continue
            exit_col = "close"
        else:
            if idx + 1 >= len(signal_dates):
                break
            future_exit = all_dates[all_dates > signal_dates[idx + 1]]
            if future_exit.empty:
                continue
            exit_date = pd.Timestamp(future_exit.iloc[0])
            exit_col = "open"
        universe = context.by_date.get(signal_date)
        entry = context.by_date.get(entry_date)
        exit_frame = context.by_date.get(exit_date)
        if universe is None or entry is None or exit_frame is None:
            continue
        frame = universe[["symbol", *score_cols]].merge(entry[["symbol", "open"]].rename(columns={"open": "entry"}), on="symbol")
        frame = frame.merge(exit_frame[["symbol", exit_col]].rename(columns={exit_col: "exit"}), on="symbol")
        frame = frame[(frame["entry"] > 0) & (frame["exit"] > 0)].copy()
        if len(frame) < 100:
            continue
        frame["asset_ret"] = frame["exit"] / frame["entry"] - 1.0 - 0.002
        benchmark_ret = float(frame["asset_ret"].mean())
        periods.append(
            PeriodSlice(
                signal_date=signal_date,
                entry_date=entry_date,
                exit_date=exit_date,
                data=frame[["symbol", "asset_ret", *score_cols]],
                benchmark_ret=benchmark_ret,
            )
        )
        if live:
            break
    return periods


def evaluate_periods(periods: list[PeriodSlice], weights: dict[str, float], top_n: int, rebalance_days: int) -> tuple[dict, pd.DataFrame]:
    rows = []
    equity = 1.0
    benchmark = 1.0
    for period in periods:
        scores = score_panel(period.data, weights)
        picks = scores.nlargest(top_n).index
        trade = period.data.loc[picks]
        if len(trade) < max(5, top_n // 3):
            continue
        strategy_ret = float(trade["asset_ret"].mean())
        benchmark_ret = period.benchmark_ret
        equity *= 1 + strategy_ret
        benchmark *= 1 + benchmark_ret
        rows.append(
            {
                "signal_date": period.signal_date.date().isoformat(),
                "entry_date": period.entry_date.date().isoformat(),
                "exit_date": period.exit_date.date().isoformat(),
                "strategy_ret": strategy_ret,
                "benchmark_ret": benchmark_ret,
                "excess_ret": strategy_ret - benchmark_ret,
                "equity": equity,
                "benchmark_equity": benchmark,
                "n": int(len(trade)),
                "bench_n": int(len(period.data)),
                "symbols": ",".join(trade["symbol"].tolist()),
            }
        )
    curve = pd.DataFrame(rows)
    if curve.empty:
        return {}, curve
    periods_per_year = 252 / rebalance_days
    total_return = equity - 1.0
    benchmark_return = benchmark - 1.0
    excess_return = equity / benchmark - 1.0
    summary = {
        "periods": int(len(curve)),
        "start": curve["entry_date"].iloc[0],
        "end": curve["exit_date"].iloc[-1],
        "total_return": total_return,
        "benchmark_return": benchmark_return,
        "excess_return": excess_return,
        "annual_return": annualized(total_return, curve["entry_date"].iloc[0], curve["exit_date"].iloc[-1]),
        "benchmark_annual": annualized(benchmark_return, curve["entry_date"].iloc[0], curve["exit_date"].iloc[-1]),
        "excess_annual": annualized(excess_return, curve["entry_date"].iloc[0], curve["exit_date"].iloc[-1]),
        "mdd": max_drawdown(curve["equity"]),
        "benchmark_mdd": max_drawdown(curve["benchmark_equity"]),
        "ir": information_ratio(curve["excess_ret"], periods_per_year),
        "avg_ir": average_year_ir(curve, periods_per_year),
        "win_excess": float((curve["excess_ret"] > 0).mean()),
    }
    return summary, curve


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
    parser.add_argument("--out-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-factory")
    parser.add_argument("--candidate-limit", type=int, default=900)
    parser.add_argument("--universe-mode", choices=["current_snapshot", "dynamic_liquidity", "pit"], default="current_snapshot")
    parser.add_argument("--pit-membership")
    parser.add_argument("--pit-universes", default="")
    args = parser.parse_args()
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ["factory_*", "dev_*.csv", "holdout_*.csv", "live_*.csv"]:
        for path in out_dir.glob(pattern):
            if path.is_file():
                path.unlink()

    pit_universes = [item.strip() for item in args.pit_universes.split(",") if item.strip()]
    panel, _, panel_manifest, membership = load_panel(
        raw_dir,
        universe_mode=args.universe_mode,
        pit_membership_path=Path(args.pit_membership) if args.pit_membership else None,
        pit_universes=pit_universes or None,
    )
    if membership is not None:
        membership.to_csv(out_dir / f"universe_membership_{args.universe_mode}.csv", index=False)
    eval_context = make_eval_context(panel)
    candidates = candidate_hypotheses(args.candidate_limit)
    rows = []
    curves_to_write: list[tuple[str, str, pd.DataFrame]] = []
    top_choices = [5, 7, 10, 20]
    rebalance_choices = [5, 10, 20]
    factor_ics = precompute_factor_ics(panel, "2023-06-30", "2025-06-29", rebalance_choices)
    period_sets = {
        rebalance_days: {
            "dev": make_period_slices(eval_context, rebalance_days, "2023-06-30", "2025-06-29"),
            "holdout": make_period_slices(eval_context, rebalance_days, "2025-06-30", "2026-06-29"),
            "live": make_period_slices(eval_context, rebalance_days, "2026-06-30", "2026-06-30", live=True),
        }
        for rebalance_days in rebalance_choices
    }
    for candidate_id, factors in candidates:
        factor_names = [f.name for f in factors]
        for rebalance_days in rebalance_choices:
            weights = ic_weights_from_values(factors, factor_ics[rebalance_days])
            best_dev = None
            best_dev_curve = None
            best_top = None
            for top_n in top_choices:
                dev, dev_curve = evaluate_periods(period_sets[rebalance_days]["dev"], weights, top_n, rebalance_days)
                if not dev:
                    continue
                score = dev["ir"] * 0.40 + dev["excess_annual"] * 0.35 + dev["win_excess"] * 0.20 - dev["mdd"] * 0.05
                if best_dev is None or score > best_dev["dev_score"]:
                    best_dev = {**dev, "dev_score": score}
                    best_dev_curve = dev_curve
                    best_top = top_n
            if best_dev is None or best_top is None:
                continue
            holdout, holdout_curve = evaluate_periods(period_sets[rebalance_days]["holdout"], weights, best_top, rebalance_days)
            live, live_curve = evaluate_periods(period_sets[rebalance_days]["live"], weights, best_top, rebalance_days)
            if not holdout or not live:
                continue
            row = {
                "candidate_id": candidate_id[:180],
                "factors": ";".join(factor_names),
                "weights": json.dumps(weights, sort_keys=True),
                "max_factor_weight": max(weights.values()),
                "effective_factor_count": 1.0 / sum(value * value for value in weights.values()),
                "top_n": best_top,
                "rebalance_days": rebalance_days,
                **{f"dev_{k}": v for k, v in best_dev.items() if k != "dev_score"},
                "dev_score": best_dev["dev_score"],
                **{f"holdout_{k}": v for k, v in holdout.items()},
                **{f"live_{k}": v for k, v in live.items()},
            }
            row["final_score"] = (
                row["dev_score"] * 0.35
                + row["holdout_ir"] * 0.25
                + row["holdout_excess_annual"] * 0.25
                + row["live_excess_return"] * 0.10
                - row["holdout_mdd"] * 0.05
            )
            rows.append(row)
            if row["holdout_excess_return"] > 0 and row["holdout_ir"] > 0.5 and row["live_excess_return"] > 0:
                safe_id = f"{len(curves_to_write):04d}_{candidate_id[:80]}_t{best_top}_r{rebalance_days}".replace("/", "_")
                curves_to_write.append((f"dev_{safe_id}", "dev", best_dev_curve))
                curves_to_write.append((f"holdout_{safe_id}", "holdout", holdout_curve))
                curves_to_write.append((f"live_{safe_id}", "live", live_curve))

    all_results = pd.DataFrame(rows).sort_values("final_score", ascending=False)
    qualified = all_results[
        (all_results["dev_excess_return"] > 0)
        & (all_results["dev_ir"] > 0.5)
        & (all_results["holdout_excess_return"] > 0)
        & (all_results["holdout_ir"] > 0.5)
        & (all_results["live_excess_return"] > 0)
    ].copy()
    failed = pd.DataFrame(
        [
            {"reason": "dev_failed", "count": int(((all_results["dev_excess_return"] <= 0) | (all_results["dev_ir"] <= 0.5)).sum())},
            {"reason": "holdout_failed", "count": int(((all_results["holdout_excess_return"] <= 0) | (all_results["holdout_ir"] <= 0.5)).sum())},
            {"reason": "live_failed", "count": int((all_results["live_excess_return"] <= 0).sum())},
        ]
    )
    all_results.to_csv(out_dir / "factory_all_candidates.csv", index=False)
    qualified.to_csv(out_dir / "factory_qualified_candidates.csv", index=False)
    failed.to_csv(out_dir / "factory_failed_summary.csv", index=False)
    if not qualified.empty:
        try:
            qualified.head(100).to_excel(out_dir / "factory_qualified_top100.xlsx", index=False)
        except Exception as exc:
            (out_dir / "factory_qualified_top100.xlsx.error.txt").write_text(str(exc), encoding="utf-8")
    for filename, _, curve in curves_to_write[:60]:
        curve.to_csv(out_dir / f"{filename}.csv", index=False)
    manifest = {
        "raw_dir": str(raw_dir),
        "panel": panel_manifest,
        "universe_mode": args.universe_mode,
        "pit_membership": args.pit_membership,
        "pit_universes": pit_universes,
        "candidate_hypotheses": len(candidates),
        "evaluated_rows": int(len(all_results)),
        "qualified_rows": int(len(qualified)),
        "scheme": "dev 2023-06-30..2025-06-29 -> one-shot holdout 2025-06-30..2026-06-29 -> live proxy 2026-06-30 signal, 2026-07-01 open entry, 2026-07-10 close mark",
        "mdd_policy": "soft penalty only, not a hard rejection",
        "live_gate": "relative excess return versus equal-weight tradable universe must be positive; absolute live return may be negative in a falling tape",
        "note": "Factor weights are development-window IC weights. HPO searches only top_n and rebalance_days.",
    }
    (out_dir / "factory_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if not qualified.empty:
        print(qualified.head(20).to_string(index=False))
    else:
        print(all_results.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
