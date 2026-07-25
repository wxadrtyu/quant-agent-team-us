from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb


def report_payload_quality(data: dict, tolerance: float = 1e-6) -> dict[str, int]:
    missing_price_count = 0
    contribution_mismatch_count = 0
    duplicate_strategy_display_count = 0
    empty_holding_strategy_count = 0
    seen: set[str] = set()
    for item in data.get("results", []):
        sid = str(item.get("sid", ""))
        if sid in seen:
            duplicate_strategy_display_count += 1
        seen.add(sid)
        stocks = item.get("stocks", [])
        if not stocks:
            empty_holding_strategy_count += 1
        contribution = 0.0
        for stock in stocks:
            if stock.get("buy_price") is None or stock.get("mtm_price") is None:
                missing_price_count += 1
            contribution += float(stock.get("contribution") or 0.0)
        if stocks and abs(contribution - float(item.get("live_return") or 0.0)) > tolerance:
            contribution_mismatch_count += 1
    return {
        "json_missing_price_count": missing_price_count,
        "json_contribution_mismatch_count": contribution_mismatch_count,
        "json_duplicate_strategy_display_count": duplicate_strategy_display_count,
        "json_empty_holding_strategy_count": empty_holding_strategy_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
    parser.add_argument("--report", required=True)
    parser.add_argument("--json", required=True)
    args = parser.parse_args()

    db_path = Path(args.db)
    report_path = Path(args.report)
    json_path = Path(args.json)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
        holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()

    text = report_path.read_text(encoding="utf-8")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    payload_quality = report_payload_quality(data)
    summary = {
        "current_strategies": int(len(strategies)),
        "current_holdings": int(len(holdings)),
        "outperformers": int((strategies["实盘超基准收益"] > 0).sum()),
        "underperformers_kept": int((strategies["实盘超基准收益"] <= 0).sum()),
        "persistent_outperformers": int(strategies["入库至今持续跑赢"].sum()),
        "dates": {str(key): int(value) for key, value in strategies["估值日期"].value_counts().sort_index().items()},
        "holding_distribution": {str(key): int(value) for key, value in strategies["top_n_numeric"].value_counts().sort_index().items()},
        "invalid_holding_count": int((~strategies["top_n_numeric"].isin([5, 7, 10, 20])).sum()),
        "json_strategy_count": int(len(data.get("results", []))),
        "report_exists": report_path.exists(),
        "html_has_nan_or_placeholder": bool(re.search(r"NaN|Infinity|__PLACEHOLDER__|TBD", text)),
        "html_has_fallback_name": ("（美股）" in text) or ("(美股)" in text),
        "has_age_fields": all(col in strategies.columns for col in ["入库日期", "入库天数", "入库至今持续跑赢", "当前诊断"]),
        "json_has_persistent_tab_data": any(item.get("persistent_outperformer") for item in data.get("results", [])),
        "json_underperformers_kept": sum(1 for item in data.get("results", []) if item.get("live_excess", 0) <= 0),
        **payload_quality,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["invalid_holding_count"] != 0:
        raise SystemExit("current table has invalid holding count")
    if summary["json_strategy_count"] != summary["current_strategies"]:
        raise SystemExit("report json count does not match current table")
    if summary["html_has_nan_or_placeholder"]:
        raise SystemExit("report has invalid placeholder values")
    if summary["html_has_fallback_name"]:
        raise SystemExit("report has fallback US stock names")
    if not summary["has_age_fields"]:
        raise SystemExit("current table lacks age fields")
    if summary["underperformers_kept"] != summary["json_underperformers_kept"]:
        raise SystemExit("underperformer count mismatch")
    if set(summary["holding_distribution"]) - {"5", "7", "10", "20"}:
        raise SystemExit("holding distribution has invalid counts")
    if summary["json_missing_price_count"] != 0:
        raise SystemExit("report json has missing holding prices")
    if summary["json_contribution_mismatch_count"] != 0:
        raise SystemExit("report json live return does not match holding contributions")
    if summary["json_duplicate_strategy_display_count"] != 0:
        raise SystemExit("report json has duplicate strategy display ids")
    if summary["json_empty_holding_strategy_count"] != 0:
        raise SystemExit("report json has empty strategy holdings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
