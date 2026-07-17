from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd


DB_PATH = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
REPORT_DIR = Path(r"G:\quant-agent-team-us\reports\us\live\current")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def add_quality_score(strategies: pd.DataFrame) -> pd.DataFrame:
    out = strategies.copy()
    out["组合层质量分"] = (
        _num(out, "信息比率") * 1.0
        + _num(out, "年度平均信息比率") * 0.35
        + _num(out, "实盘超基准收益") * 35.0
        + _num(out, "样本外滚动验证超基准收益") * 1.5
        + _num(out, "去偏标准分") * 0.20
        - _num(out, "最大回撤") * 0.55
    )
    return out


def holding_sets(holdings: pd.DataFrame) -> dict[str, set[str]]:
    if holdings.empty:
        return {}
    return {
        str(key): set(group["股票代码"].astype(str))
        for key, group in holdings.groupby("monitor_key", dropna=False)
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def select_overlap_aware(
    strategies: pd.DataFrame,
    holdings: pd.DataFrame,
    *,
    target_count: int = 80,
    max_jaccard: float = 0.55,
    min_live_excess: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if strategies.empty:
        empty_review = pd.DataFrame(columns=["monitor_key", "组合层审核状态", "最大持仓重叠度", "重叠参照策略"])
        return strategies.copy(), holdings.copy(), empty_review

    scored = add_quality_score(strategies)
    scored = scored[_num(scored, "实盘超基准收益").gt(min_live_excess)].copy()
    scored = scored.sort_values(
        ["组合层质量分", "信息比率", "实盘超基准收益", "最大回撤", "monitor_key"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)

    baskets = holding_sets(holdings)
    selected_keys: list[str] = []
    selected_baskets: dict[str, set[str]] = {}
    review_rows: list[dict[str, object]] = []

    for row in scored.itertuples(index=False):
        key = str(getattr(row, "monitor_key"))
        basket = baskets.get(key, set())
        overlaps = [(other, jaccard(basket, other_basket)) for other, other_basket in selected_baskets.items()]
        ref_key, max_overlap = max(overlaps, key=lambda item: item[1], default=("", 0.0))
        room_left = len(selected_keys) < target_count
        keep = room_left and max_overlap <= max_jaccard
        if keep:
            selected_keys.append(key)
            selected_baskets[key] = basket
        review_rows.append(
            {
                "monitor_key": key,
                "组合层审核状态": "建议保留" if keep else "延后观察",
                "组合层质量分": float(getattr(row, "组合层质量分")),
                "最大持仓重叠度": float(max_overlap),
                "重叠参照策略": ref_key,
                "审核原因": "质量达标且持仓重叠受控"
                if keep
                else ("达到目标策略数量" if not room_left else "与已选策略持仓重叠过高"),
            }
        )

    review = pd.DataFrame(review_rows)
    selected = scored[scored["monitor_key"].astype(str).isin(selected_keys)].copy()
    selected_holdings = holdings[holdings["monitor_key"].astype(str).isin(selected_keys)].copy()
    return selected.reset_index(drop=True), selected_holdings.reset_index(drop=True), review


def write_duckdb_tables(db_path: Path, selected: pd.DataFrame, selected_holdings: pd.DataFrame, review: pd.DataFrame) -> None:
    con = duckdb.connect(str(db_path))
    try:
        for table, frame in [
            ("us_live_monitoring_overlap_selected_current", selected),
            ("us_live_monitoring_overlap_holdings_current", selected_holdings),
            ("us_live_monitoring_overlap_review_current", review),
        ]:
            con.register("_frame", frame)
            con.execute(f"create or replace table {table} as select * from _frame")
            con.unregister("_frame")
    finally:
        con.close()


def write_csv_reports(report_dir: Path, selected: pd.DataFrame, selected_holdings: pd.DataFrame, review: pd.DataFrame) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    selected.to_csv(report_dir / "2026-07-14-us-overlap-aware-selected-strategies.csv", index=False, encoding="utf-8-sig")
    selected_holdings.to_csv(report_dir / "2026-07-14-us-overlap-aware-selected-holdings.csv", index=False, encoding="utf-8-sig")
    review.to_csv(report_dir / "2026-07-14-us-overlap-aware-review.csv", index=False, encoding="utf-8-sig")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument("--target-count", type=int, default=80)
    parser.add_argument("--max-jaccard", type=float, default=0.55)
    args = parser.parse_args()

    db_path = Path(args.db)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
        holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()

    selected, selected_holdings, review = select_overlap_aware(
        strategies,
        holdings,
        target_count=args.target_count,
        max_jaccard=args.max_jaccard,
    )
    write_duckdb_tables(db_path, selected, selected_holdings, review)
    write_csv_reports(Path(args.report_dir), selected, selected_holdings, review)

    distribution = selected["持仓数量"].value_counts().sort_index().to_dict() if "持仓数量" in selected else {}
    print(
        {
            "selected_strategies": int(len(selected)),
            "selected_holdings": int(len(selected_holdings)),
            "reviewed_strategies": int(len(review)),
            "max_jaccard": args.max_jaccard,
            "holding_distribution": {int(k): int(v) for k, v in distribution.items()},
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
