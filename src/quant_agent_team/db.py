from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB_NAME = "quant_agent_team"
DEFAULT_DB_URL = f"postgresql:///{DEFAULT_DB_NAME}?host=/tmp"
DEFAULT_ADMIN_DB_URL = "postgresql:///postgres?host=/tmp"
PSQL_BIN = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/psql")
CREATEDB_BIN = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/createdb")


RAW_MARKET_DDL = """
CREATE TABLE IF NOT EXISTS raw_market_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  open_price NUMERIC,
  high_price NUMERIC,
  low_price NUMERIC,
  close_price NUMERIC,
  volume NUMERIC,
  turnover NUMERIC,
  raw_line_hash TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT raw_market_daily_stock_date_key UNIQUE (stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS normalized_market_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  open_price NUMERIC,
  high_price NUMERIC,
  low_price NUMERIC,
  close_price NUMERIC,
  close_price_adj NUMERIC,
  volume NUMERIC,
  turnover NUMERIC,
  adj_factor NUMERIC,
  is_suspended BOOLEAN,
  is_st BOOLEAN,
  limit_up_price NUMERIC,
  limit_down_price NUMERIC,
  industry_name TEXT,
  sector_name TEXT,
  theme_tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  source_raw_line_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT normalized_market_daily_stock_date_key UNIQUE (stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS raw_trading_constraints_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  adj_factor NUMERIC,
  is_suspended BOOLEAN,
  is_st BOOLEAN,
  limit_up_price NUMERIC,
  limit_down_price NUMERIC,
  raw_line_hash TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT raw_trading_constraints_daily_stock_date_key UNIQUE (stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS research_feature_store (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  feature_name TEXT NOT NULL,
  feature_value_num NUMERIC,
  feature_value_text TEXT,
  source_table TEXT NOT NULL DEFAULT 'normalized_market_daily',
  source_field TEXT NOT NULL DEFAULT 'close_price_adj',
  window_size INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT research_feature_store_feature_stock_date_key UNIQUE (feature_name, stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS research_feature_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  ma_5 NUMERIC,
  ma_10 NUMERIC,
  ma_20 NUMERIC,
  ma_60 NUMERIC,
  avg_volume_20d NUMERIC,
  avg_turnover_20d NUMERIC,
  volume_ratio_20d NUMERIC,
  ret_1d NUMERIC,
  ret_5d NUMERIC,
  ret_20d NUMERIC,
  momentum_20d NUMERIC,
  volatility_20d NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT research_feature_daily_stock_date_key UNIQUE (stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS raw_northbound_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  market_scope TEXT NOT NULL,
  rank_scope TEXT NOT NULL,
  close_price NUMERIC,
  price_change_pct NUMERIC,
  hold_shares NUMERIC,
  hold_value NUMERIC,
  hold_float_ratio NUMERIC,
  hold_total_ratio NUMERIC,
  estimated_increase_shares NUMERIC,
  estimated_increase_value NUMERIC,
  estimated_increase_value_pct NUMERIC,
  board_name TEXT,
  raw_line_hash TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT raw_northbound_daily_stock_date_scope_key UNIQUE (stock_code, trade_date, market_scope, rank_scope)
);

CREATE TABLE IF NOT EXISTS raw_attention_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  source_name TEXT NOT NULL DEFAULT 'eastmoney_hot_rank',
  attention_rank INTEGER,
  attention_level NUMERIC,
  latest_price NUMERIC,
  price_change_amount NUMERIC,
  price_change_pct NUMERIC,
  new_fans_ratio NUMERIC,
  loyal_fans_ratio NUMERIC,
  raw_line_hash TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT raw_attention_daily_stock_date_source_key UNIQUE (stock_code, trade_date, source_name)
);

CREATE TABLE IF NOT EXISTS raw_theme_membership_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  theme_type TEXT NOT NULL,
  theme_name TEXT NOT NULL,
  theme_code TEXT,
  source_name TEXT NOT NULL DEFAULT 'eastmoney',
  raw_line_hash TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT raw_theme_membership_daily_key UNIQUE (stock_code, trade_date, theme_type, theme_name)
);

CREATE TABLE IF NOT EXISTS raw_notice_event_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  report_scope TEXT NOT NULL,
  notice_type TEXT,
  announcement_event_tag TEXT,
  policy_event_tag TEXT,
  notice_content TEXT,
  notice_attach_url TEXT,
  notice_attach_type TEXT,
  earnings_event_tag TEXT,
  earnings_event_direction TEXT,
  earnings_event_strength_score NUMERIC,
  earnings_change_pct_lower NUMERIC,
  earnings_change_pct_upper NUMERIC,
  title TEXT NOT NULL,
  notice_url TEXT,
  raw_line_hash TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT raw_notice_event_daily_stock_date_title_key UNIQUE (stock_code, trade_date, report_scope, title)
);

CREATE TABLE IF NOT EXISTS research_market_context_daily (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  industry_name TEXT,
  sector_name TEXT,
  northbound_hold_shares NUMERIC,
  northbound_hold_value NUMERIC,
  northbound_hold_float_ratio NUMERIC,
  northbound_hold_total_ratio NUMERIC,
  northbound_holding_change_1d NUMERIC,
  northbound_holding_change_5d NUMERIC,
  northbound_estimated_increase_shares NUMERIC,
  northbound_estimated_increase_value NUMERIC,
  northbound_estimated_increase_value_pct NUMERIC,
  northbound_net_flow_proxy_1d NUMERIC,
  northbound_net_flow_proxy_5d NUMERIC,
  northbound_board_name TEXT,
  attention_rank INTEGER,
  attention_level NUMERIC,
  attention_change_3d NUMERIC,
  attention_change_5d NUMERIC,
  attention_latest_price NUMERIC,
  attention_price_change_amount NUMERIC,
  attention_price_change_pct NUMERIC,
  attention_new_fans_ratio NUMERIC,
  attention_loyal_fans_ratio NUMERIC,
  policy_event_tag TEXT,
  announcement_event_tag TEXT,
  announcement_count_1d INTEGER,
  notice_attach_type TEXT,
  earnings_event_tag TEXT,
  earnings_event_direction TEXT,
  earnings_event_strength_score NUMERIC,
  earnings_change_pct_lower NUMERIC,
  earnings_change_pct_upper NUMERIC,
  theme_tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  theme_breadth_score NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT research_market_context_daily_stock_date_key UNIQUE (stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS ingest_conflict_log (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  trade_date DATE NOT NULL,
  existing_raw_line_hash TEXT NOT NULL,
  incoming_raw_line_hash TEXT NOT NULL,
  existing_payload JSONB NOT NULL,
  incoming_payload JSONB NOT NULL,
  resolution TEXT NOT NULL DEFAULT 'manual_review_required',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id BIGSERIAL PRIMARY KEY,
  run_type TEXT NOT NULL,
  source_path TEXT,
  status TEXT NOT NULL,
  inserted_rows INTEGER NOT NULL DEFAULT 0,
  conflict_rows INTEGER NOT NULL DEFAULT 0,
  notes JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_source_file_state (
  source_path TEXT PRIMARY KEY,
  stock_code TEXT NOT NULL,
  file_hash TEXT NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  file_mtime_ns BIGINT NOT NULL DEFAULT 0,
  row_count INTEGER NOT NULL DEFAULT 0,
  latest_trade_date DATE,
  latest_trade_row_hash TEXT,
  last_ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE ingest_runs
  ADD COLUMN IF NOT EXISTS source_path TEXT;

ALTER TABLE ingest_runs
  ADD COLUMN IF NOT EXISTS inserted_rows INTEGER NOT NULL DEFAULT 0;

ALTER TABLE ingest_runs
  ADD COLUMN IF NOT EXISTS conflict_rows INTEGER NOT NULL DEFAULT 0;

ALTER TABLE ingest_runs
  ADD COLUMN IF NOT EXISTS notes JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE ingest_source_file_state
  ADD COLUMN IF NOT EXISTS file_mtime_ns BIGINT NOT NULL DEFAULT 0;

ALTER TABLE ingest_source_file_state
  ADD COLUMN IF NOT EXISTS latest_trade_row_hash TEXT;

ALTER TABLE raw_attention_daily
  ADD COLUMN IF NOT EXISTS attention_level NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS industry_name TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS sector_name TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS northbound_holding_change_1d NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS northbound_holding_change_5d NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS northbound_net_flow_proxy_1d NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS northbound_net_flow_proxy_5d NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS attention_level NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS attention_change_3d NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS attention_change_5d NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS policy_event_tag TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS announcement_event_tag TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS announcement_count_1d INTEGER;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS notice_content TEXT;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS notice_attach_url TEXT;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS notice_attach_type TEXT;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS earnings_event_tag TEXT;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS earnings_event_direction TEXT;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS earnings_event_strength_score NUMERIC;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS earnings_change_pct_lower NUMERIC;

ALTER TABLE raw_notice_event_daily
  ADD COLUMN IF NOT EXISTS earnings_change_pct_upper NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS notice_attach_type TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS earnings_event_tag TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS earnings_event_direction TEXT;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS earnings_event_strength_score NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS earnings_change_pct_lower NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS earnings_change_pct_upper NUMERIC;

ALTER TABLE research_market_context_daily
  ADD COLUMN IF NOT EXISTS theme_breadth_score NUMERIC;

ALTER TABLE raw_market_daily
  ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'cn';

ALTER TABLE normalized_market_daily
  ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'cn';
"""


def _resolve_bin(env_var: str, command: str, fallback: Path) -> Path:
    override = os.getenv(env_var)
    if override:
        return Path(override)
    found = shutil.which(command)
    if found:
        return Path(found)
    return fallback if fallback.exists() else Path(command)


@dataclass
class DatabaseConfig:
    db_url: str = DEFAULT_DB_URL
    admin_db_url: str = DEFAULT_ADMIN_DB_URL
    psql_bin: Path = PSQL_BIN
    createdb_bin: Path = CREATEDB_BIN

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            db_url=os.getenv("QUANT_DB_URL", DEFAULT_DB_URL),
            admin_db_url=os.getenv("QUANT_DB_ADMIN_URL", DEFAULT_ADMIN_DB_URL),
            psql_bin=_resolve_bin("QUANT_PSQL_BIN", "psql", PSQL_BIN),
            createdb_bin=_resolve_bin("QUANT_CREATEDB_BIN", "createdb", CREATEDB_BIN),
        )

    @property
    def db_name(self) -> str:
        no_query = self.db_url.split("?", 1)[0]
        name = no_query.rstrip("/").split("/")[-1]
        if not name:
            raise ValueError(f"Unsupported db url format: {self.db_url}")
        return name


class PostgresCli:
    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or DatabaseConfig.from_env()

    def ensure_database(self) -> None:
        result = self.run_admin_sql(
            f"SELECT 1 FROM pg_database WHERE datname = '{self.config.db_name}';"
        )
        if result.strip() == "1":
            return
        subprocess.run(
            [str(self.config.createdb_bin), "-h", "/tmp", self.config.db_name],
            check=True,
            capture_output=True,
            text=True,
        )

    def ensure_schema(self) -> None:
        self.run_sql(RAW_MARKET_DDL)

    def run_sql(self, sql: str, capture: bool = True) -> str:
        return self._run(self.config.db_url, sql, capture=capture)

    def run_admin_sql(self, sql: str, capture: bool = True) -> str:
        return self._run(self.config.admin_db_url, sql, capture=capture)

    def _run(self, db_url: str, sql: str, capture: bool = True) -> str:
        process = subprocess.run(
            [str(self.config.psql_bin), db_url, "-v", "ON_ERROR_STOP=1", "-Atqc", sql],
            check=True,
            capture_output=capture,
            text=True,
        )
        return process.stdout if capture else ""
