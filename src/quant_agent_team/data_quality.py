from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List

from .db import PostgresCli


@dataclass
class DataQualityReport:
    generated_at: str
    database: str
    market_summary: Dict[str, object]
    recent_conflicts: Dict[str, object]
    feature_summary: Dict[str, object]
    lagging_symbols: Dict[str, object]
    consistency_summary: Dict[str, object]
    anomaly_rules: List[Dict[str, object]]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_data_quality_report(db: PostgresCli | None = None) -> DataQualityReport:
    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()

    market_summary = _load_market_summary(pg)
    recent_conflicts = _load_recent_conflicts(pg)
    feature_summary = _load_feature_summary(pg)
    lagging_symbols = _load_lagging_symbols(pg)
    consistency_summary = _load_consistency_summary(pg)
    anomaly_rules = _build_anomaly_rules(
        market_summary=market_summary,
        recent_conflicts=recent_conflicts,
        feature_summary=feature_summary,
        lagging_symbols=lagging_symbols,
        consistency_summary=consistency_summary,
    )

    notes = [
        "Lagging symbols are stock codes whose latest raw_market_daily trade_date is earlier than the database max trade_date.",
        "Feature missing_refresh counts exclude expected warmup gaps from rolling windows.",
        "Free-source fetch failures, delistings, suspensions, and code changes should be triaged from the lagging symbol list rather than assumed to be data corruption.",
        "Anomaly rules classify each condition into pass, info, warn, or fail for operational triage.",
    ]

    return DataQualityReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        database=pg.config.db_name,
        market_summary=market_summary,
        recent_conflicts=recent_conflicts,
        feature_summary=feature_summary,
        lagging_symbols=lagging_symbols,
        consistency_summary=consistency_summary,
        anomaly_rules=anomaly_rules,
        notes=notes,
    )


def _load_market_summary(db: PostgresCli) -> Dict[str, object]:
    row = db.run_sql(
        """
SELECT
  (SELECT COUNT(*) FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COUNT(*) FROM normalized_market_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COUNT(DISTINCT stock_code) FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COALESCE(MIN(trade_date)::text, '') FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COALESCE(MAX(trade_date)::text, '') FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COUNT(*) FROM ingest_conflict_log);
"""
    ).strip()
    raw_rows, normalized_rows, stock_count, min_date, max_date, conflict_rows = row.split("|")
    return {
        "raw_rows": int(raw_rows),
        "normalized_rows": int(normalized_rows),
        "stock_count": int(stock_count),
        "earliest_trade_date": min_date,
        "latest_trade_date": max_date,
        "conflict_rows": int(conflict_rows),
    }


def _load_recent_conflicts(db: PostgresCli) -> Dict[str, object]:
    rows = db.run_sql(
        """
SELECT stock_code, trade_date::text, created_at::text
FROM ingest_conflict_log
ORDER BY created_at DESC
LIMIT 10;
"""
    ).splitlines()
    latest = []
    for row in rows:
        if not row:
            continue
        stock_code, trade_date, created_at = row.split("|", 2)
        latest.append(
            {
                "stock_code": stock_code,
                "trade_date": trade_date,
                "created_at": created_at,
            }
        )
    return {
        "recent_count": len(latest),
        "latest_conflicts": latest,
    }


def _load_feature_summary(db: PostgresCli) -> Dict[str, object]:
    row = db.run_sql(
        """
WITH ordered_market AS (
  SELECT
    stock_code,
    trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY stock_code
      ORDER BY trade_date
    ) AS seq_num
  FROM normalized_market_daily
  WHERE stock_code ~ '^[0-9]{6}$'
)
SELECT
  (SELECT COUNT(*) FROM research_feature_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COUNT(DISTINCT stock_code) FROM research_feature_daily WHERE stock_code ~ '^[0-9]{6}$'),
  (SELECT COALESCE(MAX(trade_date)::text, '') FROM research_feature_daily WHERE stock_code ~ '^[0-9]{6}$'),
  SUM(CASE WHEN ordered_market.seq_num < 60 AND (feature.trade_date IS NULL OR feature.ma_60 IS NULL OR feature.volatility_20d IS NULL) THEN 1 ELSE 0 END),
  SUM(CASE WHEN ordered_market.seq_num >= 60 AND (feature.trade_date IS NULL OR feature.ma_60 IS NULL OR feature.volatility_20d IS NULL) THEN 1 ELSE 0 END),
  COUNT(DISTINCT CASE WHEN ordered_market.seq_num >= 60 AND (feature.trade_date IS NULL OR feature.ma_60 IS NULL OR feature.volatility_20d IS NULL) THEN ordered_market.stock_code END)
FROM ordered_market
LEFT JOIN research_feature_daily AS feature
  ON feature.stock_code = ordered_market.stock_code
 AND feature.trade_date = ordered_market.trade_date;
"""
    ).strip()
    (
        feature_rows,
        feature_stock_count,
        feature_max_date,
        expected_unavailable,
        missing_refresh,
        stock_codes_with_missing,
    ) = row.split("|")
    return {
        "feature_rows": int(feature_rows),
        "feature_stock_count": int(feature_stock_count),
        "latest_trade_date": feature_max_date,
        "expected_unavailable_stock_dates": int(expected_unavailable),
        "missing_refresh_stock_dates": int(missing_refresh),
        "stock_codes_with_missing_refresh": int(stock_codes_with_missing),
    }


def _load_lagging_symbols(db: PostgresCli) -> Dict[str, object]:
    max_date = db.run_sql(
        "SELECT COALESCE(MAX(trade_date)::text, '') FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$';"
    ).strip()
    rows = db.run_sql(
        """
WITH latest_by_symbol AS (
  SELECT stock_code, MAX(trade_date) AS latest_trade_date
  FROM raw_market_daily
  WHERE stock_code ~ '^[0-9]{6}$'
  GROUP BY stock_code
)
SELECT stock_code, latest_trade_date::text
FROM latest_by_symbol
WHERE latest_trade_date < (SELECT MAX(trade_date) FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$')
ORDER BY latest_trade_date ASC, stock_code ASC
LIMIT 50;
"""
    ).splitlines()
    samples = []
    for row in rows:
        if not row:
            continue
        stock_code, latest_trade_date = row.split("|", 1)
        samples.append(
            {
                "stock_code": stock_code,
                "latest_trade_date": latest_trade_date,
            }
        )
    lagging_count = db.run_sql(
        """
WITH latest_by_symbol AS (
  SELECT stock_code, MAX(trade_date) AS latest_trade_date
  FROM raw_market_daily
  WHERE stock_code ~ '^[0-9]{6}$'
  GROUP BY stock_code
)
SELECT COUNT(*)
FROM latest_by_symbol
WHERE latest_trade_date < (SELECT MAX(trade_date) FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$');
"""
    ).strip()
    bucket_rows = db.run_sql(
        """
WITH latest_by_symbol AS (
  SELECT stock_code, MAX(trade_date) AS latest_trade_date
  FROM raw_market_daily
  WHERE stock_code ~ '^[0-9]{6}$'
  GROUP BY stock_code
)
SELECT
  CASE
    WHEN latest_trade_date = DATE '2025-12-31' THEN 'batch_backfill_candidates_2026_missing'
    WHEN latest_trade_date >= DATE '2025-01-01' THEN 'recent_2025_tail'
    WHEN latest_trade_date >= DATE '2024-01-01' THEN 'stale_2024'
    WHEN latest_trade_date >= DATE '2020-01-01' THEN 'stale_2020_to_2023'
    ELSE 'historical_end_before_2020'
  END AS lagging_bucket,
  COUNT(*) AS symbol_count
FROM latest_by_symbol
WHERE latest_trade_date < (SELECT MAX(trade_date) FROM raw_market_daily WHERE stock_code ~ '^[0-9]{6}$')
GROUP BY 1
ORDER BY COUNT(*) DESC, lagging_bucket ASC;
"""
    ).splitlines()
    buckets = []
    for row in bucket_rows:
        if not row:
            continue
        lagging_bucket, symbol_count = row.split("|", 1)
        buckets.append({"bucket": lagging_bucket, "symbol_count": int(symbol_count)})
    status_snapshot = _load_lagging_backfill_status()
    return {
        "database_latest_trade_date": max_date,
        "lagging_symbol_count": int(lagging_count or "0"),
        "classification_buckets": buckets,
        "sample_lagging_symbols": samples,
        "backfill_status_snapshot": status_snapshot,
    }


def _load_lagging_backfill_status() -> Dict[str, object]:
    path = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "data_quality"
        / "lagging_backfill_status.json"
    )
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_consistency_summary(db: PostgresCli) -> Dict[str, object]:
    mismatch_count = int(
        db.run_sql(
            """
WITH latest_raw AS (
  SELECT DISTINCT ON (stock_code, trade_date)
    stock_code,
    trade_date,
    raw_line_hash
  FROM raw_market_daily
  ORDER BY stock_code, trade_date, updated_at DESC, id DESC
)
SELECT COUNT(*)
FROM normalized_market_daily AS normalized
JOIN latest_raw AS raw
  ON raw.stock_code = normalized.stock_code
 AND raw.trade_date = normalized.trade_date
WHERE normalized.source_raw_line_hash <> raw.raw_line_hash;
"""
        ).strip()
        or "0"
    )
    mismatch_symbols = int(
        db.run_sql(
            """
WITH latest_raw AS (
  SELECT DISTINCT ON (stock_code, trade_date)
    stock_code,
    trade_date,
    raw_line_hash
  FROM raw_market_daily
  ORDER BY stock_code, trade_date, updated_at DESC, id DESC
)
SELECT COUNT(DISTINCT normalized.stock_code)
FROM normalized_market_daily AS normalized
JOIN latest_raw AS raw
  ON raw.stock_code = normalized.stock_code
 AND raw.trade_date = normalized.trade_date
WHERE normalized.source_raw_line_hash <> raw.raw_line_hash;
"""
        ).strip()
        or "0"
    )
    rows = db.run_sql(
        """
WITH latest_raw AS (
  SELECT DISTINCT ON (stock_code, trade_date)
    stock_code,
    trade_date,
    raw_line_hash
  FROM raw_market_daily
  ORDER BY stock_code, trade_date, updated_at DESC, id DESC
)
SELECT normalized.stock_code, normalized.trade_date::text
FROM normalized_market_daily AS normalized
JOIN latest_raw AS raw
  ON raw.stock_code = normalized.stock_code
 AND raw.trade_date = normalized.trade_date
WHERE normalized.source_raw_line_hash <> raw.raw_line_hash
ORDER BY normalized.trade_date DESC, normalized.stock_code ASC
LIMIT 20;
"""
    ).splitlines()
    samples = []
    for row in rows:
        if not row:
            continue
        stock_code, trade_date = row.split("|", 1)
        samples.append({"stock_code": stock_code, "trade_date": trade_date})
    return {
        "normalized_source_hash_mismatch_rows": mismatch_count,
        "normalized_source_hash_mismatch_symbols": mismatch_symbols,
        "sample_mismatches": samples,
    }


def _build_anomaly_rules(
    market_summary: Dict[str, object],
    recent_conflicts: Dict[str, object],
    feature_summary: Dict[str, object],
    lagging_symbols: Dict[str, object],
    consistency_summary: Dict[str, object],
) -> List[Dict[str, object]]:
    rules: List[Dict[str, object]] = []

    raw_rows = int(market_summary.get("raw_rows", 0))
    normalized_rows = int(market_summary.get("normalized_rows", 0))
    feature_rows = int(feature_summary.get("feature_rows", 0))
    missing_refresh = int(feature_summary.get("missing_refresh_stock_dates", 0))
    stock_codes_with_missing = int(feature_summary.get("stock_codes_with_missing_refresh", 0))
    conflict_rows = int(market_summary.get("conflict_rows", 0))
    recent_conflict_count = int(recent_conflicts.get("recent_count", 0))
    lagging_count = int(lagging_symbols.get("lagging_symbol_count", 0))
    mismatch_rows = int(consistency_summary.get("normalized_source_hash_mismatch_rows", 0))
    mismatch_symbols = int(consistency_summary.get("normalized_source_hash_mismatch_symbols", 0))
    snapshot = lagging_symbols.get("backfill_status_snapshot") or {}
    recent_2026_remaining = int((snapshot.get("recent_2026_remaining") or {}).get("count", 0))
    recent_2025_tail_remaining = int((snapshot.get("recent_2025_tail_remaining") or {}).get("count", 0))
    stale_2024_remaining = int((snapshot.get("stale_2024_remaining") or {}).get("count", 0))
    stale_2020_2023_remaining = int((snapshot.get("stale_2020_2023_remaining") or {}).get("count", 0))
    historical_pre_2020_remaining = int(
        (snapshot.get("historical_end_before_2020_remaining") or {}).get("count", 0)
    )
    blocked_total = (
        recent_2026_remaining
        + recent_2025_tail_remaining
        + stale_2024_remaining
        + stale_2020_2023_remaining
        + historical_pre_2020_remaining
    )

    rules.append(
        {
            "rule_id": "market_row_balance",
            "status": "pass" if raw_rows == normalized_rows else "fail",
            "severity": "high" if raw_rows != normalized_rows else "none",
            "metric_value": raw_rows - normalized_rows,
            "summary": "raw_market_daily and normalized_market_daily row counts should match.",
            "action": (
                "Investigate normalization sync regression."
                if raw_rows != normalized_rows
                else "No action."
            ),
        }
    )
    rules.append(
        {
            "rule_id": "normalized_source_hash_alignment",
            "status": "fail" if mismatch_rows else "pass",
            "severity": "high" if mismatch_rows else "none",
            "metric_value": mismatch_rows,
            "summary": "normalized_market_daily should reference the latest raw_market_daily hash for the same stock/date.",
            "action": (
                f"Repair normalized sync for {mismatch_symbols} affected stock codes."
                if mismatch_rows
                else "No action."
            ),
        }
    )
    rules.append(
        {
            "rule_id": "feature_refresh_gap",
            "status": "pass" if missing_refresh == 0 else "warn",
            "severity": "medium" if missing_refresh else "none",
            "metric_value": missing_refresh,
            "summary": "Derived feature gaps after warmup windows should stay at zero.",
            "action": (
                f"Refresh derived features for {stock_codes_with_missing} affected stock codes."
                if missing_refresh
                else "No action."
            ),
        }
    )
    rules.append(
        {
            "rule_id": "recent_lagging_symbols",
            "status": "pass" if recent_2026_remaining == 0 else "warn",
            "severity": "medium" if recent_2026_remaining else "none",
            "metric_value": recent_2026_remaining,
            "summary": "Symbols lagging within the current latest year should be near zero after backfill.",
            "action": (
                "Investigate remaining recent laggards or add a stronger source for them."
                if recent_2026_remaining
                else "No action."
            ),
        }
    )
    rules.append(
        {
            "rule_id": "known_free_source_unavailable",
            "status": "info" if blocked_total else "pass",
            "severity": "low" if blocked_total else "none",
            "metric_value": blocked_total,
            "summary": "Known free-source-unavailable symbols should stay on the blocked list instead of being retried daily.",
            "action": (
                "Retry only after adding a new source or changing fetch logic."
                if blocked_total
                else "No action."
            ),
        }
    )
    rules.append(
        {
            "rule_id": "conflict_backlog",
            "status": "warn" if conflict_rows or recent_conflict_count else "pass",
            "severity": "medium" if conflict_rows or recent_conflict_count else "none",
            "metric_value": conflict_rows,
            "summary": "Conflicting same-day revisions should be reviewed rather than silently ignored.",
            "action": (
                "Review ingest_conflict_log and confirm whether the upstream files changed legitimately."
                if conflict_rows or recent_conflict_count
                else "No action."
            ),
        }
    )
    rules.append(
        {
            "rule_id": "lagging_bucket_visibility",
            "status": "info" if lagging_count else "pass",
            "severity": "low" if lagging_count else "none",
            "metric_value": lagging_count,
            "summary": "Lagging symbols need bucket-level triage instead of being treated as generic corruption.",
            "action": (
                f"Track {recent_2025_tail_remaining} recent_2025_tail, {stale_2024_remaining} stale_2024, {stale_2020_2023_remaining} stale_2020_2023, and {historical_pre_2020_remaining} historical_pre_2020 symbols in the blocked snapshot."
                if lagging_count
                else "No action."
            ),
        }
    )
    return rules
