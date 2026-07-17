from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd


DB_PATH = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
DRAG_SYMBOLS = {
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


def first_column(frame: pd.DataFrame, names: list[str], fallback_index: int | None = None) -> str:
    for name in names:
        if name in frame.columns:
            return name
    if fallback_index is not None and fallback_index < len(frame.columns):
        return str(frame.columns[fallback_index])
    raise KeyError(f"Missing expected columns: {names}")


def monitor_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["candidate_id"].astype(str)
        + "__N"
        + frame["top_n_numeric"].astype(int).astype(str)
        + "__R"
        + frame["rebalance_days_numeric"].astype(int).astype(str)
    )


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def current_baskets_and_counts(current_holdings: pd.DataFrame) -> tuple[dict[str, set[str]], dict[str, int]]:
    if current_holdings.empty:
        return {}, {}
    monitor_col = first_column(current_holdings, ["monitor_key"], 1)
    symbol_col = first_column(current_holdings, ["股票代码", "鑲＄エ浠ｇ爜"], 5)
    baskets = {
        str(key): set(group[symbol_col].astype(str))
        for key, group in current_holdings.groupby(monitor_col, dropna=False)
    }
    counts: dict[str, int] = {}
    for basket in baskets.values():
        for symbol in basket:
            counts[symbol] = counts.get(symbol, 0) + 1
    return baskets, counts


def max_current_overlap(symbols: set[str], current_baskets: dict[str, set[str]]) -> float:
    if not current_baskets:
        return 0.0
    return max(jaccard(symbols, basket) for basket in current_baskets.values())


def live_excess_column(frame: pd.DataFrame) -> str | None:
    for column in frame.columns:
        text = str(column)
        if "实盘超基准" in text or "瓒呭熀" in text:
            return text
    return None


def audit_promoted_frames(
    strategies: pd.DataFrame,
    holdings: pd.DataFrame,
    current_holdings: pd.DataFrame,
    max_overlap: float,
    max_reuse_share: float,
    max_symbol_count: int,
    allowed_holdings: set[int],
) -> pd.DataFrame:
    if strategies.empty:
        return pd.DataFrame(
            columns=[
                "monitor_key",
                "approved",
                "reason",
                "top_n",
                "live_excess",
                "max_current_overlap",
                "current_stock_reuse_share",
                "max_current_symbol_count",
                "drag_symbol_hits",
            ]
        )

    baskets, counts = current_baskets_and_counts(current_holdings)
    strategy_id_col = first_column(strategies, ["策略编号", "绛栫暐缂栧彿"], 1)
    holding_strategy_col = first_column(holdings, ["策略编号", "绛栫暐缂栧彿"], 1)
    symbol_col = first_column(holdings, ["股票代码", "鑲＄エ浠ｇ爜"], 2)
    excess_col = live_excess_column(strategies)

    prepared = strategies.copy()
    if "monitor_key" not in prepared.columns:
        prepared["monitor_key"] = monitor_key(prepared)

    rows: list[dict[str, object]] = []
    for _, strategy in prepared.iterrows():
        strategy_id = str(strategy[strategy_id_col])
        strategy_holdings = holdings[holdings[holding_strategy_col].astype(str).eq(strategy_id)]
        symbols = strategy_holdings[symbol_col].astype(str).tolist()
        symbol_set = set(symbols)
        top_n = int(strategy.get("top_n_numeric", len(symbols)))
        overlap = max_current_overlap(symbol_set, baskets)
        symbol_counts = [counts.get(symbol, 0) for symbol in symbols]
        reuse_share = sum(1 for value in symbol_counts if value > 0) / len(symbol_counts) if symbol_counts else 0.0
        max_count = max(symbol_counts) if symbol_counts else 0
        drag_hits = len(symbol_set & DRAG_SYMBOLS)
        live_excess = float(strategy.get(excess_col, 0.0)) if excess_col else 0.0

        reasons = []
        if top_n not in allowed_holdings:
            reasons.append("invalid_holding_count")
        if live_excess <= 0:
            reasons.append("non_positive_live_excess")
        if overlap > max_overlap:
            reasons.append("high_current_basket_overlap")
        if reuse_share > max_reuse_share:
            reasons.append("high_current_stock_reuse")
        if max_count > max_symbol_count:
            reasons.append("high_single_stock_crowding")
        if top_n <= 7 and drag_hits > 0:
            reasons.append("drag_symbol_leakage")

        rows.append(
            {
                "monitor_key": str(strategy["monitor_key"]),
                "approved": not reasons,
                "reason": "approved" if not reasons else ";".join(reasons),
                "top_n": top_n,
                "live_excess": live_excess,
                "max_current_overlap": overlap,
                "current_stock_reuse_share": reuse_share,
                "max_current_symbol_count": max_count,
                "drag_symbol_hits": drag_hits,
            }
        )
    return pd.DataFrame(rows)


def audit_rounds(
    db_path: Path,
    start_round: int,
    end_round: int,
    max_overlap: float,
    max_reuse_share: float,
    max_symbol_count: int,
    allowed_holdings: set[int],
) -> pd.DataFrame:
    run_ids = [f"2026-07-13-monitor-round{round_no}-quality-stability" for round_no in range(start_round, end_round + 1)]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        strategies = con.execute("select * from us_live_pool_strategies").fetchdf()
        holdings = con.execute("select * from us_live_pool_holdings").fetchdf()
        current_holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()
    if not strategies.empty:
        strategies = strategies[strategies["run_id"].astype(str).isin(run_ids)].copy()
    if not holdings.empty:
        holdings = holdings[holdings["run_id"].astype(str).isin(run_ids)].copy()
    return audit_promoted_frames(
        strategies,
        holdings,
        current_holdings,
        max_overlap=max_overlap,
        max_reuse_share=max_reuse_share,
        max_symbol_count=max_symbol_count,
        allowed_holdings=allowed_holdings,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--start-round", type=int, required=True)
    parser.add_argument("--end-round", type=int, required=True)
    parser.add_argument("--max-overlap", type=float, default=0.25)
    parser.add_argument("--max-reuse-share", type=float, default=0.40)
    parser.add_argument("--max-symbol-count", type=int, default=8)
    parser.add_argument("--allowed-holdings", default="5,7,10,20")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    allowed_holdings = {int(value.strip()) for value in args.allowed_holdings.split(",") if value.strip()}
    audit = audit_rounds(
        Path(args.db),
        args.start_round,
        args.end_round,
        args.max_overlap,
        args.max_reuse_share,
        args.max_symbol_count,
        allowed_holdings,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out_path, index=False)
    summary = {
        "rows": int(len(audit)),
        "approved": int(audit["approved"].sum()) if not audit.empty else 0,
        "rejected": int((~audit["approved"]).sum()) if not audit.empty else 0,
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
