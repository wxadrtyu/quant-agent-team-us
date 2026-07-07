#!/usr/bin/env python3.11
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import DatabaseConfig, PostgresCli


st.set_page_config(page_title="Quant DB Dashboard", layout="wide")


def run_query_frame(sql: str) -> pd.DataFrame:
    config = DatabaseConfig.from_env()
    process = subprocess.run(
        [
            str(config.psql_bin),
            config.db_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"COPY ({sql}) TO STDOUT WITH CSV HEADER",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = process.stdout.strip()
    if not payload:
        return pd.DataFrame()
    return pd.read_csv(StringIO(payload))


@st.cache_data(ttl=60)
def load_data_quality_report() -> dict:
    path = ROOT / "reports" / "data_quality" / "latest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(ttl=60)
def load_daily_update_summary() -> dict:
    path = ROOT / "reports" / "ingestion" / "daily_update_latest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(ttl=60)
def load_overview() -> dict[str, str]:
    db = PostgresCli()
    return {
        "raw_rows": db.run_sql("SELECT COUNT(*) FROM raw_market_daily;").strip(),
        "normalized_rows": db.run_sql("SELECT COUNT(*) FROM normalized_market_daily;").strip(),
        "feature_rows": db.run_sql("SELECT COUNT(*) FROM research_feature_daily;").strip(),
        "conflict_rows": db.run_sql("SELECT COUNT(*) FROM ingest_conflict_log;").strip(),
        "raw_max_date": db.run_sql("SELECT COALESCE(MAX(trade_date)::text, '') FROM raw_market_daily;").strip(),
        "normalized_max_date": db.run_sql("SELECT COALESCE(MAX(trade_date)::text, '') FROM normalized_market_daily;").strip(),
        "stock_count": db.run_sql("SELECT COUNT(DISTINCT stock_code) FROM raw_market_daily;").strip(),
    }


@st.cache_data(ttl=60)
def load_recent_runs() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT id, run_type, status, inserted_rows, conflict_rows, created_at
FROM ingest_runs
ORDER BY id DESC
LIMIT 20
"""
    )


@st.cache_data(ttl=60)
def load_recent_market_dates() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT trade_date, COUNT(*) AS row_count
FROM raw_market_daily
GROUP BY trade_date
ORDER BY trade_date DESC
LIMIT 30
"""
    )


@st.cache_data(ttl=60)
def load_feature_coverage() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT feature_name, row_count, max_trade_date
FROM (
  SELECT 'avg_turnover_20d' AS feature_name, COUNT(avg_turnover_20d) AS row_count, MAX(trade_date) FILTER (WHERE avg_turnover_20d IS NOT NULL) AS max_trade_date FROM research_feature_daily
  UNION ALL
  SELECT 'avg_volume_20d', COUNT(avg_volume_20d), MAX(trade_date) FILTER (WHERE avg_volume_20d IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ma_10', COUNT(ma_10), MAX(trade_date) FILTER (WHERE ma_10 IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ma_20', COUNT(ma_20), MAX(trade_date) FILTER (WHERE ma_20 IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ma_5', COUNT(ma_5), MAX(trade_date) FILTER (WHERE ma_5 IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ma_60', COUNT(ma_60), MAX(trade_date) FILTER (WHERE ma_60 IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'momentum_20d', COUNT(momentum_20d), MAX(trade_date) FILTER (WHERE momentum_20d IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ret_1d', COUNT(ret_1d), MAX(trade_date) FILTER (WHERE ret_1d IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ret_20d', COUNT(ret_20d), MAX(trade_date) FILTER (WHERE ret_20d IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'ret_5d', COUNT(ret_5d), MAX(trade_date) FILTER (WHERE ret_5d IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'volatility_20d', COUNT(volatility_20d), MAX(trade_date) FILTER (WHERE volatility_20d IS NOT NULL) FROM research_feature_daily
  UNION ALL
  SELECT 'volume_ratio_20d', COUNT(volume_ratio_20d), MAX(trade_date) FILTER (WHERE volume_ratio_20d IS NOT NULL) FROM research_feature_daily
) AS coverage
ORDER BY feature_name
"""
    )


@st.cache_data(ttl=60)
def load_storage_overview() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT relname AS table_name,
       pg_total_relation_size(relid) AS total_bytes,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
WHERE relname IN ('raw_market_daily', 'normalized_market_daily', 'research_feature_daily')
ORDER BY pg_total_relation_size(relid) DESC
"""
    )


@st.cache_data(ttl=60)
def load_feature_density() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  COUNT(*) AS total_rows,
  COUNT(ma_5) AS ma_5_rows,
  COUNT(ma_10) AS ma_10_rows,
  COUNT(ma_20) AS ma_20_rows,
  COUNT(ma_60) AS ma_60_rows,
  COUNT(avg_volume_20d) AS avg_volume_20d_rows,
  COUNT(avg_turnover_20d) AS avg_turnover_20d_rows,
  COUNT(volume_ratio_20d) AS volume_ratio_20d_rows,
  COUNT(ret_1d) AS ret_1d_rows,
  COUNT(ret_5d) AS ret_5d_rows,
  COUNT(ret_20d) AS ret_20d_rows,
  COUNT(momentum_20d) AS momentum_20d_rows,
  COUNT(volatility_20d) AS volatility_20d_rows
FROM research_feature_daily
"""
    )


@st.cache_data(ttl=60)
def load_market_context_overview() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  COUNT(*) AS context_rows,
  COUNT(*) FILTER (WHERE attention_level IS NOT NULL) AS attention_rows,
  COUNT(*) FILTER (WHERE northbound_hold_value IS NOT NULL) AS northbound_rows,
  COUNT(*) FILTER (WHERE announcement_event_tag IS NOT NULL) AS announcement_rows,
  COUNT(*) FILTER (WHERE theme_tags <> '{}'::text[]) AS themed_rows,
  MIN(trade_date) FILTER (WHERE attention_level IS NOT NULL) AS attention_min_date,
  MAX(trade_date) FILTER (WHERE attention_level IS NOT NULL) AS attention_max_date,
  MIN(trade_date) FILTER (WHERE northbound_hold_value IS NOT NULL) AS northbound_min_date,
  MAX(trade_date) FILTER (WHERE northbound_hold_value IS NOT NULL) AS northbound_max_date,
  MIN(trade_date) FILTER (WHERE announcement_event_tag IS NOT NULL) AS announcement_min_date,
  MAX(trade_date) FILTER (WHERE announcement_event_tag IS NOT NULL) AS announcement_max_date
FROM research_market_context_daily
"""
    )


@st.cache_data(ttl=60)
def load_theme_membership_summary() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  COUNT(*) AS membership_rows,
  COUNT(DISTINCT stock_code) AS stock_count,
  COUNT(*) FILTER (WHERE theme_type = 'industry') AS industry_rows,
  COUNT(*) FILTER (WHERE theme_type = 'concept') AS concept_rows,
  MIN(trade_date) AS min_trade_date,
  MAX(trade_date) AS max_trade_date
FROM raw_theme_membership_daily
"""
    )


@st.cache_data(ttl=60)
def load_attention_source_breakdown() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  source_name,
  COUNT(*) AS row_count,
  COUNT(DISTINCT stock_code) AS stock_count,
  MIN(trade_date) AS min_trade_date,
  MAX(trade_date) AS max_trade_date
FROM raw_attention_daily
GROUP BY source_name
ORDER BY row_count DESC
"""
    )


@st.cache_data(ttl=60)
def load_attention_recent_rows() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  stock_code,
  trade_date,
  source_name,
  attention_rank,
  attention_level,
  price_change_pct
FROM raw_attention_daily
ORDER BY trade_date DESC, attention_rank NULLS LAST, attention_level DESC NULLS LAST
LIMIT 80
"""
    )


@st.cache_data(ttl=60)
def load_market_context_recent_rows() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  stock_code,
  trade_date,
  industry_name,
  sector_name,
  theme_tags,
  theme_breadth_score,
  policy_event_tag,
  announcement_event_tag,
  announcement_count_1d,
  attention_rank,
  attention_level,
  attention_change_3d,
  northbound_hold_value,
  northbound_holding_change_1d,
  northbound_net_flow_proxy_1d
FROM research_market_context_daily
WHERE attention_level IS NOT NULL
   OR northbound_hold_value IS NOT NULL
   OR announcement_event_tag IS NOT NULL
ORDER BY trade_date DESC, attention_level DESC NULLS LAST, northbound_hold_value DESC NULLS LAST
LIMIT 80
"""
    )


@st.cache_data(ttl=60)
def load_notice_recent_rows() -> pd.DataFrame:
    return run_query_frame(
        """
SELECT
  stock_code,
  trade_date,
  report_scope,
  announcement_event_tag,
  policy_event_tag,
  title
FROM raw_notice_event_daily
ORDER BY trade_date DESC, stock_code
LIMIT 80
"""
    )


@st.cache_data(ttl=60)
def load_feature_gap_health() -> pd.DataFrame:
    return run_query_frame(
        """
WITH ordered_market AS (
  SELECT
    market.stock_code,
    market.trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY market.stock_code
      ORDER BY market.trade_date
    ) AS seq_num
  FROM normalized_market_daily AS market
)
SELECT
  CASE
    WHEN ordered_market.seq_num < 20 THEN 'expected_unavailable'
    ELSE 'missing_refresh'
  END AS gap_type,
  COUNT(*) AS stock_date_count,
  COUNT(DISTINCT ordered_market.stock_code) AS stock_code_count,
  MIN(ordered_market.trade_date) AS earliest_trade_date,
  MAX(ordered_market.trade_date) AS latest_trade_date
FROM ordered_market
LEFT JOIN research_feature_daily AS feature
  ON feature.stock_code = ordered_market.stock_code
 AND feature.trade_date = ordered_market.trade_date
WHERE feature.trade_date IS NULL
   OR (
     ordered_market.seq_num >= 20
     AND (feature.ma_20 IS NULL OR feature.momentum_20d IS NULL)
   )
GROUP BY gap_type
ORDER BY gap_type
"""
    )


@st.cache_data(ttl=60)
def load_stock_sample(stock_code: str) -> pd.DataFrame:
    return run_query_frame(
        f"""
SELECT
  market.trade_date,
  market.open_price,
  market.high_price,
  market.low_price,
  market.close_price,
  market.volume,
  market.turnover,
  normalized.close_price_adj,
  normalized.adj_factor,
  feature.ma_5,
  feature.ma_10,
  feature.ma_20,
  feature.ma_60,
  feature.avg_volume_20d,
  feature.avg_turnover_20d,
  feature.volume_ratio_20d,
  feature.ret_1d,
  feature.ret_5d,
  feature.ret_20d,
  feature.momentum_20d,
  feature.volatility_20d,
  context.industry_name,
  context.sector_name,
  context.theme_tags,
  context.theme_breadth_score,
  context.policy_event_tag,
  context.announcement_event_tag,
  context.announcement_count_1d,
  context.attention_rank,
  context.attention_level,
  context.attention_change_3d,
  context.attention_change_5d,
  context.northbound_hold_value,
  context.northbound_holding_change_1d,
  context.northbound_net_flow_proxy_1d
FROM raw_market_daily AS market
JOIN normalized_market_daily AS normalized
  ON normalized.stock_code = market.stock_code
 AND normalized.trade_date = market.trade_date
LEFT JOIN research_feature_daily AS feature
  ON feature.stock_code = market.stock_code
 AND feature.trade_date = market.trade_date
LEFT JOIN research_market_context_daily AS context
  ON context.stock_code = market.stock_code
 AND context.trade_date = market.trade_date
WHERE market.stock_code = '{stock_code}'
ORDER BY market.trade_date DESC
LIMIT 60
"""
    )


overview = load_overview()
quality = load_data_quality_report()
daily_update = load_daily_update_summary()
st.title("Quant Database Dashboard")
st.caption(f"Database: {DatabaseConfig.from_env().db_name}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Raw Rows", overview["raw_rows"])
col2.metric("Normalized Rows", overview["normalized_rows"])
col3.metric("Feature Rows", overview["feature_rows"])
col4.metric("Conflict Rows", overview["conflict_rows"])

col5, col6, col7 = st.columns(3)
col5.metric("Stock Count", overview["stock_count"])
col6.metric("Raw Max Date", overview["raw_max_date"])
col7.metric("Normalized Max Date", overview["normalized_max_date"])

st.subheader("Recent Ingest Runs")
st.dataframe(load_recent_runs(), use_container_width=True, hide_index=True)

st.subheader("Recent Raw Market Coverage")
date_frame = load_recent_market_dates()
st.line_chart(date_frame.set_index("trade_date")["row_count"], height=260)
st.dataframe(date_frame, use_container_width=True, hide_index=True)

st.subheader("Feature Coverage")
st.dataframe(load_feature_coverage(), use_container_width=True, hide_index=True)

st.subheader("Storage Overview")
storage = load_storage_overview()
st.dataframe(storage, use_container_width=True, hide_index=True)

st.subheader("Feature Density")
density = load_feature_density()
if not density.empty:
    st.dataframe(density, use_container_width=True, hide_index=True)

st.subheader("Feature Gap Health")
gap_health = load_feature_gap_health()
if gap_health.empty:
    st.success("No feature gaps detected.")
else:
    st.dataframe(gap_health, use_container_width=True, hide_index=True)

st.subheader("Market Context")
context_overview = load_market_context_overview()
if not context_overview.empty:
    ctx = context_overview.iloc[0]
    col16, col17, col18, col19, col20 = st.columns(5)
    col16.metric("Context Rows", ctx.get("context_rows", ""))
    col17.metric("Attention Rows", ctx.get("attention_rows", ""))
    col18.metric("Northbound Rows", ctx.get("northbound_rows", ""))
    col19.metric("Announcement Rows", ctx.get("announcement_rows", ""))
    col20.metric("Themed Rows", ctx.get("themed_rows", ""))
    st.dataframe(context_overview, use_container_width=True, hide_index=True)

theme_summary = load_theme_membership_summary()
if not theme_summary.empty:
    st.caption("Theme Membership Snapshot")
    st.dataframe(theme_summary, use_container_width=True, hide_index=True)

attention_sources = load_attention_source_breakdown()
if not attention_sources.empty:
    st.caption("Attention Source Breakdown")
    st.dataframe(attention_sources, use_container_width=True, hide_index=True)

attention_recent = load_attention_recent_rows()
if not attention_recent.empty:
    st.caption("Recent Attention Rows")
    st.dataframe(attention_recent, use_container_width=True, hide_index=True)

notice_recent = load_notice_recent_rows()
if not notice_recent.empty:
    st.caption("Recent Notice Event Rows")
    st.dataframe(notice_recent, use_container_width=True, hide_index=True)

context_recent = load_market_context_recent_rows()
if not context_recent.empty:
    st.caption("Recent Market Context Rows")
    st.dataframe(context_recent, use_container_width=True, hide_index=True)

st.subheader("Data Quality")
if not quality:
    st.info("No data quality report found yet. Run scripts/data_quality_report.py first.")
else:
    market = quality.get("market_summary", {})
    feature = quality.get("feature_summary", {})
    lagging = quality.get("lagging_symbols", {})
    backfill_status = lagging.get("backfill_status_snapshot", {})
    anomaly_rules = pd.DataFrame(quality.get("anomaly_rules", []))
    col8, col9, col10, col11 = st.columns(4)
    col8.metric("DQ Stock Count", market.get("stock_count", ""))
    col9.metric("DQ Conflict Rows", market.get("conflict_rows", ""))
    col10.metric("DQ Missing Refresh", feature.get("missing_refresh_stock_dates", ""))
    col11.metric("DQ Lagging Symbols", lagging.get("lagging_symbol_count", ""))

    quality_summary = pd.DataFrame(
        [
            {"section": "market", **market},
            {"section": "feature", **feature},
            {
                "section": "lagging",
                "database_latest_trade_date": lagging.get("database_latest_trade_date"),
                "lagging_symbol_count": lagging.get("lagging_symbol_count"),
            },
        ]
    )
    st.dataframe(quality_summary, use_container_width=True, hide_index=True)

    conflicts = pd.DataFrame(quality.get("recent_conflicts", {}).get("latest_conflicts", []))
    if not conflicts.empty:
        st.caption("Recent Conflicts")
        st.dataframe(conflicts, use_container_width=True, hide_index=True)

    lagging_samples = pd.DataFrame(lagging.get("sample_lagging_symbols", []))
    if not lagging_samples.empty:
        st.caption("Lagging Symbol Samples")
        st.dataframe(lagging_samples, use_container_width=True, hide_index=True)

    if backfill_status:
        st.caption("Free-Source Unavailable Snapshot")
        snapshot_summary = pd.DataFrame(
            [
                {
                    "bucket": "recent_2026_remaining",
                    "count": backfill_status.get("recent_2026_remaining", {}).get("count", 0),
                },
                {
                    "bucket": "recent_2025_tail_remaining",
                    "count": backfill_status.get("recent_2025_tail_remaining", {}).get("count", 0),
                },
                {
                    "bucket": "stale_2024_remaining",
                    "count": backfill_status.get("stale_2024_remaining", {}).get("count", 0),
                },
                {
                    "bucket": "stale_2020_2023_remaining",
                    "count": backfill_status.get("stale_2020_2023_remaining", {}).get("count", 0),
                },
                {
                    "bucket": "historical_end_before_2020_remaining",
                    "count": backfill_status.get("historical_end_before_2020_remaining", {}).get("count", 0),
                },
            ]
        )
        st.dataframe(snapshot_summary, use_container_width=True, hide_index=True)

        unresolved_samples = []
        for bucket_name in (
            "recent_2026_remaining",
            "recent_2025_tail_remaining",
            "stale_2024_remaining",
            "stale_2020_2023_remaining",
            "historical_end_before_2020_remaining",
        ):
            bucket = backfill_status.get(bucket_name, {})
            for row in (bucket.get("symbols") or [])[:10]:
                unresolved_samples.append({"bucket": bucket_name, **row})
        unresolved_df = pd.DataFrame(unresolved_samples)
        if not unresolved_df.empty:
            st.caption("Free-Source Unavailable Samples")
            st.dataframe(unresolved_df, use_container_width=True, hide_index=True)

    if not anomaly_rules.empty:
        st.caption("Anomaly Rules")
        st.dataframe(anomaly_rules, use_container_width=True, hide_index=True)

st.subheader("Latest Daily Update")
if not daily_update:
    st.info("No daily update summary found yet.")
else:
    execution = daily_update.get("execution", {})
    fetch = execution.get("fetch", {})
    col12, col13, col14, col15 = st.columns(4)
    col12.metric("Fetch Attempted", fetch.get("attempted_stock_codes", ""))
    col13.metric("Fetch Failed", fetch.get("failed_fetch_count", ""))
    col14.metric("Fetch Skipped", fetch.get("skipped_free_source_unavailable_count", ""))
    col15.metric("Files Changed", execution.get("files_changed", ""))

    update_summary = pd.DataFrame(
        [
            {
                "status": daily_update.get("status"),
                "source_path": execution.get("source_path"),
                "inserted_rows": execution.get("inserted_rows"),
                "conflict_rows": execution.get("conflict_rows"),
                "normalized_rows_synced": execution.get("normalized_rows_synced"),
                "requested_stock_codes": fetch.get("requested_stock_codes"),
                "attempted_stock_codes": fetch.get("attempted_stock_codes"),
                "failed_fetch_count": fetch.get("failed_fetch_count"),
                "skipped_free_source_unavailable_count": fetch.get(
                    "skipped_free_source_unavailable_count"
                ),
                "explicit_stock_codes": fetch.get("explicit_stock_codes"),
                "include_free_source_unavailable": fetch.get(
                    "include_free_source_unavailable"
                ),
            }
        ]
    )
    st.dataframe(update_summary, use_container_width=True, hide_index=True)

    failed_fetches = pd.DataFrame(fetch.get("failed_fetches", []))
    if not failed_fetches.empty:
        st.caption("Latest Fetch Failures")
        st.dataframe(failed_fetches, use_container_width=True, hide_index=True)

    skipped_fetches = pd.DataFrame(
        [{"stock_code": code} for code in fetch.get("skipped_free_source_unavailable_sample", [])]
    )
    if not skipped_fetches.empty:
        st.caption("Latest Skipped Free-Source Unavailable Samples")
        st.dataframe(skipped_fetches, use_container_width=True, hide_index=True)

st.subheader("Stock Drilldown")
default_code = "000001"
stock_code = st.text_input("Stock Code", value=default_code).strip() or default_code
sample = load_stock_sample(stock_code)
if sample.empty:
    st.warning(f"No rows found for stock_code={stock_code}")
else:
    st.dataframe(sample, use_container_width=True, hide_index=True)
    st.line_chart(sample.sort_values("trade_date").set_index("trade_date")[["close_price", "close_price_adj"]], height=320)
