--
-- PostgreSQL database dump
--

\restrict MzrugaRJFZ8X5unMAT1ibChl4aiJfTH7lUMPVdfp2Jutymg8jTX7zEAv5Amf6qa

-- Dumped from database version 17.9 (Homebrew)
-- Dumped by pg_dump version 17.9 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE quant_agent_team;
--
-- Name: quant_agent_team; Type: DATABASE; Schema: -; Owner: laisicong
--

CREATE DATABASE quant_agent_team WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.UTF-8';


ALTER DATABASE quant_agent_team OWNER TO laisicong;

\unrestrict MzrugaRJFZ8X5unMAT1ibChl4aiJfTH7lUMPVdfp2Jutymg8jTX7zEAv5Amf6qa
\connect quant_agent_team
\restrict MzrugaRJFZ8X5unMAT1ibChl4aiJfTH7lUMPVdfp2Jutymg8jTX7zEAv5Amf6qa

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: attention_mirror_post_index; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.attention_mirror_post_index (
    id bigint NOT NULL,
    source_name text NOT NULL,
    maintainer_account text NOT NULL,
    status_id bigint NOT NULL,
    trade_date date,
    published_at timestamp with time zone,
    title text NOT NULL,
    post_url text NOT NULL,
    processing_status text,
    content_shape text,
    source_tags text[] DEFAULT '{}'::text[] NOT NULL,
    platform_mentions text[] DEFAULT '{}'::text[] NOT NULL,
    contains_sections text[] DEFAULT '{}'::text[] NOT NULL,
    matched_keywords text[] DEFAULT '{}'::text[] NOT NULL,
    excerpt text,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.attention_mirror_post_index OWNER TO laisicong;

--
-- Name: attention_mirror_post_index_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.attention_mirror_post_index_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attention_mirror_post_index_id_seq OWNER TO laisicong;

--
-- Name: attention_mirror_post_index_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.attention_mirror_post_index_id_seq OWNED BY public.attention_mirror_post_index.id;


--
-- Name: ingest_conflict_log; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.ingest_conflict_log (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    existing_raw_line_hash text NOT NULL,
    incoming_raw_line_hash text NOT NULL,
    existing_payload jsonb NOT NULL,
    incoming_payload jsonb NOT NULL,
    resolution text DEFAULT 'manual_review_required'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ingest_conflict_log OWNER TO laisicong;

--
-- Name: ingest_conflict_log_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.ingest_conflict_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ingest_conflict_log_id_seq OWNER TO laisicong;

--
-- Name: ingest_conflict_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.ingest_conflict_log_id_seq OWNED BY public.ingest_conflict_log.id;


--
-- Name: ingest_runs; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.ingest_runs (
    id bigint NOT NULL,
    run_type text NOT NULL,
    source_path text,
    status text NOT NULL,
    inserted_rows integer DEFAULT 0 NOT NULL,
    conflict_rows integer DEFAULT 0 NOT NULL,
    notes jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ingest_runs OWNER TO laisicong;

--
-- Name: ingest_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.ingest_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ingest_runs_id_seq OWNER TO laisicong;

--
-- Name: ingest_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.ingest_runs_id_seq OWNED BY public.ingest_runs.id;


--
-- Name: ingest_source_file_state; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.ingest_source_file_state (
    source_path text NOT NULL,
    stock_code text NOT NULL,
    file_hash text NOT NULL,
    file_size_bytes bigint NOT NULL,
    row_count integer DEFAULT 0 NOT NULL,
    latest_trade_date date,
    last_ingested_at timestamp with time zone DEFAULT now() NOT NULL,
    file_mtime_ns bigint DEFAULT 0 NOT NULL,
    latest_trade_row_hash text
);


ALTER TABLE public.ingest_source_file_state OWNER TO laisicong;

--
-- Name: normalized_market_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.normalized_market_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    open_price numeric,
    high_price numeric,
    low_price numeric,
    close_price numeric,
    close_price_adj numeric,
    volume numeric,
    turnover numeric,
    adj_factor numeric,
    is_suspended boolean,
    is_st boolean,
    limit_up_price numeric,
    limit_down_price numeric,
    industry_name text,
    sector_name text,
    theme_tags text[] DEFAULT '{}'::text[] NOT NULL,
    source_raw_line_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.normalized_market_daily OWNER TO laisicong;

--
-- Name: normalized_market_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.normalized_market_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.normalized_market_daily_id_seq OWNER TO laisicong;

--
-- Name: normalized_market_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.normalized_market_daily_id_seq OWNED BY public.normalized_market_daily.id;


--
-- Name: raw_attention_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.raw_attention_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    source_name text DEFAULT 'eastmoney_hot_rank'::text NOT NULL,
    attention_rank integer,
    latest_price numeric,
    price_change_amount numeric,
    price_change_pct numeric,
    new_fans_ratio numeric,
    loyal_fans_ratio numeric,
    raw_line_hash text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    attention_level numeric
);


ALTER TABLE public.raw_attention_daily OWNER TO laisicong;

--
-- Name: raw_attention_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.raw_attention_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_attention_daily_id_seq OWNER TO laisicong;

--
-- Name: raw_attention_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.raw_attention_daily_id_seq OWNED BY public.raw_attention_daily.id;


--
-- Name: raw_market_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.raw_market_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    open_price numeric,
    high_price numeric,
    low_price numeric,
    close_price numeric,
    volume numeric,
    turnover numeric,
    raw_line_hash text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_market_daily OWNER TO laisicong;

--
-- Name: raw_market_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.raw_market_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_market_daily_id_seq OWNER TO laisicong;

--
-- Name: raw_market_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.raw_market_daily_id_seq OWNED BY public.raw_market_daily.id;


--
-- Name: raw_northbound_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.raw_northbound_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    market_scope text NOT NULL,
    rank_scope text NOT NULL,
    close_price numeric,
    price_change_pct numeric,
    hold_shares numeric,
    hold_value numeric,
    hold_float_ratio numeric,
    hold_total_ratio numeric,
    estimated_increase_shares numeric,
    estimated_increase_value numeric,
    estimated_increase_value_pct numeric,
    board_name text,
    raw_line_hash text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_northbound_daily OWNER TO laisicong;

--
-- Name: raw_northbound_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.raw_northbound_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_northbound_daily_id_seq OWNER TO laisicong;

--
-- Name: raw_northbound_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.raw_northbound_daily_id_seq OWNED BY public.raw_northbound_daily.id;


--
-- Name: raw_notice_event_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.raw_notice_event_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    report_scope text NOT NULL,
    notice_type text,
    announcement_event_tag text,
    policy_event_tag text,
    title text NOT NULL,
    notice_url text,
    raw_line_hash text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    earnings_event_tag text,
    earnings_event_direction text,
    earnings_event_strength_score numeric,
    notice_content text,
    notice_attach_url text,
    notice_attach_type text,
    earnings_change_pct_lower numeric,
    earnings_change_pct_upper numeric
);


ALTER TABLE public.raw_notice_event_daily OWNER TO laisicong;

--
-- Name: raw_notice_event_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.raw_notice_event_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_notice_event_daily_id_seq OWNER TO laisicong;

--
-- Name: raw_notice_event_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.raw_notice_event_daily_id_seq OWNED BY public.raw_notice_event_daily.id;


--
-- Name: raw_theme_membership_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.raw_theme_membership_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    theme_type text NOT NULL,
    theme_name text NOT NULL,
    theme_code text,
    source_name text DEFAULT 'eastmoney'::text NOT NULL,
    raw_line_hash text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_theme_membership_daily OWNER TO laisicong;

--
-- Name: raw_theme_membership_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.raw_theme_membership_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_theme_membership_daily_id_seq OWNER TO laisicong;

--
-- Name: raw_theme_membership_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.raw_theme_membership_daily_id_seq OWNED BY public.raw_theme_membership_daily.id;


--
-- Name: raw_trading_constraints_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.raw_trading_constraints_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    adj_factor numeric,
    is_suspended boolean,
    is_st boolean,
    limit_up_price numeric,
    limit_down_price numeric,
    raw_line_hash text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_trading_constraints_daily OWNER TO laisicong;

--
-- Name: raw_trading_constraints_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.raw_trading_constraints_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_trading_constraints_daily_id_seq OWNER TO laisicong;

--
-- Name: raw_trading_constraints_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.raw_trading_constraints_daily_id_seq OWNED BY public.raw_trading_constraints_daily.id;


--
-- Name: research_feature_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.research_feature_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    ma_5 numeric,
    ma_10 numeric,
    ma_20 numeric,
    ma_60 numeric,
    avg_volume_20d numeric,
    avg_turnover_20d numeric,
    volume_ratio_20d numeric,
    ret_1d numeric,
    ret_5d numeric,
    ret_20d numeric,
    momentum_20d numeric,
    volatility_20d numeric,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.research_feature_daily OWNER TO laisicong;

--
-- Name: research_feature_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.research_feature_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.research_feature_daily_id_seq OWNER TO laisicong;

--
-- Name: research_feature_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.research_feature_daily_id_seq OWNED BY public.research_feature_daily.id;


--
-- Name: research_feature_store; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.research_feature_store (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    feature_name text NOT NULL,
    feature_value_num numeric,
    feature_value_text text,
    source_table text DEFAULT 'normalized_market_daily'::text NOT NULL,
    source_field text DEFAULT 'close_price_adj'::text NOT NULL,
    window_size integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.research_feature_store OWNER TO laisicong;

--
-- Name: research_feature_store_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.research_feature_store_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.research_feature_store_id_seq OWNER TO laisicong;

--
-- Name: research_feature_store_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.research_feature_store_id_seq OWNED BY public.research_feature_store.id;


--
-- Name: research_market_context_daily; Type: TABLE; Schema: public; Owner: laisicong
--

CREATE TABLE public.research_market_context_daily (
    id bigint NOT NULL,
    stock_code text NOT NULL,
    trade_date date NOT NULL,
    northbound_hold_shares numeric,
    northbound_hold_value numeric,
    northbound_hold_float_ratio numeric,
    northbound_hold_total_ratio numeric,
    northbound_estimated_increase_shares numeric,
    northbound_estimated_increase_value numeric,
    northbound_estimated_increase_value_pct numeric,
    northbound_board_name text,
    attention_rank integer,
    attention_latest_price numeric,
    attention_price_change_amount numeric,
    attention_price_change_pct numeric,
    attention_new_fans_ratio numeric,
    attention_loyal_fans_ratio numeric,
    theme_tags text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    industry_name text,
    sector_name text,
    northbound_holding_change_1d numeric,
    northbound_holding_change_5d numeric,
    northbound_net_flow_proxy_1d numeric,
    northbound_net_flow_proxy_5d numeric,
    attention_level numeric,
    attention_change_3d numeric,
    attention_change_5d numeric,
    theme_breadth_score numeric,
    policy_event_tag text,
    announcement_event_tag text,
    announcement_count_1d integer,
    attention_proxy_rank integer,
    attention_proxy_level numeric,
    attention_proxy_change_3d numeric,
    attention_proxy_change_5d numeric,
    earnings_event_tag text,
    earnings_event_direction text,
    earnings_event_strength_score numeric,
    notice_attach_type text,
    earnings_change_pct_lower numeric,
    earnings_change_pct_upper numeric
);


ALTER TABLE public.research_market_context_daily OWNER TO laisicong;

--
-- Name: research_market_context_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: laisicong
--

CREATE SEQUENCE public.research_market_context_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.research_market_context_daily_id_seq OWNER TO laisicong;

--
-- Name: research_market_context_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: laisicong
--

ALTER SEQUENCE public.research_market_context_daily_id_seq OWNED BY public.research_market_context_daily.id;


--
-- Name: attention_mirror_post_index id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.attention_mirror_post_index ALTER COLUMN id SET DEFAULT nextval('public.attention_mirror_post_index_id_seq'::regclass);


--
-- Name: ingest_conflict_log id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.ingest_conflict_log ALTER COLUMN id SET DEFAULT nextval('public.ingest_conflict_log_id_seq'::regclass);


--
-- Name: ingest_runs id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.ingest_runs ALTER COLUMN id SET DEFAULT nextval('public.ingest_runs_id_seq'::regclass);


--
-- Name: normalized_market_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.normalized_market_daily ALTER COLUMN id SET DEFAULT nextval('public.normalized_market_daily_id_seq'::regclass);


--
-- Name: raw_attention_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_attention_daily ALTER COLUMN id SET DEFAULT nextval('public.raw_attention_daily_id_seq'::regclass);


--
-- Name: raw_market_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_market_daily ALTER COLUMN id SET DEFAULT nextval('public.raw_market_daily_id_seq'::regclass);


--
-- Name: raw_northbound_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_northbound_daily ALTER COLUMN id SET DEFAULT nextval('public.raw_northbound_daily_id_seq'::regclass);


--
-- Name: raw_notice_event_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_notice_event_daily ALTER COLUMN id SET DEFAULT nextval('public.raw_notice_event_daily_id_seq'::regclass);


--
-- Name: raw_theme_membership_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_theme_membership_daily ALTER COLUMN id SET DEFAULT nextval('public.raw_theme_membership_daily_id_seq'::regclass);


--
-- Name: raw_trading_constraints_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_trading_constraints_daily ALTER COLUMN id SET DEFAULT nextval('public.raw_trading_constraints_daily_id_seq'::regclass);


--
-- Name: research_feature_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_feature_daily ALTER COLUMN id SET DEFAULT nextval('public.research_feature_daily_id_seq'::regclass);


--
-- Name: research_feature_store id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_feature_store ALTER COLUMN id SET DEFAULT nextval('public.research_feature_store_id_seq'::regclass);


--
-- Name: research_market_context_daily id; Type: DEFAULT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_market_context_daily ALTER COLUMN id SET DEFAULT nextval('public.research_market_context_daily_id_seq'::regclass);


--
-- Name: attention_mirror_post_index attention_mirror_post_index_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.attention_mirror_post_index
    ADD CONSTRAINT attention_mirror_post_index_pkey PRIMARY KEY (id);


--
-- Name: attention_mirror_post_index attention_mirror_post_index_source_status_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.attention_mirror_post_index
    ADD CONSTRAINT attention_mirror_post_index_source_status_key UNIQUE (source_name, status_id);


--
-- Name: ingest_conflict_log ingest_conflict_log_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.ingest_conflict_log
    ADD CONSTRAINT ingest_conflict_log_pkey PRIMARY KEY (id);


--
-- Name: ingest_runs ingest_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.ingest_runs
    ADD CONSTRAINT ingest_runs_pkey PRIMARY KEY (id);


--
-- Name: ingest_source_file_state ingest_source_file_state_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.ingest_source_file_state
    ADD CONSTRAINT ingest_source_file_state_pkey PRIMARY KEY (source_path);


--
-- Name: normalized_market_daily normalized_market_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.normalized_market_daily
    ADD CONSTRAINT normalized_market_daily_pkey PRIMARY KEY (id);


--
-- Name: normalized_market_daily normalized_market_daily_stock_date_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.normalized_market_daily
    ADD CONSTRAINT normalized_market_daily_stock_date_key UNIQUE (stock_code, trade_date);


--
-- Name: raw_attention_daily raw_attention_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_attention_daily
    ADD CONSTRAINT raw_attention_daily_pkey PRIMARY KEY (id);


--
-- Name: raw_attention_daily raw_attention_daily_raw_line_hash_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_attention_daily
    ADD CONSTRAINT raw_attention_daily_raw_line_hash_key UNIQUE (raw_line_hash);


--
-- Name: raw_attention_daily raw_attention_daily_stock_date_source_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_attention_daily
    ADD CONSTRAINT raw_attention_daily_stock_date_source_key UNIQUE (stock_code, trade_date, source_name);


--
-- Name: raw_market_daily raw_market_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_market_daily
    ADD CONSTRAINT raw_market_daily_pkey PRIMARY KEY (id);


--
-- Name: raw_market_daily raw_market_daily_raw_line_hash_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_market_daily
    ADD CONSTRAINT raw_market_daily_raw_line_hash_key UNIQUE (raw_line_hash);


--
-- Name: raw_market_daily raw_market_daily_stock_date_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_market_daily
    ADD CONSTRAINT raw_market_daily_stock_date_key UNIQUE (stock_code, trade_date);


--
-- Name: raw_northbound_daily raw_northbound_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_northbound_daily
    ADD CONSTRAINT raw_northbound_daily_pkey PRIMARY KEY (id);


--
-- Name: raw_northbound_daily raw_northbound_daily_raw_line_hash_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_northbound_daily
    ADD CONSTRAINT raw_northbound_daily_raw_line_hash_key UNIQUE (raw_line_hash);


--
-- Name: raw_northbound_daily raw_northbound_daily_stock_date_scope_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_northbound_daily
    ADD CONSTRAINT raw_northbound_daily_stock_date_scope_key UNIQUE (stock_code, trade_date, market_scope, rank_scope);


--
-- Name: raw_notice_event_daily raw_notice_event_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_notice_event_daily
    ADD CONSTRAINT raw_notice_event_daily_pkey PRIMARY KEY (id);


--
-- Name: raw_notice_event_daily raw_notice_event_daily_raw_line_hash_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_notice_event_daily
    ADD CONSTRAINT raw_notice_event_daily_raw_line_hash_key UNIQUE (raw_line_hash);


--
-- Name: raw_notice_event_daily raw_notice_event_daily_stock_date_title_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_notice_event_daily
    ADD CONSTRAINT raw_notice_event_daily_stock_date_title_key UNIQUE (stock_code, trade_date, report_scope, title);


--
-- Name: raw_theme_membership_daily raw_theme_membership_daily_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_theme_membership_daily
    ADD CONSTRAINT raw_theme_membership_daily_key UNIQUE (stock_code, trade_date, theme_type, theme_name);


--
-- Name: raw_theme_membership_daily raw_theme_membership_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_theme_membership_daily
    ADD CONSTRAINT raw_theme_membership_daily_pkey PRIMARY KEY (id);


--
-- Name: raw_theme_membership_daily raw_theme_membership_daily_raw_line_hash_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_theme_membership_daily
    ADD CONSTRAINT raw_theme_membership_daily_raw_line_hash_key UNIQUE (raw_line_hash);


--
-- Name: raw_trading_constraints_daily raw_trading_constraints_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_trading_constraints_daily
    ADD CONSTRAINT raw_trading_constraints_daily_pkey PRIMARY KEY (id);


--
-- Name: raw_trading_constraints_daily raw_trading_constraints_daily_raw_line_hash_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_trading_constraints_daily
    ADD CONSTRAINT raw_trading_constraints_daily_raw_line_hash_key UNIQUE (raw_line_hash);


--
-- Name: raw_trading_constraints_daily raw_trading_constraints_daily_stock_date_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.raw_trading_constraints_daily
    ADD CONSTRAINT raw_trading_constraints_daily_stock_date_key UNIQUE (stock_code, trade_date);


--
-- Name: research_feature_daily research_feature_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_feature_daily
    ADD CONSTRAINT research_feature_daily_pkey PRIMARY KEY (id);


--
-- Name: research_feature_daily research_feature_daily_stock_date_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_feature_daily
    ADD CONSTRAINT research_feature_daily_stock_date_key UNIQUE (stock_code, trade_date);


--
-- Name: research_feature_store research_feature_store_feature_stock_date_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_feature_store
    ADD CONSTRAINT research_feature_store_feature_stock_date_key UNIQUE (feature_name, stock_code, trade_date);


--
-- Name: research_feature_store research_feature_store_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_feature_store
    ADD CONSTRAINT research_feature_store_pkey PRIMARY KEY (id);


--
-- Name: research_market_context_daily research_market_context_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_market_context_daily
    ADD CONSTRAINT research_market_context_daily_pkey PRIMARY KEY (id);


--
-- Name: research_market_context_daily research_market_context_daily_stock_date_key; Type: CONSTRAINT; Schema: public; Owner: laisicong
--

ALTER TABLE ONLY public.research_market_context_daily
    ADD CONSTRAINT research_market_context_daily_stock_date_key UNIQUE (stock_code, trade_date);


--
-- PostgreSQL database dump complete
--

\unrestrict MzrugaRJFZ8X5unMAT1ibChl4aiJfTH7lUMPVdfp2Jutymg8jTX7zEAv5Amf6qa

