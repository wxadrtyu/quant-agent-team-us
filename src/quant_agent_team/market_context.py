from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import re
import signal
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

from .db import DEFAULT_DB_URL, PSQL_BIN, PostgresCli
from .market_fetch import _without_proxy_env


@dataclass(frozen=True)
class NorthboundRecord:
    stock_code: str
    trade_date: str
    market_scope: str
    rank_scope: str
    close_price: float | None
    price_change_pct: float | None
    hold_shares: float | None
    hold_value: float | None
    hold_float_ratio: float | None
    hold_total_ratio: float | None
    estimated_increase_shares: float | None
    estimated_increase_value: float | None
    estimated_increase_value_pct: float | None
    board_name: str | None
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class AttentionRecord:
    stock_code: str
    trade_date: str
    source_name: str
    attention_rank: int | None
    attention_level: float | None
    latest_price: float | None
    price_change_amount: float | None
    price_change_pct: float | None
    new_fans_ratio: float | None
    loyal_fans_ratio: float | None
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class ThemeMembershipRecord:
    stock_code: str
    trade_date: str
    theme_type: str
    theme_name: str
    theme_code: str | None
    source_name: str
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class NoticeEventRecord:
    stock_code: str
    trade_date: str
    report_scope: str
    notice_type: str | None
    announcement_event_tag: str | None
    policy_event_tag: str | None
    notice_content: str | None
    notice_attach_url: str | None
    notice_attach_type: str | None
    earnings_event_tag: str | None
    earnings_event_direction: str | None
    earnings_event_strength_score: float | None
    earnings_change_pct_lower: float | None
    earnings_change_pct_upper: float | None
    title: str
    notice_url: str | None
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class MarketContextRefreshResult:
    generated_at: str
    northbound_rows: int
    attention_rows: int
    notice_rows: int
    theme_rows: int
    context_rows_upserted: int
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "northbound_rows": self.northbound_rows,
            "attention_rows": self.attention_rows,
            "notice_rows": self.notice_rows,
            "theme_rows": self.theme_rows,
            "context_rows_upserted": self.context_rows_upserted,
            "notes": self.notes,
        }


def refresh_market_context(
    db: PostgresCli | None = None,
    stock_codes: Iterable[str] | None = None,
    top_n_attention: int = 100,
    attention_start_date: str | None = None,
    notice_start_date: str | None = None,
    context_start_date: str | None = "2025-01-01",
    theme_snapshot_date: str | None = None,
    include_industries: bool = True,
    include_concepts: bool = True,
    max_concepts: int = 60,
    max_industries: int | None = None,
) -> MarketContextRefreshResult:
    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()

    northbound_rows = fetch_northbound_records()
    if stock_codes:
        selected = {code for code in stock_codes}
        northbound_rows = [row for row in northbound_rows if row.stock_code in selected]

    attention_dates = _resolve_attention_history_dates(pg, attention_start_date)
    attention_rows = fetch_attention_records(
        top_n=top_n_attention,
        historical_dates=attention_dates,
    )
    notice_dates = _resolve_notice_history_dates(pg, notice_start_date or attention_start_date)
    notice_rows = fetch_notice_event_records(notice_dates)
    theme_rows = fetch_theme_membership_records(
        db=pg,
        stock_codes=stock_codes,
        context_start_date=context_start_date,
        snapshot_date=theme_snapshot_date,
        include_industries=include_industries,
        include_concepts=include_concepts,
        max_concepts=max_concepts,
        max_industries=max_industries,
    )
    if stock_codes:
        selected = {code for code in stock_codes}
        attention_rows = [row for row in attention_rows if row.stock_code in selected]
        notice_rows = [row for row in notice_rows if row.stock_code in selected]
        theme_rows = [row for row in theme_rows if row.stock_code in selected]

    if northbound_rows:
        _upsert_raw_northbound(pg, northbound_rows)
    if attention_rows:
        _upsert_raw_attention(pg, attention_rows)
    if notice_rows:
        _upsert_raw_notice_events(pg, notice_rows)
    if theme_rows:
        _upsert_raw_theme_memberships(pg, theme_rows)

    context_rows = _rebuild_market_context(
        pg,
        stock_codes=stock_codes,
        context_start_date=context_start_date,
    )
    notes = [
        "Northbound data currently uses AKShare Eastmoney ranking interfaces.",
        "Attention data uses Baidu hot search history plus live Eastmoney/Xueqiu fallback.",
        "Announcement events currently use Eastmoney notice report categories and title keyword normalization.",
        "Theme tags now use industry + concept membership snapshots from Eastmoney where available.",
        "Northbound board names remain as a fallback proxy when theme membership snapshots are missing.",
    ]
    return MarketContextRefreshResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        northbound_rows=len(northbound_rows),
        attention_rows=len(attention_rows),
        notice_rows=len(notice_rows),
        theme_rows=len(theme_rows),
        context_rows_upserted=context_rows,
        notes=notes,
    )


def fetch_northbound_records() -> List[NorthboundRecord]:
    import akshare as ak  # type: ignore

    records: list[NorthboundRecord] = []
    for market_scope in ["北向"]:
        for rank_scope in ["今日排行", "5日排行", "10日排行", "月排行"]:
            try:
                with _without_proxy_env():
                    frame = ak.stock_hsgt_hold_stock_em(market=market_scope, indicator=rank_scope)
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                code = _normalize_stock_code(row.get("代码"))
                trade_date = _normalize_trade_date(row.get("日期"))
                if not code or not trade_date:
                    continue
                payload = {str(key): _jsonable(value) for key, value in row.to_dict().items()}
                records.append(
                    NorthboundRecord(
                        stock_code=code,
                        trade_date=trade_date,
                        market_scope=market_scope,
                        rank_scope=rank_scope,
                        close_price=_to_float(row.get("今日收盘价")),
                        price_change_pct=_to_float(row.get("今日涨跌幅")),
                        hold_shares=_to_float(row.get("今日持股-股数")),
                        hold_value=_to_float(row.get("今日持股-市值")),
                        hold_float_ratio=_to_float(row.get("今日持股-占流通股比")),
                        hold_total_ratio=_to_float(row.get("今日持股-占总股本比")),
                        estimated_increase_shares=_to_float(row.get("今日增持估计-股数")),
                        estimated_increase_value=_to_float(row.get("今日增持估计-市值")),
                        estimated_increase_value_pct=_to_float(row.get("今日增持估计-市值增幅")),
                        board_name=_to_text(row.get("所属板块")),
                        raw_payload=payload,
                    )
                )
    deduped: dict[tuple[str, str, str, str], NorthboundRecord] = {}
    for row in records:
        deduped[(row.stock_code, row.trade_date, row.market_scope, row.rank_scope)] = row
    return list(deduped.values())


def fetch_attention_records(
    top_n: int = 100,
    historical_dates: Iterable[str] | None = None,
) -> List[AttentionRecord]:
    records: list[AttentionRecord] = []
    if historical_dates:
        records.extend(_fetch_baidu_attention_records(historical_dates, top_n=top_n))
    records.extend(_fetch_live_attention_records(top_n=top_n))
    deduped: dict[tuple[str, str, str], AttentionRecord] = {}
    for row in records:
        deduped[(row.stock_code, row.trade_date, row.source_name)] = row
    return list(deduped.values())


def fetch_notice_event_records(historical_dates: Iterable[str] | None = None) -> List[NoticeEventRecord]:
    import akshare as ak  # type: ignore

    if not historical_dates:
        return []
    report_scopes = ["重大事项", "财务报告", "风险提示", "持股变动"]
    records: list[NoticeEventRecord] = []
    for trade_date in historical_dates:
        for report_scope in report_scopes:
            try:
                with _without_proxy_env():
                    frame = ak.stock_notice_report(symbol=report_scope, date=trade_date.replace("-", ""))
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                stock_code = _normalize_stock_code(row.get("代码"))
                notice_date = _normalize_trade_date(row.get("公告日期")) or trade_date
                title = _to_text(row.get("公告标题"))
                if not stock_code or not notice_date or not title:
                    continue
                notice_type = _to_text(row.get("公告类型"))
                announcement_event_tag = _normalize_notice_event_tag(report_scope, notice_type)
                policy_event_tag = _classify_notice_policy_tag(title, notice_type, report_scope)
                earnings_event_tag, earnings_event_direction, earnings_event_strength_score = (
                    _classify_notice_earnings_tag(title, notice_type, report_scope)
                )
                payload = {str(key): _jsonable(value) for key, value in row.to_dict().items()}
                records.append(
                    NoticeEventRecord(
                        stock_code=stock_code,
                        trade_date=notice_date,
                        report_scope=report_scope,
                        notice_type=notice_type,
                        announcement_event_tag=announcement_event_tag,
                        policy_event_tag=policy_event_tag,
                        notice_content=None,
                        notice_attach_url=None,
                        notice_attach_type=None,
                        earnings_event_tag=earnings_event_tag,
                        earnings_event_direction=earnings_event_direction,
                        earnings_event_strength_score=earnings_event_strength_score,
                        earnings_change_pct_lower=None,
                        earnings_change_pct_upper=None,
                        title=title,
                        notice_url=_to_text(row.get("网址")),
                        raw_payload=payload,
                    )
                )
    deduped: dict[tuple[str, str, str, str], NoticeEventRecord] = {}
    for row in records:
        deduped[(row.stock_code, row.trade_date, row.report_scope, row.title)] = row
    return list(deduped.values())


def enhance_notice_earnings_details(
    db: PostgresCli,
    start_date: str = "2025-01-01",
    max_workers: int = 4,
) -> int:
    query = f"""
SELECT row_to_json(t)::text
FROM (
  SELECT id, stock_code, trade_date::text, report_scope, notice_type, title, notice_url
  FROM raw_notice_event_daily
  WHERE trade_date >= '{start_date}'::date
    AND (
      notice_type IN ('业绩预告', '业绩快报')
      OR title ~ '(业绩预告|业绩快报|年报|年度报告|季报|季度报告|中报|半年报|半年度报告|一季报|三季报|净利润|归母净利润|扣非净利润|预盈|预亏|预增|预减|扭亏|首亏|续亏|续盈|减亏|略增|略减|增亏)'
    )
  ORDER BY trade_date, stock_code, id
) AS t;
"""
    raw_rows = [row for row in db.run_sql(query).splitlines() if row.strip()]
    candidates = [json.loads(row) for row in raw_rows]

    enhanced: list[dict[str, object]] = []

    def _worker(item: dict[str, object]) -> dict[str, object]:
        title = _to_text(item.get("title")) or ""
        notice_type = _to_text(item.get("notice_type"))
        report_scope = _to_text(item.get("report_scope")) or ""
        notice_url = _to_text(item.get("notice_url"))
        info_code = _extract_notice_info_code(notice_url)
        detail = _fetch_notice_detail_payload(info_code) if info_code else None
        attach_url = _to_text((detail or {}).get("attach_url_web"))
        attach_type = _to_text((detail or {}).get("attach_type"))
        notice_content = _to_text((detail or {}).get("notice_content"))
        pdf_text = None
        if attach_type == "0" and attach_url:
            pdf_text = _download_pdf_text(attach_url)
        combined_content = "\n".join(part for part in [notice_content, pdf_text] if part).strip() or None
        (
            earnings_event_tag,
            earnings_event_direction,
            earnings_event_strength_score,
            earnings_change_pct_lower,
            earnings_change_pct_upper,
        ) = _classify_notice_earnings_details(
            title=title,
            notice_type=notice_type,
            report_scope=report_scope,
            notice_content=combined_content,
            notice_attach_type=attach_type,
        )
        return {
            "id": int(item["id"]),
            "notice_content": combined_content,
            "notice_attach_url": attach_url,
            "notice_attach_type": attach_type,
            "earnings_event_tag": earnings_event_tag,
            "earnings_event_direction": earnings_event_direction,
            "earnings_event_strength_score": earnings_event_strength_score,
            "earnings_change_pct_lower": earnings_change_pct_lower,
            "earnings_change_pct_upper": earnings_change_pct_upper,
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_worker, item) for item in candidates if _is_notice_earnings_candidate(_to_text(item.get("title")) or "", _to_text(item.get("notice_type")), _to_text(item.get("report_scope")) or "")]
        for future in as_completed(futures):
            try:
                enhanced.append(future.result())
            except Exception:
                continue

    _update_notice_earnings_enrichment(db, enhanced)
    return len(enhanced)


def fetch_theme_membership_records(
    db: PostgresCli,
    stock_codes: Iterable[str] | None = None,
    context_start_date: str | None = "2025-01-01",
    snapshot_date: str | None = None,
    include_industries: bool = True,
    include_concepts: bool = True,
    max_concepts: int = 60,
    max_industries: int | None = None,
) -> List[ThemeMembershipRecord]:
    snapshot_date = snapshot_date or datetime.now().date().isoformat()
    records: list[ThemeMembershipRecord] = []
    target_codes = _resolve_theme_stock_codes(db, stock_codes, context_start_date)
    if include_industries:
        industry_rows = _fetch_cninfo_industry_profile_rows(
            stock_codes=target_codes,
            max_stocks=max_industries,
        )
        for row in industry_rows:
            records.append(
                ThemeMembershipRecord(
                    stock_code=row["stock_code"],
                    trade_date=snapshot_date,
                    theme_type="industry",
                    theme_name=row["industry_name"],
                    theme_code=row.get("industry_code"),
                    source_name="cninfo_profile",
                    raw_payload=row["raw_payload"],
                )
            )

    if include_concepts:
        import akshare as ak  # type: ignore

        try:
            with _without_proxy_env():
                concept_frame = _call_with_timeout(ak.stock_board_concept_name_em, timeout_seconds=15)
        except Exception:
            concept_frame = None
        if concept_frame is not None and not concept_frame.empty:
            if "排名" in concept_frame.columns:
                concept_frame = concept_frame.sort_values("排名")
            for _, row in concept_frame.head(max_concepts).iterrows():
                theme_name = _to_text(row.get("板块名称"))
                if not theme_name:
                    continue
                theme_code = _to_text(row.get("板块代码"))
                try:
                    with _without_proxy_env():
                        cons = _call_with_timeout(
                            ak.stock_board_concept_cons_em,
                            symbol=theme_name,
                            timeout_seconds=12,
                        )
                except Exception:
                    continue
                if cons is None or cons.empty:
                    continue
                for _, member in cons.iterrows():
                    stock_code = _normalize_stock_code(member.get("代码"))
                    if not stock_code or stock_code not in target_codes:
                        continue
                    payload = {
                        "concept_name": theme_name,
                        "concept_code": theme_code,
                        "member": {str(k): _jsonable(v) for k, v in member.to_dict().items()},
                    }
                    records.append(
                        ThemeMembershipRecord(
                            stock_code=stock_code,
                            trade_date=snapshot_date,
                            theme_type="concept",
                            theme_name=theme_name,
                            theme_code=theme_code,
                            source_name="eastmoney",
                            raw_payload=payload,
                        )
                    )

    deduped: dict[tuple[str, str, str, str], ThemeMembershipRecord] = {}
    for row in records:
        deduped[(row.stock_code, row.trade_date, row.theme_type, row.theme_name)] = row
    return list(deduped.values())


def _fetch_live_attention_records(top_n: int = 100) -> List[AttentionRecord]:
    import akshare as ak  # type: ignore

    try:
        with _without_proxy_env():
            frame = ak.stock_hot_rank_em()
    except Exception:
        frame = None
    if frame is None or frame.empty:
        try:
            with _without_proxy_env():
                frame = ak.stock_hot_follow_xq(symbol="最热门")
        except Exception:
            return []
        if frame is None or frame.empty:
            return []
        records: list[AttentionRecord] = []
        today = datetime.now().date().isoformat()
        for rank_index, (_, row) in enumerate(frame.head(top_n).iterrows(), start=1):
            stock_code = _normalize_stock_code(row.get("股票代码"))
            if not stock_code:
                continue
            payload = {str(key): _jsonable(value) for key, value in row.to_dict().items()}
            records.append(
                AttentionRecord(
                    stock_code=stock_code,
                    trade_date=today,
                    source_name="xueqiu_follow_rank",
                    attention_rank=rank_index,
                    attention_level=float(max(top_n - rank_index + 1, 1)),
                    latest_price=_to_float(row.get("最新价")),
                    price_change_amount=None,
                    price_change_pct=None,
                    new_fans_ratio=None,
                    loyal_fans_ratio=None,
                    raw_payload=payload,
                )
            )
        return records

    records: list[AttentionRecord] = []
    for _, row in frame.head(top_n).iterrows():
        symbol = _to_text(row.get("代码"))
        stock_code = _normalize_stock_code(symbol)
        if not stock_code:
            continue
        detail_symbol = symbol if symbol and len(symbol) > 6 else _em_symbol(stock_code)
        detail_trade_date = None
        new_fans_ratio = None
        loyal_fans_ratio = None
        try:
            with _without_proxy_env():
                detail = ak.stock_hot_rank_detail_em(symbol=detail_symbol)
            if detail is not None and not detail.empty:
                latest = detail.iloc[-1]
                detail_trade_date = _normalize_trade_date(latest.get("时间"))
                new_fans_ratio = _to_float(latest.get("新晋粉丝"))
                loyal_fans_ratio = _to_float(latest.get("铁杆粉丝"))
        except Exception:
            detail = None

        trade_date = detail_trade_date or datetime.now().date().isoformat()
        payload = {str(key): _jsonable(value) for key, value in row.to_dict().items()}
        if detail is not None and not detail.empty:
            payload["detail_latest"] = {str(key): _jsonable(value) for key, value in detail.iloc[-1].to_dict().items()}
        records.append(
            AttentionRecord(
                stock_code=stock_code,
                trade_date=trade_date,
                source_name="eastmoney_hot_rank",
                attention_rank=_to_int(row.get("当前排名")),
                attention_level=float(max(top_n - (_to_int(row.get("当前排名")) or top_n) + 1, 1)),
                latest_price=_to_float(row.get("最新价")),
                price_change_amount=_to_float(row.get("涨跌额")),
                price_change_pct=_to_float(row.get("涨跌幅")),
                new_fans_ratio=new_fans_ratio,
                loyal_fans_ratio=loyal_fans_ratio,
                raw_payload=payload,
            )
        )
    return records


def _fetch_baidu_attention_records(
    historical_dates: Iterable[str],
    top_n: int,
) -> List[AttentionRecord]:
    import akshare as ak  # type: ignore

    name_to_code = _load_stock_name_code_map()
    records: list[AttentionRecord] = []
    for trade_date in historical_dates:
        ymd = trade_date.replace("-", "")
        try:
            with _without_proxy_env():
                frame = ak.stock_hot_search_baidu(symbol="A股", date=ymd, time="今日")
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        for rank_index, (_, row) in enumerate(frame.head(top_n).iterrows(), start=1):
            stock_code = _resolve_code_from_name_cell(row.get("名称/代码"), name_to_code)
            if not stock_code:
                continue
            payload = {str(key): _jsonable(value) for key, value in row.to_dict().items()}
            records.append(
                AttentionRecord(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    source_name="baidu_hot_search",
                    attention_rank=rank_index,
                    attention_level=_to_float(row.get("综合热度")),
                    latest_price=None,
                    price_change_amount=None,
                    price_change_pct=_to_pct_float(row.get("涨跌幅")),
                    new_fans_ratio=None,
                    loyal_fans_ratio=None,
                    raw_payload=payload,
                )
            )
    return records


def _upsert_raw_northbound(db: PostgresCli, rows: Iterable[NorthboundRecord]) -> None:
    values = []
    for row in rows:
        values.append(
            "("
            f"'{row.stock_code}', "
            f"'{row.trade_date}'::date, "
            f"{_sql_text(row.market_scope)}, "
            f"{_sql_text(row.rank_scope)}, "
            f"{_sql_num(row.close_price)}, "
            f"{_sql_num(row.price_change_pct)}, "
            f"{_sql_num(row.hold_shares)}, "
            f"{_sql_num(row.hold_value)}, "
            f"{_sql_num(row.hold_float_ratio)}, "
            f"{_sql_num(row.hold_total_ratio)}, "
            f"{_sql_num(row.estimated_increase_shares)}, "
            f"{_sql_num(row.estimated_increase_value)}, "
            f"{_sql_num(row.estimated_increase_value_pct)}, "
            f"{_sql_text(row.board_name)}, "
            f"{_sql_text(_hash_payload(row.raw_payload, row.stock_code, row.trade_date, row.market_scope, row.rank_scope))}, "
            f"{_sql_json(row.raw_payload)}"
            ")"
        )
    for batch in _chunked(values, 200):
        db.run_sql(
            f"""
INSERT INTO raw_northbound_daily (
  stock_code, trade_date, market_scope, rank_scope,
  close_price, price_change_pct, hold_shares, hold_value,
  hold_float_ratio, hold_total_ratio,
  estimated_increase_shares, estimated_increase_value, estimated_increase_value_pct,
  board_name, raw_line_hash, raw_payload
)
VALUES
  {", ".join(batch)}
ON CONFLICT (stock_code, trade_date, market_scope, rank_scope) DO UPDATE SET
  close_price = EXCLUDED.close_price,
  price_change_pct = EXCLUDED.price_change_pct,
  hold_shares = EXCLUDED.hold_shares,
  hold_value = EXCLUDED.hold_value,
  hold_float_ratio = EXCLUDED.hold_float_ratio,
  hold_total_ratio = EXCLUDED.hold_total_ratio,
  estimated_increase_shares = EXCLUDED.estimated_increase_shares,
  estimated_increase_value = EXCLUDED.estimated_increase_value,
  estimated_increase_value_pct = EXCLUDED.estimated_increase_value_pct,
  board_name = EXCLUDED.board_name,
  raw_line_hash = EXCLUDED.raw_line_hash,
  raw_payload = EXCLUDED.raw_payload,
  updated_at = NOW();
"""
        )


def _upsert_raw_attention(db: PostgresCli, rows: Iterable[AttentionRecord]) -> None:
    values = []
    for row in rows:
        values.append(
            "("
            f"'{row.stock_code}', "
            f"'{row.trade_date}'::date, "
            f"{_sql_text(row.source_name)}, "
            f"{_sql_int(row.attention_rank)}, "
            f"{_sql_num(row.attention_level)}, "
            f"{_sql_num(row.latest_price)}, "
            f"{_sql_num(row.price_change_amount)}, "
            f"{_sql_num(row.price_change_pct)}, "
            f"{_sql_num(row.new_fans_ratio)}, "
            f"{_sql_num(row.loyal_fans_ratio)}, "
            f"{_sql_text(_hash_payload(row.raw_payload, row.stock_code, row.trade_date, row.source_name))}, "
            f"{_sql_json(row.raw_payload)}"
            ")"
        )
    for batch in _chunked(values, 200):
        db.run_sql(
            f"""
INSERT INTO raw_attention_daily (
  stock_code, trade_date, source_name, attention_rank, attention_level,
  latest_price, price_change_amount, price_change_pct,
  new_fans_ratio, loyal_fans_ratio, raw_line_hash, raw_payload
)
VALUES
  {", ".join(batch)}
ON CONFLICT (stock_code, trade_date, source_name) DO UPDATE SET
  attention_rank = EXCLUDED.attention_rank,
  attention_level = EXCLUDED.attention_level,
  latest_price = EXCLUDED.latest_price,
  price_change_amount = EXCLUDED.price_change_amount,
  price_change_pct = EXCLUDED.price_change_pct,
  new_fans_ratio = EXCLUDED.new_fans_ratio,
  loyal_fans_ratio = EXCLUDED.loyal_fans_ratio,
  raw_line_hash = EXCLUDED.raw_line_hash,
  raw_payload = EXCLUDED.raw_payload,
  updated_at = NOW();
"""
        )


def _upsert_raw_theme_memberships(db: PostgresCli, rows: Iterable[ThemeMembershipRecord]) -> None:
    values = []
    for row in rows:
        values.append(
            "("
            f"'{row.stock_code}', "
            f"'{row.trade_date}'::date, "
            f"{_sql_text(row.theme_type)}, "
            f"{_sql_text(row.theme_name)}, "
            f"{_sql_text(row.theme_code)}, "
            f"{_sql_text(row.source_name)}, "
            f"{_sql_text(_hash_payload(row.raw_payload, row.stock_code, row.trade_date, row.theme_type, row.theme_name))}, "
            f"{_sql_json(row.raw_payload)}"
            ")"
        )
    for batch in _chunked(values, 200):
        db.run_sql(
            f"""
INSERT INTO raw_theme_membership_daily (
  stock_code, trade_date, theme_type, theme_name, theme_code, source_name,
  raw_line_hash, raw_payload
)
VALUES
  {", ".join(batch)}
ON CONFLICT (stock_code, trade_date, theme_type, theme_name) DO UPDATE SET
  theme_code = EXCLUDED.theme_code,
  source_name = EXCLUDED.source_name,
  raw_line_hash = EXCLUDED.raw_line_hash,
  raw_payload = EXCLUDED.raw_payload,
  updated_at = NOW();
"""
        )


def _upsert_raw_notice_events(db: PostgresCli, rows: Iterable[NoticeEventRecord]) -> None:
    rows = list(rows)
    if not rows:
        return
    with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False) as handle:
        temp_path = Path(handle.name)
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(
                [
                    row.stock_code,
                    row.trade_date,
                    row.report_scope,
                    row.notice_type or "",
                    row.announcement_event_tag or "",
                    row.policy_event_tag or "",
                    row.notice_content or "",
                    row.notice_attach_url or "",
                    row.notice_attach_type or "",
                    row.earnings_event_tag or "",
                    row.earnings_event_direction or "",
                    "" if row.earnings_event_strength_score is None else row.earnings_event_strength_score,
                    "" if row.earnings_change_pct_lower is None else row.earnings_change_pct_lower,
                    "" if row.earnings_change_pct_upper is None else row.earnings_change_pct_upper,
                    row.title,
                    row.notice_url or "",
                    _hash_payload(row.raw_payload, row.stock_code, row.trade_date, row.report_scope, row.title),
                    json.dumps(row.raw_payload, ensure_ascii=False),
                ]
            )
    sql = f"""
DROP TABLE IF EXISTS tmp_raw_notice_event_daily;
CREATE TEMP TABLE tmp_raw_notice_event_daily (
  stock_code TEXT,
  trade_date DATE,
  report_scope TEXT,
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
  title TEXT,
  notice_url TEXT,
  raw_line_hash TEXT,
  raw_payload JSONB
);
\\copy tmp_raw_notice_event_daily FROM '{temp_path}' WITH (FORMAT CSV);
INSERT INTO raw_notice_event_daily (
  stock_code, trade_date, report_scope, notice_type,
  announcement_event_tag, policy_event_tag, notice_content, notice_attach_url, notice_attach_type,
  earnings_event_tag, earnings_event_direction, earnings_event_strength_score,
  earnings_change_pct_lower, earnings_change_pct_upper,
  title, notice_url, raw_line_hash, raw_payload
)
SELECT
  stock_code, trade_date, report_scope, NULLIF(notice_type, ''),
  NULLIF(announcement_event_tag, ''), NULLIF(policy_event_tag, ''), NULLIF(notice_content, ''), NULLIF(notice_attach_url, ''), NULLIF(notice_attach_type, ''),
  NULLIF(earnings_event_tag, ''), NULLIF(earnings_event_direction, ''), earnings_event_strength_score,
  earnings_change_pct_lower, earnings_change_pct_upper,
  title, NULLIF(notice_url, ''), raw_line_hash, raw_payload
FROM tmp_raw_notice_event_daily
ON CONFLICT (stock_code, trade_date, report_scope, title) DO UPDATE SET
  notice_type = EXCLUDED.notice_type,
  announcement_event_tag = EXCLUDED.announcement_event_tag,
  policy_event_tag = EXCLUDED.policy_event_tag,
  notice_content = COALESCE(EXCLUDED.notice_content, raw_notice_event_daily.notice_content),
  notice_attach_url = COALESCE(EXCLUDED.notice_attach_url, raw_notice_event_daily.notice_attach_url),
  notice_attach_type = COALESCE(EXCLUDED.notice_attach_type, raw_notice_event_daily.notice_attach_type),
  earnings_event_tag = EXCLUDED.earnings_event_tag,
  earnings_event_direction = EXCLUDED.earnings_event_direction,
  earnings_event_strength_score = EXCLUDED.earnings_event_strength_score,
  earnings_change_pct_lower = EXCLUDED.earnings_change_pct_lower,
  earnings_change_pct_upper = EXCLUDED.earnings_change_pct_upper,
  notice_url = EXCLUDED.notice_url,
  raw_line_hash = EXCLUDED.raw_line_hash,
  raw_payload = EXCLUDED.raw_payload,
  updated_at = NOW();
"""
    try:
        subprocess.run(
            [str(PSQL_BIN), DEFAULT_DB_URL, "-v", "ON_ERROR_STOP=1", "-f", "-"],
            input=sql,
            check=True,
            text=True,
        )
    finally:
        temp_path.unlink(missing_ok=True)


def _update_notice_earnings_enrichment(db: PostgresCli, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        return
    with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False) as handle:
        temp_path = Path(handle.name)
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(
                [
                    int(row["id"]),
                    _to_text(row.get("notice_content")) or "",
                    _to_text(row.get("notice_attach_url")) or "",
                    _to_text(row.get("notice_attach_type")) or "",
                    _to_text(row.get("earnings_event_tag")) or "",
                    _to_text(row.get("earnings_event_direction")) or "",
                    "" if row.get("earnings_event_strength_score") is None else row.get("earnings_event_strength_score"),
                    "" if row.get("earnings_change_pct_lower") is None else row.get("earnings_change_pct_lower"),
                    "" if row.get("earnings_change_pct_upper") is None else row.get("earnings_change_pct_upper"),
                ]
            )
    sql = f"""
DROP TABLE IF EXISTS tmp_notice_earnings_enrichment;
CREATE TEMP TABLE tmp_notice_earnings_enrichment (
  id BIGINT PRIMARY KEY,
  notice_content TEXT,
  notice_attach_url TEXT,
  notice_attach_type TEXT,
  earnings_event_tag TEXT,
  earnings_event_direction TEXT,
  earnings_event_strength_score NUMERIC,
  earnings_change_pct_lower NUMERIC,
  earnings_change_pct_upper NUMERIC
);
\\copy tmp_notice_earnings_enrichment FROM '{temp_path}' WITH (FORMAT CSV);
UPDATE raw_notice_event_daily AS dst
SET
  notice_content = NULLIF(src.notice_content, ''),
  notice_attach_url = NULLIF(src.notice_attach_url, ''),
  notice_attach_type = NULLIF(src.notice_attach_type, ''),
  earnings_event_tag = NULLIF(src.earnings_event_tag, ''),
  earnings_event_direction = NULLIF(src.earnings_event_direction, ''),
  earnings_event_strength_score = src.earnings_event_strength_score,
  earnings_change_pct_lower = src.earnings_change_pct_lower,
  earnings_change_pct_upper = src.earnings_change_pct_upper,
  updated_at = NOW()
FROM tmp_notice_earnings_enrichment AS src
WHERE dst.id = src.id;
"""
    try:
        subprocess.run(
            [str(PSQL_BIN), DEFAULT_DB_URL, "-v", "ON_ERROR_STOP=1", "-f", "-"],
            input=sql,
            check=True,
            text=True,
        )
    finally:
        temp_path.unlink(missing_ok=True)


def _rebuild_market_context(
    db: PostgresCli,
    stock_codes: Iterable[str] | None = None,
    context_start_date: str | None = "2025-01-01",
) -> int:
    conditions = []
    if stock_codes:
        quoted = ", ".join(_sql_text(code) for code in sorted({code for code in stock_codes if code}))
        conditions.append(f"stock_code IN ({quoted})")
    if context_start_date:
        conditions.append(f"trade_date >= '{context_start_date}'::date")
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    board_where_sql = ""
    if stock_codes:
        quoted = ", ".join(_sql_text(code) for code in sorted({code for code in stock_codes if code}))
        board_where_sql = f"WHERE stock_code IN ({quoted}) AND board_name IS NOT NULL"
    else:
        board_where_sql = "WHERE board_name IS NOT NULL"

    db.run_sql(
        f"""
WITH latest_northbound AS (
  SELECT DISTINCT ON (stock_code, trade_date)
    stock_code,
    trade_date,
    hold_shares,
    hold_value,
    hold_float_ratio,
    hold_total_ratio,
    estimated_increase_shares,
    estimated_increase_value,
    estimated_increase_value_pct,
    board_name
  FROM raw_northbound_daily
  {where_sql}
  ORDER BY stock_code, trade_date, rank_scope = '今日排行' DESC, updated_at DESC
),
static_board AS (
  SELECT DISTINCT ON (stock_code)
    stock_code,
    board_name
  FROM raw_northbound_daily
  {board_where_sql}
  ORDER BY stock_code, trade_date DESC, rank_scope = '今日排行' DESC, updated_at DESC
),
theme_latest AS (
  SELECT DISTINCT ON (stock_code, theme_type, theme_name)
    stock_code,
    theme_type,
    theme_name
  FROM raw_theme_membership_daily
  {where_sql}
  ORDER BY stock_code, theme_type, theme_name, trade_date DESC
),
theme_agg AS (
  SELECT
    stock_code,
    MAX(CASE WHEN theme_type = 'industry' THEN theme_name END) AS industry_name,
    MAX(CASE WHEN theme_type = 'industry' THEN theme_name END) AS sector_name,
    ARRAY_AGG(theme_name) FILTER (WHERE theme_type = 'concept') AS theme_tags
  FROM theme_latest
  GROUP BY stock_code
),
theme_counts AS (
  SELECT theme_name, COUNT(*)::numeric AS theme_breadth_score
  FROM theme_latest
  WHERE theme_type = 'concept'
  GROUP BY theme_name
),
theme_breadth AS (
  SELECT
    theme_latest.stock_code,
    MAX(theme_counts.theme_breadth_score) AS theme_breadth_score
  FROM theme_latest
  JOIN theme_counts
    ON theme_counts.theme_name = theme_latest.theme_name
  WHERE theme_latest.theme_type = 'concept'
  GROUP BY theme_latest.stock_code
),
enriched_northbound AS (
  SELECT
    stock_code,
    trade_date,
    hold_shares,
    hold_value,
    hold_float_ratio,
    hold_total_ratio,
    hold_value - LAG(hold_value, 1) OVER (PARTITION BY stock_code ORDER BY trade_date) AS holding_change_1d,
    hold_value - LAG(hold_value, 5) OVER (PARTITION BY stock_code ORDER BY trade_date) AS holding_change_5d,
    estimated_increase_shares,
    estimated_increase_value,
    estimated_increase_value_pct,
    COALESCE(
      estimated_increase_value,
      hold_value - LAG(hold_value, 1) OVER (PARTITION BY stock_code ORDER BY trade_date)
    ) AS net_flow_proxy_1d,
    COALESCE(
      estimated_increase_value,
      hold_value - LAG(hold_value, 5) OVER (PARTITION BY stock_code ORDER BY trade_date)
    ) AS net_flow_proxy_5d,
    board_name
  FROM latest_northbound
),
latest_attention AS (
  SELECT DISTINCT ON (stock_code, trade_date)
    stock_code,
    trade_date,
    attention_rank,
    attention_level,
    latest_price,
    price_change_amount,
    price_change_pct,
    new_fans_ratio,
    loyal_fans_ratio
  FROM raw_attention_daily
  {where_sql}
  ORDER BY stock_code, trade_date,
    (source_name = 'eastmoney_hot_rank') DESC,
    (source_name = 'xueqiu_follow_rank') DESC,
    (source_name = 'baidu_hot_search') DESC,
    updated_at DESC
),
enriched_attention AS (
  SELECT
    stock_code,
    trade_date,
    attention_rank,
    attention_level,
    CASE
      WHEN LAG(attention_level, 3) OVER (PARTITION BY stock_code ORDER BY trade_date) IS NULL
        OR LAG(attention_level, 3) OVER (PARTITION BY stock_code ORDER BY trade_date) = 0
      THEN NULL
      ELSE attention_level / LAG(attention_level, 3) OVER (PARTITION BY stock_code ORDER BY trade_date) - 1
    END AS attention_change_3d,
    CASE
      WHEN LAG(attention_level, 5) OVER (PARTITION BY stock_code ORDER BY trade_date) IS NULL
        OR LAG(attention_level, 5) OVER (PARTITION BY stock_code ORDER BY trade_date) = 0
      THEN NULL
      ELSE attention_level / LAG(attention_level, 5) OVER (PARTITION BY stock_code ORDER BY trade_date) - 1
    END AS attention_change_5d,
    latest_price,
    price_change_amount,
    price_change_pct,
    new_fans_ratio,
    loyal_fans_ratio
  FROM latest_attention
),
notice_daily AS (
  SELECT
    stock_code,
    trade_date,
    STRING_AGG(DISTINCT announcement_event_tag, '|' ORDER BY announcement_event_tag)
      FILTER (WHERE announcement_event_tag IS NOT NULL AND announcement_event_tag <> '') AS announcement_event_tag,
    STRING_AGG(DISTINCT policy_event_tag, '|' ORDER BY policy_event_tag)
      FILTER (WHERE policy_event_tag IS NOT NULL AND policy_event_tag <> '') AS policy_event_tag,
    STRING_AGG(DISTINCT notice_attach_type, '|' ORDER BY notice_attach_type)
      FILTER (WHERE notice_attach_type IS NOT NULL AND notice_attach_type <> '') AS notice_attach_type,
    STRING_AGG(DISTINCT earnings_event_tag, '|' ORDER BY earnings_event_tag)
      FILTER (WHERE earnings_event_tag IS NOT NULL AND earnings_event_tag <> '') AS earnings_event_tag,
    STRING_AGG(DISTINCT earnings_event_direction, '|' ORDER BY earnings_event_direction)
      FILTER (WHERE earnings_event_direction IS NOT NULL AND earnings_event_direction <> '') AS earnings_event_direction,
    MAX(earnings_event_strength_score) AS earnings_event_strength_score,
    MAX(earnings_change_pct_lower) AS earnings_change_pct_lower,
    MAX(earnings_change_pct_upper) AS earnings_change_pct_upper,
    COUNT(*)::integer AS announcement_count_1d
  FROM raw_notice_event_daily
  {where_sql}
  GROUP BY stock_code, trade_date
),
keys AS (
  SELECT stock_code, trade_date FROM normalized_market_daily
  {where_sql}
  UNION
  SELECT stock_code, trade_date FROM enriched_northbound
  UNION
  SELECT stock_code, trade_date FROM enriched_attention
  UNION
  SELECT stock_code, trade_date FROM notice_daily
),
board_breadth AS (
  SELECT
    keys.trade_date,
    board.board_name,
    COUNT(*)::numeric AS theme_breadth_score
  FROM keys
  JOIN static_board AS board
    ON board.stock_code = keys.stock_code
  GROUP BY keys.trade_date, board.board_name
)
INSERT INTO research_market_context_daily (
  stock_code, trade_date,
  industry_name, sector_name,
  northbound_hold_shares, northbound_hold_value,
  northbound_hold_float_ratio, northbound_hold_total_ratio,
  northbound_holding_change_1d, northbound_holding_change_5d,
  northbound_estimated_increase_shares, northbound_estimated_increase_value, northbound_estimated_increase_value_pct,
  northbound_net_flow_proxy_1d, northbound_net_flow_proxy_5d,
  northbound_board_name,
  attention_rank, attention_level, attention_change_3d, attention_change_5d,
  attention_latest_price, attention_price_change_amount, attention_price_change_pct,
  attention_new_fans_ratio, attention_loyal_fans_ratio,
  policy_event_tag, announcement_event_tag, announcement_count_1d, notice_attach_type,
  earnings_event_tag, earnings_event_direction, earnings_event_strength_score,
  earnings_change_pct_lower, earnings_change_pct_upper,
  theme_tags, theme_breadth_score
)
SELECT
  keys.stock_code,
  keys.trade_date,
  COALESCE(theme.industry_name, board.board_name),
  COALESCE(theme.sector_name, board.board_name),
  nb.hold_shares,
  nb.hold_value,
  nb.hold_float_ratio,
  nb.hold_total_ratio,
  nb.holding_change_1d,
  nb.holding_change_5d,
  nb.estimated_increase_shares,
  nb.estimated_increase_value,
  nb.estimated_increase_value_pct,
  nb.net_flow_proxy_1d,
  nb.net_flow_proxy_5d,
  nb.board_name,
  att.attention_rank,
  att.attention_level,
  att.attention_change_3d,
  att.attention_change_5d,
  att.latest_price,
  att.price_change_amount,
  att.price_change_pct,
  att.new_fans_ratio,
  att.loyal_fans_ratio,
  notice.policy_event_tag,
  notice.announcement_event_tag,
  notice.announcement_count_1d,
  notice.notice_attach_type,
  notice.earnings_event_tag,
  notice.earnings_event_direction,
  notice.earnings_event_strength_score,
  notice.earnings_change_pct_lower,
  notice.earnings_change_pct_upper,
  COALESCE(theme.theme_tags, CASE
    WHEN board.board_name IS NULL THEN '{{}}'::text[]
    ELSE ARRAY[board.board_name]::text[]
  END),
  COALESCE(theme_breadth.theme_breadth_score, breadth.theme_breadth_score)
FROM keys
LEFT JOIN enriched_northbound AS nb
  ON nb.stock_code = keys.stock_code
 AND nb.trade_date = keys.trade_date
LEFT JOIN enriched_attention AS att
  ON att.stock_code = keys.stock_code
 AND att.trade_date = keys.trade_date
LEFT JOIN notice_daily AS notice
  ON notice.stock_code = keys.stock_code
 AND notice.trade_date = keys.trade_date
LEFT JOIN static_board AS board
  ON board.stock_code = keys.stock_code
LEFT JOIN board_breadth AS breadth
  ON breadth.trade_date = keys.trade_date
 AND breadth.board_name = board.board_name
LEFT JOIN theme_agg AS theme
  ON theme.stock_code = keys.stock_code
LEFT JOIN theme_breadth
  ON theme_breadth.stock_code = keys.stock_code
ON CONFLICT (stock_code, trade_date) DO UPDATE SET
  industry_name = EXCLUDED.industry_name,
  sector_name = EXCLUDED.sector_name,
  northbound_hold_shares = EXCLUDED.northbound_hold_shares,
  northbound_hold_value = EXCLUDED.northbound_hold_value,
  northbound_hold_float_ratio = EXCLUDED.northbound_hold_float_ratio,
  northbound_hold_total_ratio = EXCLUDED.northbound_hold_total_ratio,
  northbound_holding_change_1d = EXCLUDED.northbound_holding_change_1d,
  northbound_holding_change_5d = EXCLUDED.northbound_holding_change_5d,
  northbound_estimated_increase_shares = EXCLUDED.northbound_estimated_increase_shares,
  northbound_estimated_increase_value = EXCLUDED.northbound_estimated_increase_value,
  northbound_estimated_increase_value_pct = EXCLUDED.northbound_estimated_increase_value_pct,
  northbound_net_flow_proxy_1d = EXCLUDED.northbound_net_flow_proxy_1d,
  northbound_net_flow_proxy_5d = EXCLUDED.northbound_net_flow_proxy_5d,
  northbound_board_name = EXCLUDED.northbound_board_name,
  attention_rank = EXCLUDED.attention_rank,
  attention_level = EXCLUDED.attention_level,
  attention_change_3d = EXCLUDED.attention_change_3d,
  attention_change_5d = EXCLUDED.attention_change_5d,
  attention_latest_price = EXCLUDED.attention_latest_price,
  attention_price_change_amount = EXCLUDED.attention_price_change_amount,
  attention_price_change_pct = EXCLUDED.attention_price_change_pct,
  attention_new_fans_ratio = EXCLUDED.attention_new_fans_ratio,
  attention_loyal_fans_ratio = EXCLUDED.attention_loyal_fans_ratio,
  policy_event_tag = EXCLUDED.policy_event_tag,
  announcement_event_tag = EXCLUDED.announcement_event_tag,
  announcement_count_1d = EXCLUDED.announcement_count_1d,
  notice_attach_type = EXCLUDED.notice_attach_type,
  earnings_event_tag = EXCLUDED.earnings_event_tag,
  earnings_event_direction = EXCLUDED.earnings_event_direction,
  earnings_event_strength_score = EXCLUDED.earnings_event_strength_score,
  earnings_change_pct_lower = EXCLUDED.earnings_change_pct_lower,
  earnings_change_pct_upper = EXCLUDED.earnings_change_pct_upper,
  theme_tags = EXCLUDED.theme_tags,
  theme_breadth_score = EXCLUDED.theme_breadth_score,
  updated_at = NOW();
"""
    )
    count_sql = "SELECT COUNT(*) FROM research_market_context_daily"
    if conditions:
        count_sql += " WHERE " + " AND ".join(conditions)
    return int(db.run_sql(count_sql).strip() or "0")


def _normalize_stock_code(value: object) -> str | None:
    text = _to_text(value)
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) != 6:
        return None
    return digits


def _normalize_trade_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    return text[:10]


def _normalize_stock_name(value: object) -> str | None:
    text = _to_text(value)
    if not text:
        return None
    return "".join(ch for ch in text if not ch.isspace())


def _resolve_attention_history_dates(db: PostgresCli, start_date: str | None) -> list[str]:
    if not start_date:
        return []
    sql = f"""
SELECT DISTINCT trade_date
FROM normalized_market_daily
WHERE trade_date >= '{start_date}'::date
  AND trade_date <= CURRENT_DATE
ORDER BY trade_date
"""
    rows = db.run_sql(sql).splitlines()
    return [row.strip() for row in rows if row.strip()]


def _resolve_notice_history_dates(db: PostgresCli, start_date: str | None) -> list[str]:
    if start_date:
        return _resolve_attention_history_dates(db, start_date)
    latest = db.run_sql("SELECT COALESCE(MAX(trade_date)::text, '') FROM raw_notice_event_daily;").strip()
    fallback_start = latest or "2025-01-01"
    sql = f"""
SELECT DISTINCT trade_date
FROM normalized_market_daily
WHERE trade_date >= '{fallback_start}'::date
  AND trade_date <= CURRENT_DATE
ORDER BY trade_date
"""
    rows = db.run_sql(sql).splitlines()
    if latest and rows:
        return [row.strip() for row in rows if row.strip() and row.strip() > latest]
    return [row.strip() for row in rows if row.strip()]


def _resolve_theme_stock_codes(
    db: PostgresCli,
    stock_codes: Iterable[str] | None,
    context_start_date: str | None,
) -> list[str]:
    if stock_codes:
        return sorted({code for code in stock_codes if code and len(code) == 6})
    where = "WHERE stock_code ~ '^[0-9]{6}$'"
    if context_start_date:
        where += f" AND trade_date >= '{context_start_date}'::date"
    rows = db.run_sql(
        f"""
SELECT DISTINCT stock_code
FROM normalized_market_daily
{where}
ORDER BY stock_code
"""
    ).splitlines()
    return [row.strip() for row in rows if row.strip()]


def _fetch_cninfo_industry_profile_rows(
    stock_codes: list[str],
    max_stocks: int | None = None,
) -> list[dict[str, object]]:
    target_codes = stock_codes[:max_stocks] if max_stocks else stock_codes
    if not target_codes:
        return []
    session = requests.Session()
    session.trust_env = False
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_fetch_single_cninfo_profile, session, stock_code): stock_code
            for stock_code in target_codes
        }
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception:
                continue
            if row:
                rows.append(row)
    return rows


def _fetch_single_cninfo_profile(
    session: requests.Session,
    stock_code: str,
) -> dict[str, object] | None:
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1133"
    headers = _cninfo_headers()
    response = session.post(url, params={"scode": stock_code}, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("records") or []
    if not records:
        return None
    record = records[0]
    industry_name = _to_text(record.get("F032V"))
    if not industry_name:
        return None
    return {
        "stock_code": stock_code,
        "industry_name": industry_name,
        "industry_code": None,
        "raw_payload": {str(k): _jsonable(v) for k, v in record.items()},
    }


def _cninfo_headers() -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Host": "webapi.cninfo.com.cn",
        "Accept-Enckey": _build_cninfo_enckey(),
        "Origin": "https://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    }


def _build_cninfo_enckey() -> str:
    plain = str(int(time.time())).encode("utf-8")
    cipher = AES.new(b"1234567887654321", AES.MODE_CBC, b"1234567887654321")
    encrypted = cipher.encrypt(pad(plain, 16))
    return base64.b64encode(encrypted).decode("utf-8")


def _load_stock_name_code_map() -> dict[str, str]:
    import akshare as ak  # type: ignore

    with _without_proxy_env():
        frame = ak.stock_info_a_code_name()
    mapping: dict[str, str] = {}
    for _, row in frame.iterrows():
        stock_code = _normalize_stock_code(row.get("code"))
        stock_name = _normalize_stock_name(row.get("name"))
        if stock_code and stock_name:
            mapping[stock_name] = stock_code
    return mapping


def _resolve_code_from_name_cell(value: object, name_to_code: dict[str, str]) -> str | None:
    text = _to_text(value)
    if not text:
        return None
    code = _normalize_stock_code(text)
    if code:
        return code
    return name_to_code.get(_normalize_stock_name(text) or "")


def _normalize_notice_event_tag(report_scope: str, notice_type: str | None) -> str:
    parts = [report_scope]
    if notice_type:
        parts.append(notice_type)
    return "::".join(parts)


def _classify_notice_policy_tag(
    title: str,
    notice_type: str | None,
    report_scope: str,
) -> str | None:
    haystack = f"{report_scope} {notice_type or ''} {title}"
    keyword_map = [
        ("risk_warning", ["风险", "异常波动", "退市", "诉讼", "问询", "处罚"]),
        ("capital_support", ["回购", "增持", "员工持股"]),
        ("share_reduction", ["减持", "减持计划"]),
        ("mna_restructure", ["重组", "并购", "收购", "资产置换"]),
        ("business_contract", ["签订", "合同", "订单", "中标", "框架协议"]),
    ]
    for tag, keywords in keyword_map:
        if any(keyword in haystack for keyword in keywords):
            return tag
    if report_scope == "重大事项":
        return "major_notice"
    if report_scope == "持股变动":
        return "shareholding_change"
    return None


def _is_notice_earnings_candidate(
    title: str,
    notice_type: str | None,
    report_scope: str,
) -> bool:
    haystack = f"{report_scope} {notice_type or ''} {title}"
    return any(
        keyword in haystack
        for keyword in [
            "业绩预告",
            "业绩快报",
            "年报",
            "年度报告",
            "季报",
            "季度报告",
            "中报",
            "半年报",
            "半年度报告",
            "一季报",
            "三季报",
            "净利润",
            "归母净利润",
            "扣非净利润",
            "预盈",
            "预亏",
            "预增",
            "预减",
            "扭亏",
            "首亏",
            "续亏",
            "续盈",
            "减亏",
            "略增",
            "略减",
            "增亏",
        ]
    )


def _extract_notice_info_code(notice_url: str | None) -> str | None:
    if not notice_url:
        return None
    matched = re.search(r"(AN\d{12,})", notice_url)
    if matched:
        return matched.group(1)
    return None


def _fetch_notice_detail_payload(info_code: str) -> dict[str, object] | None:
    try:
        response = requests.get(
            "https://np-cnotice-stock-test.eastmoney.com/api/content/ann",
            params={
                "cb": "cb",
                "art_code": info_code,
                "client_source": "web",
                "page_index": "1",
            },
            timeout=20,
        )
        response.raise_for_status()
    except Exception:
        return None
    match = re.match(r"^[^(]+\((.*)\)\s*$", response.text, re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    return data


def _download_pdf_text(attach_url: str | None) -> str | None:
    if not attach_url or PdfReader is None:
        return None
    try:
        response = requests.get(attach_url, timeout=30)
        response.raise_for_status()
        reader = PdfReader(io.BytesIO(response.content))
    except Exception:
        return None
    pages: list[str] = []
    for page in reader.pages[:8]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            pages.append(text)
    if not pages:
        return None
    merged = "\n".join(pages)
    merged = re.sub(r"\s+", " ", merged)
    return merged[:20000]


def _extract_earnings_change_range(text: str) -> tuple[float | None, float | None]:
    compact = text.replace("％", "%").replace("—", "-").replace("–", "-").replace("至", "-")

    patterns = [
        r"(?:同比|较上年同期|比上年同期)(?:增长|上升|增加|变动|下降|减少|下滑)?[^%]{0,20}?(-?\d+(?:\.\d+)?)%\s*-\s*(-?\d+(?:\.\d+)?)%",
        r"(?:预计|预告|净利润|归母净利润|扣非净利润)[^%]{0,40}?(-?\d+(?:\.\d+)?)%\s*-\s*(-?\d+(?:\.\d+)?)%",
    ]
    for pattern in patterns:
        matched = re.search(pattern, compact, re.I)
        if matched:
            values = [float(matched.group(1)), float(matched.group(2))]
            return min(values), max(values)

    single_patterns = [
        r"(?:同比|较上年同期|比上年同期)(?:增长|上升|增加|下降|减少|下滑)[^%]{0,20}?(-?\d+(?:\.\d+)?)%",
        r"(?:预增|预减|预盈|预亏|扭亏|减亏|增亏|续盈|续亏|略增|略减)[^%]{0,20}?(-?\d+(?:\.\d+)?)%",
    ]
    for pattern in single_patterns:
        matched = re.search(pattern, compact, re.I)
        if matched:
            value = float(matched.group(1))
            return value, value

    return None, None


def _classify_notice_earnings_tag(
    title: str,
    notice_type: str | None,
    report_scope: str,
) -> tuple[str | None, str | None, float | None]:
    haystack = f"{report_scope} {notice_type or ''} {title}"

    exclusion_keywords = [
        "月度经营情况",
        "生产经营快报",
        "生产经营数据",
        "产销快报",
        "产销数据",
        "经营数据",
        "经营指标",
        "自愿性信息披露",
        "业绩承诺",
        "业绩补偿",
        "审计进展",
        "风险提示",
        "退市风险",
        "终止上市",
        "关注公告",
        "仲裁",
        "诉讼",
    ]
    if any(keyword in haystack for keyword in exclusion_keywords):
        return None, None, None

    explicit_event_keywords = [
        "业绩预告",
        "业绩快报",
        "年报",
        "年度报告",
        "季报",
        "季度报告",
        "中报",
        "半年报",
        "半年度报告",
        "一季报",
        "三季报",
        "净利润",
        "归母净利润",
        "扣非净利润",
        "预盈",
        "预亏",
        "预增",
        "预减",
        "扭亏",
        "首亏",
        "续亏",
        "续盈",
        "减亏",
        "略增",
        "略减",
        "增亏",
    ]
    if not any(keyword in haystack for keyword in explicit_event_keywords):
        return None, None, None

    if any(keyword in haystack for keyword in ["业绩快报", "快报"]):
        event_tag = "earnings_preliminary"
    elif any(
        keyword in haystack
        for keyword in ["业绩预告", "预告", "预盈", "预亏", "预增", "预减", "扭亏", "首亏", "续亏", "续盈", "减亏", "略增", "略减", "增亏"]
    ):
        event_tag = "earnings_guidance"
    elif any(
        keyword in haystack
        for keyword in ["年报", "年度报告", "季报", "季度报告", "中报", "一季报", "半年报", "半年度报告", "三季报"]
    ):
        event_tag = "financial_report"
    else:
        event_tag = "earnings_related"

    negative_keywords = [
        "预亏",
        "预减",
        "首亏",
        "续亏",
        "增亏",
        "亏损",
        "下滑",
        "下降",
        "下跌",
        "减少",
        "承压",
        "由盈转亏",
    ]
    positive_keywords = [
        "预盈",
        "预增",
        "略增",
        "续盈",
        "减亏",
        "扭亏",
        "大增",
        "增长",
        "上升",
        "向好",
        "改善",
        "同比上升",
        "同比增长",
        "同比扭亏",
        "实现盈利",
        "扭亏为盈",
    ]
    neutral_keywords = ["不确定", "修正", "更正", "补充", "说明", "调整", "关注"]

    direction: str | None
    strength: float | None

    if any(keyword in haystack for keyword in neutral_keywords):
        direction = "mixed"
        strength = 0.0
    elif any(keyword in haystack for keyword in negative_keywords):
        direction = "negative"
        strength = -1.0
    elif any(keyword in haystack for keyword in positive_keywords):
        direction = "positive"
        strength = 1.0
    else:
        direction = "unknown"
        strength = 0.0

    if direction == "positive":
        if any(keyword in haystack for keyword in ["大增", "扭亏", "扭亏为盈", "同比增长", "同比上升", "同比扭亏"]):
            strength = 2.0
    elif direction == "negative":
        if any(keyword in haystack for keyword in ["首亏", "由盈转亏", "续亏", "增亏"]):
            strength = -2.0

    return event_tag, direction, strength


def _classify_notice_earnings_details(
    title: str,
    notice_type: str | None,
    report_scope: str,
    notice_content: str | None,
    notice_attach_type: str | None,
) -> tuple[str | None, str | None, float | None, float | None, float | None]:
    event_tag, direction, strength = _classify_notice_earnings_tag(title, notice_type, report_scope)
    content_haystack = f"{title} {notice_content or ''}"
    lower, upper = _extract_earnings_change_range(content_haystack)

    if event_tag is None and notice_content:
        event_tag, direction, strength = _classify_notice_earnings_tag(
            content_haystack,
            notice_type,
            report_scope,
        )

    if lower is not None or upper is not None:
        midpoint_values = [value for value in [lower, upper] if value is not None]
        midpoint = sum(midpoint_values) / len(midpoint_values)
        if midpoint >= 0:
            direction = "positive"
            strength = 2.0 if midpoint >= 30 else 1.0
        else:
            direction = "negative"
            strength = -2.0 if midpoint <= -30 else -1.0

    if notice_attach_type == "0" and event_tag in {"earnings_preliminary", "earnings_guidance", "financial_report"}:
        strength = strength if strength is not None else 0.0

    return event_tag, direction, strength, lower, upper


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_pct_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).replace("%", "").replace(",", "").strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text) / 100.0
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else None


def _to_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _jsonable(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _em_symbol(stock_code: str) -> str:
    return ("SH" if stock_code.startswith("6") else "SZ") + stock_code


def _hash_payload(payload: dict[str, object], *parts: str) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
    digest.update(blob.encode("utf-8"))
    return digest.hexdigest()


def _sql_text(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def _sql_json(value: dict[str, object]) -> str:
    return _sql_text(json.dumps(value, ensure_ascii=False)).replace("NULL", "'{}'") + "::jsonb"


def _sql_num(value: float | None) -> str:
    return "NULL" if value is None else str(value)


def _sql_int(value: int | None) -> str:
    return "NULL" if value is None else str(value)


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _call_with_timeout(func, *args, timeout_seconds: int = 15, **kwargs):
    previous = signal.getsignal(signal.SIGALRM)

    def _raise_timeout(signum, frame):  # noqa: ARG001
        raise TimeoutError(f"{getattr(func, '__name__', 'call')} timed out after {timeout_seconds}s")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(timeout_seconds)
    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
