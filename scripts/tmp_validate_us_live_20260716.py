from pathlib import Path
import json
import re

import duckdb


DB = Path(r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
REPORT = Path(
    r"G:\quant-agent-team-us\reports\us\live\current\us_simulation_formal_monitoring_detail_0630_0716.html"
)
JSON_PATH = Path(
    r"G:\quant-agent-team-us\reports\us\live\current\us_simulation_formal_monitoring_0630_0716.json"
)

con = duckdb.connect(str(DB), read_only=True)
strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
excluded = con.execute(
    "select count(*) from us_live_monitoring_strategies_excluded_20260716_intraday"
).fetchone()[0]
revalued = con.execute(
    "select count(*) from us_live_monitoring_strategies_revalued_20260716"
).fetchone()[0]
con.close()

text = REPORT.read_text(encoding="utf-8")
data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

summary = {
    "current_strategies": int(len(strategies)),
    "current_holdings": int(len(holdings)),
    "outperformers": int((strategies["实盘超基准收益"] > 0).sum()),
    "underperformers_kept": int((strategies["实盘超基准收益"] <= 0).sum()),
    "persistent_outperformers": int(strategies["入库至今持续跑赢"].sum()),
    "dates": {
        str(key): int(value)
        for key, value in strategies["估值日期"].value_counts().sort_index().items()
    },
    "holding_distribution": {
        str(key): int(value)
        for key, value in strategies["top_n_numeric"].value_counts().sort_index().items()
    },
    "invalid_holding_count": int((~strategies["top_n_numeric"].isin([5, 7, 10, 20])).sum()),
    "excluded": int(excluded),
    "revalued_all": int(revalued),
    "json_strategy_count": int(len(data.get("results", []))),
    "report_exists": REPORT.exists(),
    "html_has_nan_or_placeholder": bool(
        re.search(r"NaN|Infinity|__PLACEHOLDER__|TBD", text)
    ),
    "html_has_fallback_name": ("（美股）" in text) or ("(美股)" in text),
    "html_has_us_fallback_text": "美股" in text,
    "has_age_fields": all(
        col in strategies.columns
        for col in ["入库日期", "入库天数", "入库至今持续跑赢", "当前诊断"]
    ),
    "json_has_persistent_tab_data": any(
        item.get("persistent_outperformer") for item in data.get("results", [])
    ),
    "json_underperformers_kept": sum(
        1 for item in data.get("results", []) if item.get("live_excess", 0) <= 0
    ),
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
