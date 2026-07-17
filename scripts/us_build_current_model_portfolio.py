from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from us_model_portfolio import cap_and_redistribute


DB = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
RAW_DIR = Path(r"E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart")
OUT_DIR = Path(r"G:\quant-agent-team-us\reports\us\live\current")
DEFAULT_DRAG_SYMBOLS = {
    "ARM",
    "ON",
    "DELL",
    "HON",
    "SNX",
    "QCOM",
    "VIRT",
    "LBRDK",
    "ALB",
    "ORCL",
    "CAR",
    "JEF",
    "CLF",
    "DUOL",
    "IBKR",
}


def _load_metadata(path: Path = RAW_DIR / "us_stock_meta.csv") -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "sector", "name"])
    metadata = pd.read_csv(path)
    return metadata[["symbol", "sector", "name"]].drop_duplicates("symbol")


def _normalize(values: pd.Series) -> pd.Series:
    values = values.astype(float).clip(lower=0)
    total = float(values.sum())
    if total <= 0:
        raise ValueError("weights must have a positive sum")
    return values / total


def _redistribute_with_caps(weights: pd.Series, caps: pd.Series, max_sector_weight: float | None, sectors: pd.Series) -> pd.Series:
    weights = _normalize(weights)
    caps = caps.reindex(weights.index).astype(float)
    if float(caps.sum()) < 1.0 - 1e-12:
        raise ValueError("symbol caps are too tight to allocate 100%")

    for _ in range(200):
        before = weights.copy()

        over_symbol = weights > caps
        if bool(over_symbol.any()):
            excess = float((weights[over_symbol] - caps[over_symbol]).sum())
            weights[over_symbol] = caps[over_symbol]
            room = (caps - weights).clip(lower=0)
            if float(room.sum()) > 0:
                weights += room / float(room.sum()) * excess

        if max_sector_weight is not None:
            sector_weights = weights.groupby(sectors).sum()
            for sector, sector_weight in sector_weights.items():
                if float(sector_weight) <= max_sector_weight + 1e-12:
                    continue
                members = sectors[sectors.eq(sector)].index
                excess = float(sector_weight) - max_sector_weight
                weights.loc[members] *= max_sector_weight / float(sector_weight)
                room = (caps - weights).clip(lower=0)
                other_members = sectors[~sectors.eq(sector)].index
                other_room = room.loc[other_members]
                if float(other_room.sum()) > 0:
                    weights.loc[other_members] += other_room / float(other_room.sum()) * excess

        weights = _normalize(weights.clip(upper=caps))
        if float((weights - before).abs().sum()) < 1e-10:
            break

    return weights


def build_model_portfolio(
    strategies: pd.DataFrame,
    holdings: pd.DataFrame,
    target_symbols: int,
    max_symbol_weight: float,
    metadata: pd.DataFrame | None = None,
    drag_symbols: Iterable[str] = DEFAULT_DRAG_SYMBOLS,
    exclude_drag_symbols: bool = False,
    max_drag_weight: float = 0.02,
    max_sector_weight: float | None = 0.30,
    max_source_strategies: int = 60,
) -> pd.DataFrame:
    pool = strategies[
        strategies["入库至今持续跑赢"].astype(bool)
        & (pd.to_numeric(strategies["实盘超基准收益"], errors="coerce") > 0)
        & (strategies["top_n_numeric"].isin([5, 7]))
    ].copy()
    if pool.empty:
        raise ValueError("no persistent outperforming 5/7 strategies available")

    pool["strategy_quality"] = (
        pd.to_numeric(pool["实盘超基准收益"], errors="coerce").clip(lower=0) * 100
        + pd.to_numeric(pool["信息比率"], errors="coerce").clip(lower=0)
        + pd.to_numeric(pool["去偏标准分"], errors="coerce").clip(lower=0) * 0.5
    )
    pool = pool.sort_values(["strategy_quality", "实盘超基准收益"], ascending=[False, False]).head(max_source_strategies)

    selected = holdings[holdings["monitor_key"].isin(set(pool["monitor_key"]))].copy()
    selected = selected.merge(
        pool[["monitor_key", "strategy_quality", "实盘超基准收益", "信息比率"]],
        on="monitor_key",
        how="inner",
    )
    selected["目标权重"] = pd.to_numeric(selected["目标权重"], errors="coerce").fillna(0).clip(lower=0)
    selected = selected[selected["目标权重"] > 0].copy()
    if selected.empty:
        raise ValueError("selected strategies have no positive holdings")

    selected["holding_score"] = selected["strategy_quality"] * selected["目标权重"]
    grouped = (
        selected.groupby("股票代码", as_index=False)
        .agg(
            raw_score=("holding_score", "sum"),
            contributing_strategies=("monitor_key", lambda values: ";".join(sorted(set(map(str, values))))),
            strategy_count=("monitor_key", "nunique"),
            avg_strategy_excess=("实盘超基准收益", "mean"),
        )
        .reset_index(drop=True)
    )
    drag_set = {symbol.upper() for symbol in drag_symbols}
    grouped["is_drag_symbol"] = grouped["股票代码"].astype(str).str.upper().isin(drag_set)
    grouped["congestion_penalty"] = grouped["strategy_count"].map(lambda count: 1.0 / math.sqrt(max(float(count), 1.0)))
    grouped["adjusted_score"] = grouped["raw_score"] * grouped["congestion_penalty"]
    grouped.loc[grouped["is_drag_symbol"], "adjusted_score"] *= 0.15

    meta = metadata.copy() if metadata is not None else _load_metadata()
    if not meta.empty:
        meta = meta.rename(columns={"symbol": "股票代码", "sector": "行业分组", "name": "股票名称"})
        grouped = grouped.merge(meta[["股票代码", "行业分组", "股票名称"]], on="股票代码", how="left")
    else:
        grouped["行业分组"] = "未知"
        grouped["股票名称"] = grouped["股票代码"]
    grouped["行业分组"] = grouped["行业分组"].fillna("未知")
    grouped["股票名称"] = grouped["股票名称"].fillna(grouped["股票代码"])

    grouped = grouped.sort_values(["adjusted_score", "raw_score"], ascending=[False, False]).copy()
    if exclude_drag_symbols and int((~grouped["is_drag_symbol"]).sum()) >= target_symbols:
        grouped = grouped[~grouped["is_drag_symbol"]].copy()
    grouped = grouped.head(target_symbols).copy()
    if len(grouped) < target_symbols:
        raise ValueError(f"only {len(grouped)} symbols available for target {target_symbols}")

    scores = grouped.set_index("股票代码")["adjusted_score"]
    if max_sector_weight is None and not bool(grouped["is_drag_symbol"].any()):
        weights = cap_and_redistribute(scores, cap=max_symbol_weight)
    else:
        caps = pd.Series(max_symbol_weight, index=scores.index, dtype=float)
        drag_index = grouped[grouped["is_drag_symbol"]].set_index("股票代码").index
        caps.loc[drag_index] = caps.loc[drag_index].clip(upper=max_drag_weight)
        sectors = grouped.set_index("股票代码")["行业分组"]
        weights = _redistribute_with_caps(scores, caps, max_sector_weight, sectors)

    grouped["目标权重"] = grouped["股票代码"].map(weights)
    grouped = grouped.sort_values(["目标权重", "adjusted_score"], ascending=[False, False]).reset_index(drop=True)
    grouped.insert(0, "排名", range(1, len(grouped) + 1))
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-symbols", type=int, default=20)
    parser.add_argument("--max-symbol-weight", type=float, default=0.08)
    parser.add_argument("--max-drag-weight", type=float, default=0.02)
    parser.add_argument("--max-sector-weight", type=float, default=0.30)
    parser.add_argument("--exclude-drag-symbols", action="store_true")
    parser.add_argument("--date", default="20260716")
    args = parser.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    try:
        strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
        holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()

    portfolio = build_model_portfolio(
        strategies,
        holdings,
        args.target_symbols,
        args.max_symbol_weight,
        metadata=_load_metadata(),
        exclude_drag_symbols=args.exclude_drag_symbols,
        max_drag_weight=args.max_drag_weight,
        max_sector_weight=args.max_sector_weight,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"us_current_model_portfolio_{args.date}.csv"
    out_json = OUT_DIR / f"us_current_model_portfolio_{args.date}.json"
    portfolio.to_csv(out_csv, index=False, encoding="utf-8-sig")
    sector_weights = portfolio.groupby("行业分组")["目标权重"].sum().sort_values(ascending=False)
    summary = {
        "output_csv": str(out_csv),
        "symbols": int(len(portfolio)),
        "total_weight": float(portfolio["目标权重"].sum()),
        "largest_weight": float(portfolio["目标权重"].max()),
        "largest_sector_weight": float(sector_weights.iloc[0]),
        "drag_symbols": portfolio.loc[portfolio["is_drag_symbol"], "股票代码"].tolist(),
        "source": "persistent outperforming current strategies, 5/7 sleeves only, portfolio-level capped aggregation",
        "status": "候选模型组合，未替代 current 单策略池",
    }
    out_json.write_text(
        json.dumps({"summary": summary, "holdings": portfolio.to_dict(orient="records")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
