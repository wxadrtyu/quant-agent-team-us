from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .db import PostgresCli
from .io_utils import ensure_parent, write_json


RAW_MARKET_FIELDS = {
    "stock_code",
    "trade_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "turnover",
}

BASE_PLANNED_FIELDS = {
    "close_price_adj",
    "adj_factor",
    "is_suspended",
    "is_st",
    "limit_up_price",
    "limit_down_price",
}

FEATURE_FIELDS = {
    "ma_5",
    "ma_10",
    "ma_20",
    "ma_60",
    "avg_volume_20d",
    "avg_turnover_20d",
    "volume_ratio_20d",
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "momentum_20d",
    "volatility_20d",
}

TRADING_CONSTRAINT_FIELD_ALIASES = {
    "trade_date": ["trade_date", "交易日期"],
    "adj_factor": ["adj_factor", "复权因子", "adjust_factor"],
    "is_suspended": ["is_suspended", "停牌", "是否停牌"],
    "is_st": ["is_st", "st", "是否st", "是否ST"],
    "limit_up_price": ["limit_up_price", "涨停价"],
    "limit_down_price": ["limit_down_price", "跌停价"],
    "stock_code": ["stock_code", "股票代码"],
}


@dataclass
class BaseIngestModulePlan:
    module: str
    description: str
    fixed_schedule: str


@dataclass
class BaseIncrementalIngestPlan:
    generated_at: str
    modules: List[BaseIngestModulePlan] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class InventoryItem:
    name: str
    status: str
    source: str
    notes: str = ""


@dataclass
class DataInventory:
    generated_at: str
    available_items: List[InventoryItem] = field(default_factory=list)
    planned_items: List[InventoryItem] = field(default_factory=list)
    missing_items: List[InventoryItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    def available_names(self) -> List[str]:
        return [item.name for item in self.available_items if item.status == "available"]


@dataclass
class StockHistorySnapshot:
    source_path: str
    file_count: int
    sample_size: int
    earliest_trade_date: Optional[str] = None
    latest_trade_date: Optional[str] = None
    sample_symbols: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class BaseIncrementalIngestSummary:
    generated_at: str
    status: str
    source_snapshot: Optional[StockHistorySnapshot]
    inventory: DataInventory
    modules: List[BaseIngestModulePlan] = field(default_factory=list)
    execution: Dict[str, object] | None = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "status": self.status,
            "source_snapshot": self.source_snapshot.to_dict() if self.source_snapshot else None,
            "inventory": self.inventory.to_dict(),
            "modules": [asdict(module) for module in self.modules],
            "execution": dict(self.execution) if self.execution is not None else None,
            "notes": list(self.notes),
        }


@dataclass
class BootstrapIngestResult:
    generated_at: str
    status: str
    database: str
    source_path: str
    files_processed: int
    rows_prepared: int
    inserted_rows: int
    conflict_rows: int
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class IncrementalFileState:
    source_path: str
    stock_code: str
    file_hash: str
    file_size_bytes: int
    file_mtime_ns: int
    row_count: int
    latest_trade_date: Optional[str]
    latest_trade_row_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class TradingConstraintsIngestResult:
    source_path: Optional[str]
    status: str
    files_scanned: int
    files_changed: int
    rows_prepared: int
    inserted_rows: int
    changed_stock_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class NormalizedSyncRepairResult:
    generated_at: str
    status: str
    repair_mode: str
    stock_codes_requested: List[str] = field(default_factory=list)
    stock_codes_repaired: List[str] = field(default_factory=list)
    stock_code_count: int = 0
    batch_size: int = 0
    batch_count: int = 0
    mismatch_rows_before: int = 0
    mismatch_rows_after: int = 0
    normalized_rows_synced: int = 0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_base_incremental_ingest_plan() -> BaseIncrementalIngestPlan:
    generated_at = datetime.now().isoformat(timespec="seconds")
    return BaseIncrementalIngestPlan(
        generated_at=generated_at,
        modules=[
            BaseIngestModulePlan(
                module="market_daily",
                description="Update daily OHLCV market data required by all strategies.",
                fixed_schedule="daily_after_close",
            ),
            BaseIngestModulePlan(
                module="trading_constraints",
                description="Update tradability constraints such as adjustment factors, suspension, ST, and limit data.",
                fixed_schedule="daily_after_close",
            ),
        ],
        notes=[
            "Base ingestion is fixed and token-free.",
            "Fundamental, label, and event sync should be strategy-driven via strategy_data_sync.",
        ],
    )


def inspect_stock_history(source_dir: Path, sample_size: int = 50) -> Optional[StockHistorySnapshot]:
    if not source_dir.exists():
        return None

    files = sorted(path for path in source_dir.glob("*.csv") if path.is_file())
    if not files:
        return None

    earliest: Optional[str] = None
    latest: Optional[str] = None
    sample_symbols: List[str] = []
    inspected = 0

    for path in files[:sample_size]:
        inspected += 1
        symbol = path.stem
        sample_symbols.append(symbol)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            first_row = next(reader, None)
            if not first_row:
                continue
            first_date = first_row.get("交易日期")
            last_date = first_date
            for row in reader:
                last_date = row.get("交易日期") or last_date

        candidates = [date for date in [first_date, last_date] if date]
        if not candidates:
            continue
        local_min = min(candidates)
        local_max = max(candidates)
        earliest = local_min if earliest is None else min(earliest, local_min)
        latest = local_max if latest is None else max(latest, local_max)

    return StockHistorySnapshot(
        source_path=str(source_dir),
        file_count=len(files),
        sample_size=inspected,
        earliest_trade_date=earliest,
        latest_trade_date=latest,
        sample_symbols=sample_symbols[:10],
    )


def build_data_inventory(
    source_snapshot: Optional[StockHistorySnapshot],
    normalized_available_fields: Iterable[str] | None = None,
    feature_available_fields: Iterable[str] | None = None,
) -> DataInventory:
    generated_at = datetime.now().isoformat(timespec="seconds")
    available_items: List[InventoryItem] = []
    planned_items: List[InventoryItem] = []
    normalized_available = set(normalized_available_fields or [])
    feature_available = set(feature_available_fields or [])

    if source_snapshot is not None:
        available_items.extend(
            InventoryItem(
                name=name,
                status="available",
                source="stock_history_seed",
                notes="Available from local historical seed data.",
            )
            for name in sorted(RAW_MARKET_FIELDS)
        )
        available_items.extend(
            InventoryItem(
                name=name,
                status="available",
                source="normalized_market_daily",
                notes="Available from normalized market data generated by base incremental ingest.",
            )
            for name in sorted(normalized_available)
        )
        available_items.extend(
            InventoryItem(
                name=name,
                status="available",
                source="research_feature_daily",
                notes="Available from persisted derived features generated by feature refresh.",
            )
            for name in sorted(feature_available)
        )
        planned_items.extend(
            InventoryItem(
                name=name,
                status="planned",
                source="base_incremental_ingest",
                notes="Expected to be produced by daily base ingestion or standardization.",
            )
            for name in sorted(BASE_PLANNED_FIELDS - normalized_available)
        )
        planned_items.extend(
            InventoryItem(
                name=name,
                status="planned",
                source="feature_refresh",
                notes="Expected to be produced by derived feature refresh.",
            )
            for name in sorted(FEATURE_FIELDS - feature_available)
        )

    return DataInventory(
        generated_at=generated_at,
        available_items=available_items,
        planned_items=planned_items,
        missing_items=[],
    )


def build_base_incremental_ingest_summary(
    source_dir: Path,
    sample_size: int = 50,
) -> BaseIncrementalIngestSummary:
    plan = build_base_incremental_ingest_plan()
    snapshot = inspect_stock_history(source_dir, sample_size=sample_size)
    inventory = build_data_inventory(snapshot)
    status = "ready" if snapshot is not None else "missing_seed_source"
    notes = list(plan.notes)
    if snapshot is None:
        notes.append("Local stock_history seed source was not found.")
    else:
        notes.append("Inventory contains currently available seed fields and planned base fields.")

    return BaseIncrementalIngestSummary(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        source_snapshot=snapshot,
        inventory=inventory,
        modules=plan.modules,
        notes=notes,
    )


def write_base_incremental_outputs(
    project_root: Path,
    source_dir: Path,
    sample_size: int = 50,
    constraints_dir: Path | None = None,
    stock_codes: Iterable[str] | None = None,
    db: PostgresCli | None = None,
) -> Dict[str, Path]:
    summary = run_base_incremental_ingest(
        source_dir=source_dir,
        sample_size=sample_size,
        constraints_dir=constraints_dir,
        stock_codes=stock_codes,
        db=db,
    )
    summary_path = project_root / "reports" / "ingestion" / "base_incremental_summary.json"
    inventory_path = project_root / "configs" / "data_inventory.json"
    write_json(summary_path, summary.to_dict())
    write_json(inventory_path, summary.inventory.to_dict())
    return {"summary": summary_path, "inventory": inventory_path}


def load_available_inventory_items(path: Path) -> List[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    available_items = payload.get("available_items", [])
    return [
        item["name"]
        for item in available_items
        if item.get("status") == "available" and item.get("name")
    ]


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _material_change_predicate(existing_alias: str, staging_alias: str) -> str:
    return f"""
(
  {existing_alias}.raw_line_hash <> {staging_alias}.raw_line_hash
  AND NOT (
    COALESCE({existing_alias}.open_price, 0) = COALESCE({staging_alias}.open_price, 0)
    AND COALESCE({existing_alias}.high_price, 0) = COALESCE({staging_alias}.high_price, 0)
    AND COALESCE({existing_alias}.low_price, 0) = COALESCE({staging_alias}.low_price, 0)
    AND COALESCE({existing_alias}.close_price, 0) = COALESCE({staging_alias}.close_price, 0)
    AND ABS(COALESCE({existing_alias}.turnover, 0) - COALESCE({staging_alias}.turnover, 0)) <= 0.01
    AND ABS(COALESCE({existing_alias}.volume, 0) - COALESCE({staging_alias}.volume, 0)) <= 100
  )
)
""".strip()


def load_ingest_source_file_state(db: PostgresCli) -> Dict[str, IncrementalFileState]:
    rows = db.run_sql(
        """
SELECT source_path, stock_code, file_hash, file_size_bytes, file_mtime_ns, row_count, latest_trade_date, latest_trade_row_hash
FROM ingest_source_file_state;
"""
    ).splitlines()
    state: Dict[str, IncrementalFileState] = {}
    for row in rows:
        if not row:
            continue
        (
            source_path,
            stock_code,
            file_hash,
            file_size_bytes,
            file_mtime_ns,
            row_count,
            latest_trade_date,
            latest_trade_row_hash,
        ) = row.split("|", 7)
        state[source_path] = IncrementalFileState(
            source_path=source_path,
            stock_code=stock_code,
            file_hash=file_hash,
            file_size_bytes=int(file_size_bytes),
            file_mtime_ns=int(file_mtime_ns or "0"),
            row_count=int(row_count or "0"),
            latest_trade_date=latest_trade_date or None,
            latest_trade_row_hash=latest_trade_row_hash or None,
        )
    return state


def build_incremental_bundle(
    source_dir: Path,
    output_csv: Path,
    known_file_states: Dict[str, IncrementalFileState],
    stock_codes: Iterable[str] | None = None,
) -> Dict[str, object]:
    selected_codes = {code for code in (stock_codes or []) if code}
    files = sorted(
        path
        for path in source_dir.glob("*.csv")
        if path.is_file() and (not selected_codes or path.stem in selected_codes)
    )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    files_changed = 0
    file_states: List[IncrementalFileState] = []

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stock_code",
                "trade_date",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "turnover",
                "raw_line_hash",
                "raw_payload",
            ],
        )
        writer.writeheader()

        for path in files:
            source_path = str(path.resolve())
            stock_code = path.stem
            stat = path.stat()
            known_state = known_file_states.get(source_path)
            metadata_matches = bool(
                known_state
                and known_state.file_size_bytes == stat.st_size
                and known_state.file_mtime_ns == stat.st_mtime_ns
            )

            latest_trade_date: Optional[str] = (
                known_state.latest_trade_date if metadata_matches and known_state else None
            )
            local_row_count = known_state.row_count if metadata_matches and known_state else 0
            file_hash = known_state.file_hash if metadata_matches and known_state else ""
            latest_trade_row_hash = (
                known_state.latest_trade_row_hash if metadata_matches and known_state else None
            )
            changed = not metadata_matches

            if changed:
                file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                changed = known_state is None or known_state.file_hash != file_hash
            if changed:
                files_changed += 1

            if changed:
                latest_trade_date = None
                local_row_count = 0
                latest_trade_row_hash = None

                # Fast path for append-only updates: walk from the file head until we hit the
                # previously ingested latest row hash, then only stage the new prefix rows.
                if known_state and known_state.latest_trade_row_hash:
                    append_rows: List[Dict[str, object]] = []
                    with path.open("r", encoding="utf-8-sig", newline="") as source:
                        reader = csv.DictReader(source)
                        for index, row in enumerate(reader):
                            normalized = _normalize_stock_history_row(row, stock_code)
                            trade_date = str(normalized["trade_date"])
                            if latest_trade_date is None or trade_date > latest_trade_date:
                                latest_trade_date = trade_date
                                latest_trade_row_hash = str(normalized["raw_line_hash"])
                            if normalized["raw_line_hash"] == known_state.latest_trade_row_hash:
                                if index > 0:
                                    for staged in append_rows:
                                        writer.writerow(staged)
                                        row_count += 1
                                    local_row_count = known_state.row_count + len(append_rows)
                                    break
                                # File hash changed but the previous latest row is still at the
                                # head of the file. Treat this as a potential historical rewrite
                                # and fall back to the full-file path so conflict detection stays
                                # intact.
                                append_rows = []
                                latest_trade_date = None
                                latest_trade_row_hash = None
                                local_row_count = 0
                                break
                            append_rows.append(normalized)
                        else:
                            append_rows = []

                    if local_row_count == 0:
                        latest_trade_date = None
                        latest_trade_row_hash = None

                if local_row_count == 0:
                    with path.open("r", encoding="utf-8-sig", newline="") as source:
                        reader = csv.DictReader(source)
                        for row in reader:
                            normalized = _normalize_stock_history_row(row, stock_code)
                            local_row_count += 1
                            trade_date = str(normalized["trade_date"])
                            if latest_trade_date is None or trade_date > latest_trade_date:
                                latest_trade_date = trade_date
                                latest_trade_row_hash = str(normalized["raw_line_hash"])
                            writer.writerow(normalized)
                            row_count += 1

            file_states.append(
                IncrementalFileState(
                    source_path=source_path,
                    stock_code=stock_code,
                    file_hash=file_hash,
                    file_size_bytes=stat.st_size,
                    file_mtime_ns=stat.st_mtime_ns,
                    row_count=local_row_count,
                    latest_trade_date=latest_trade_date,
                    latest_trade_row_hash=latest_trade_row_hash,
                )
            )

    return {
        "files_scanned": len(files),
        "files_changed": files_changed,
        "rows_prepared": row_count,
        "file_states": file_states,
    }


def _resolve_constraint_column(fieldnames: Iterable[str] | None, canonical_name: str) -> Optional[str]:
    if not fieldnames:
        return None
    normalized = {name.strip().lower(): name for name in fieldnames if name}
    for alias in TRADING_CONSTRAINT_FIELD_ALIASES[canonical_name]:
        matched = normalized.get(alias.lower())
        if matched:
            return matched
    return None


def _parse_optional_bool(value: str | None) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"", "null", "none"}:
        return None
    if normalized in {"1", "true", "t", "yes", "y", "是"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "否"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def _parse_optional_float(value: str | None) -> Optional[float]:
    if value is None:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return float(normalized)


def _normalize_trading_constraints_row(
    row: Dict[str, str],
    stock_code: str,
    trade_date_col: str,
    adj_factor_col: Optional[str],
    is_suspended_col: Optional[str],
    is_st_col: Optional[str],
    limit_up_price_col: Optional[str],
    limit_down_price_col: Optional[str],
) -> Dict[str, object]:
    payload = {
        "stock_code": stock_code,
        "trade_date": row[trade_date_col],
        "adj_factor": _parse_optional_float(row.get(adj_factor_col)) if adj_factor_col else None,
        "is_suspended": _parse_optional_bool(row.get(is_suspended_col)) if is_suspended_col else None,
        "is_st": _parse_optional_bool(row.get(is_st_col)) if is_st_col else None,
        "limit_up_price": _parse_optional_float(row.get(limit_up_price_col)) if limit_up_price_col else None,
        "limit_down_price": _parse_optional_float(row.get(limit_down_price_col)) if limit_down_price_col else None,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return {
        **payload,
        "raw_line_hash": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "raw_payload": payload_json,
    }


def _normalize_stock_history_row(row: Dict[str, str], stock_code: str) -> Dict[str, object]:
    payload = {
        "stock_code": stock_code,
        "trade_date": row["交易日期"],
        "close_price": float(row["收盘价"]),
        "open_price": float(row["开盘价"]),
        "high_price": float(row["最高价"]),
        "low_price": float(row["最低价"]),
        "volume": float(row["成交量"]),
        "turnover": float(row["成交额"]),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return {
        **payload,
        "raw_line_hash": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "raw_payload": payload_json,
    }


def build_bootstrap_bundle(
    source_dir: Path,
    output_csv: Path,
    limit_files: Optional[int] = None,
) -> Dict[str, int]:
    files = sorted(path for path in source_dir.glob("*.csv") if path.is_file())
    if limit_files is not None:
        files = files[:limit_files]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stock_code",
                "trade_date",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "turnover",
                "raw_line_hash",
                "raw_payload",
            ],
        )
        writer.writeheader()
        for path in files:
            stock_code = path.stem
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                for row in reader:
                    writer.writerow(_normalize_stock_history_row(row, stock_code))
                    row_count += 1

    return {"files_processed": len(files), "rows_prepared": row_count}


def run_trading_constraints_ingest(
    db: PostgresCli,
    source_dir: Path | None,
    known_file_states: Dict[str, IncrementalFileState],
) -> TradingConstraintsIngestResult:
    if source_dir is None:
        return TradingConstraintsIngestResult(
            source_path=None,
            status="not_configured",
            files_scanned=0,
            files_changed=0,
            rows_prepared=0,
            inserted_rows=0,
        )
    if not source_dir.exists():
        return TradingConstraintsIngestResult(
            source_path=str(source_dir),
            status="missing_source",
            files_scanned=0,
            files_changed=0,
            rows_prepared=0,
            inserted_rows=0,
        )

    files = sorted(path for path in source_dir.glob("*.csv") if path.is_file())
    if not files:
        return TradingConstraintsIngestResult(
            source_path=str(source_dir),
            status="empty_source",
            files_scanned=0,
            files_changed=0,
            rows_prepared=0,
            inserted_rows=0,
        )

    inserted_rows = 0
    rows_prepared = 0
    files_changed = 0
    changed_stock_codes: set[str] = set()
    file_states: List[IncrementalFileState] = []

    for path in files:
        source_path = str(path.resolve())
        stock_code = path.stem
        stat = path.stat()
        known_state = known_file_states.get(source_path)
        metadata_matches = bool(
            known_state
            and known_state.file_size_bytes == stat.st_size
            and known_state.file_mtime_ns == stat.st_mtime_ns
        )
        local_row_count = known_state.row_count if metadata_matches and known_state else 0
        latest_trade_date: Optional[str] = known_state.latest_trade_date if metadata_matches and known_state else None
        file_hash = known_state.file_hash if metadata_matches and known_state else ""
        changed = not metadata_matches

        if changed:
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            changed = known_state is None or known_state.file_hash != file_hash

        if changed:
            files_changed += 1
            local_row_count = 0
            latest_trade_date = None
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                trade_date_col = _resolve_constraint_column(reader.fieldnames, "trade_date")
                stock_code_col = _resolve_constraint_column(reader.fieldnames, "stock_code")
                adj_factor_col = _resolve_constraint_column(reader.fieldnames, "adj_factor")
                is_suspended_col = _resolve_constraint_column(reader.fieldnames, "is_suspended")
                is_st_col = _resolve_constraint_column(reader.fieldnames, "is_st")
                limit_up_price_col = _resolve_constraint_column(reader.fieldnames, "limit_up_price")
                limit_down_price_col = _resolve_constraint_column(reader.fieldnames, "limit_down_price")

                if trade_date_col is None:
                    raise ValueError(f"Constraints file missing trade_date column: {path}")

                for row in reader:
                    row_stock_code = row.get(stock_code_col, "").strip() if stock_code_col else stock_code
                    if not row_stock_code:
                        row_stock_code = stock_code
                    local_row_count += 1
                    trade_date = row.get(trade_date_col)
                    if trade_date:
                        latest_trade_date = (
                            trade_date if latest_trade_date is None else max(latest_trade_date, trade_date)
                        )

                    normalized = _normalize_trading_constraints_row(
                        row,
                        row_stock_code,
                        trade_date_col,
                        adj_factor_col,
                        is_suspended_col,
                        is_st_col,
                        limit_up_price_col,
                        limit_down_price_col,
                    )
                    payload_json = _sql_literal(normalized["raw_payload"])
                    db.run_sql(
                        f"""
INSERT INTO raw_trading_constraints_daily (
  stock_code,
  trade_date,
  adj_factor,
  is_suspended,
  is_st,
  limit_up_price,
  limit_down_price,
  raw_line_hash,
  raw_payload
)
VALUES (
  '{_sql_literal(str(normalized["stock_code"]))}',
  '{_sql_literal(str(normalized["trade_date"]))}'::date,
  {normalized["adj_factor"] if normalized["adj_factor"] is not None else 'NULL'},
  {str(normalized["is_suspended"]).upper() if normalized["is_suspended"] is not None else 'NULL'},
  {str(normalized["is_st"]).upper() if normalized["is_st"] is not None else 'NULL'},
  {normalized["limit_up_price"] if normalized["limit_up_price"] is not None else 'NULL'},
  {normalized["limit_down_price"] if normalized["limit_down_price"] is not None else 'NULL'},
  '{normalized["raw_line_hash"]}',
  '{payload_json}'::jsonb
)
ON CONFLICT (stock_code, trade_date) DO UPDATE SET
  adj_factor = EXCLUDED.adj_factor,
  is_suspended = EXCLUDED.is_suspended,
  is_st = EXCLUDED.is_st,
  limit_up_price = EXCLUDED.limit_up_price,
  limit_down_price = EXCLUDED.limit_down_price,
  raw_line_hash = EXCLUDED.raw_line_hash,
  raw_payload = EXCLUDED.raw_payload,
  updated_at = NOW()
WHERE raw_trading_constraints_daily.raw_line_hash <> EXCLUDED.raw_line_hash
   OR raw_trading_constraints_daily.raw_line_hash = EXCLUDED.raw_line_hash;
"""
                    )
                    rows_prepared += 1
                    inserted_rows += 1
                    changed_stock_codes.add(row_stock_code)

        file_states.append(
            IncrementalFileState(
                source_path=source_path,
                stock_code=stock_code,
                file_hash=file_hash,
                file_size_bytes=stat.st_size,
                file_mtime_ns=stat.st_mtime_ns,
                row_count=local_row_count,
                latest_trade_date=latest_trade_date,
            )
        )

    _upsert_ingest_source_file_state(db, file_states)
    status = "success" if files_changed else "no_changes"
    return TradingConstraintsIngestResult(
        source_path=str(source_dir),
        status=status,
        files_scanned=len(files),
        files_changed=files_changed,
        rows_prepared=rows_prepared,
        inserted_rows=inserted_rows,
        changed_stock_codes=sorted(changed_stock_codes),
    )


def run_normalized_market_sync(
    db: PostgresCli,
    stock_codes: Iterable[str],
) -> int:
    selected = sorted({code for code in stock_codes if code})
    if not selected:
        return 0
    values = ", ".join(f"('{_sql_literal(code)}')" for code in selected)
    db.run_sql(
        f"""
CREATE TEMP TABLE staging_changed_stock_codes (
  stock_code TEXT PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO staging_changed_stock_codes (stock_code)
VALUES {values};

INSERT INTO normalized_market_daily (
  stock_code,
  trade_date,
  open_price,
  high_price,
  low_price,
  close_price,
  close_price_adj,
  volume,
  turnover,
  adj_factor,
  is_suspended,
  is_st,
  limit_up_price,
  limit_down_price,
  industry_name,
  sector_name,
  theme_tags,
  source_raw_line_hash
)
SELECT
  raw.stock_code,
  raw.trade_date,
  raw.open_price,
  raw.high_price,
  raw.low_price,
  raw.close_price,
  COALESCE(constraints.adj_factor, 1.0) * raw.close_price,
  raw.volume,
  raw.turnover,
  COALESCE(constraints.adj_factor, 1.0),
  constraints.is_suspended,
  constraints.is_st,
  constraints.limit_up_price,
  constraints.limit_down_price,
  NULL,
  NULL,
  '{{}}'::text[],
  raw.raw_line_hash
FROM raw_market_daily AS raw
JOIN staging_changed_stock_codes AS changed
  ON changed.stock_code = raw.stock_code
LEFT JOIN raw_trading_constraints_daily AS constraints
  ON constraints.stock_code = raw.stock_code
 AND constraints.trade_date = raw.trade_date
ON CONFLICT (stock_code, trade_date) DO UPDATE SET
  open_price = EXCLUDED.open_price,
  high_price = EXCLUDED.high_price,
  low_price = EXCLUDED.low_price,
  close_price = EXCLUDED.close_price,
  close_price_adj = EXCLUDED.close_price_adj,
  volume = EXCLUDED.volume,
  turnover = EXCLUDED.turnover,
  adj_factor = EXCLUDED.adj_factor,
  is_suspended = EXCLUDED.is_suspended,
  is_st = EXCLUDED.is_st,
  limit_up_price = EXCLUDED.limit_up_price,
  limit_down_price = EXCLUDED.limit_down_price,
  source_raw_line_hash = EXCLUDED.source_raw_line_hash,
  updated_at = NOW();
"""
    )
    stock_code_list = ", ".join(f"'{_sql_literal(code)}'" for code in selected)
    return int(
        db.run_sql(
            f"""
SELECT COUNT(*)
FROM normalized_market_daily
WHERE stock_code IN ({stock_code_list});
"""
        ).strip()
        or "0"
    )


def load_normalized_hash_mismatch_stock_codes(db: PostgresCli) -> List[str]:
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
SELECT DISTINCT normalized.stock_code
FROM normalized_market_daily AS normalized
JOIN latest_raw AS raw
  ON raw.stock_code = normalized.stock_code
 AND raw.trade_date = normalized.trade_date
WHERE normalized.source_raw_line_hash <> raw.raw_line_hash
ORDER BY normalized.stock_code;
"""
    ).splitlines()
    return [row for row in rows if row]


def load_all_raw_market_stock_codes(db: PostgresCli) -> List[str]:
    rows = db.run_sql(
        """
SELECT DISTINCT stock_code
FROM raw_market_daily
WHERE stock_code ~ '^[0-9]{6}$'
ORDER BY stock_code;
"""
    ).splitlines()
    return [row for row in rows if row]


def count_normalized_hash_mismatches(db: PostgresCli, stock_codes: Iterable[str] | None = None) -> int:
    selected = sorted({code for code in (stock_codes or []) if code})
    raw_where_clause = ""
    normalized_where_clause = ""
    if selected:
        stock_code_list = ", ".join(f"'{_sql_literal(code)}'" for code in selected)
        raw_where_clause = f"\n  WHERE stock_code IN ({stock_code_list})"
        normalized_where_clause = f"\n  AND normalized.stock_code IN ({stock_code_list})"
    return int(
        db.run_sql(
            f"""
WITH latest_raw AS (
  SELECT DISTINCT ON (stock_code, trade_date)
    stock_code,
    trade_date,
    raw_line_hash
  FROM raw_market_daily
  {raw_where_clause}
  ORDER BY stock_code, trade_date, updated_at DESC, id DESC
)
SELECT COUNT(*)
FROM normalized_market_daily AS normalized
JOIN latest_raw AS raw
  ON raw.stock_code = normalized.stock_code
 AND raw.trade_date = normalized.trade_date
WHERE normalized.source_raw_line_hash <> raw.raw_line_hash{normalized_where_clause};
"""
        ).strip()
        or "0"
    )


def repair_normalized_hash_mismatches(
    db: PostgresCli,
    stock_codes: Iterable[str] | None = None,
    batch_size: int = 250,
) -> NormalizedSyncRepairResult:
    requested = sorted({code for code in (stock_codes or []) if code})
    if requested:
        target_codes = requested
        mismatch_before = count_normalized_hash_mismatches(db, target_codes)
        synced_rows = run_normalized_market_sync(db, target_codes)
        mismatch_after = count_normalized_hash_mismatches(db, target_codes)
        status = "success" if target_codes and mismatch_after == 0 else "no_mismatches"
        if target_codes and mismatch_after > 0:
            status = "partial"
        return NormalizedSyncRepairResult(
            generated_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            repair_mode="targeted",
            stock_codes_requested=requested,
            stock_codes_repaired=target_codes,
            stock_code_count=len(target_codes),
            batch_size=len(target_codes),
            batch_count=1 if target_codes else 0,
            mismatch_rows_before=mismatch_before,
            mismatch_rows_after=mismatch_after,
            normalized_rows_synced=synced_rows,
        )

    target_codes = load_all_raw_market_stock_codes(db)
    total_synced_rows = 0
    total_batches = 0
    if not target_codes:
        status = "no_data"
    else:
        for index in range(0, len(target_codes), batch_size):
            batch = target_codes[index : index + batch_size]
            total_synced_rows += run_normalized_market_sync(db, batch)
            total_batches += 1
        status = "success"
    return NormalizedSyncRepairResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        repair_mode="full_batched_resync",
        stock_codes_requested=requested,
        stock_codes_repaired=[],
        stock_code_count=len(target_codes),
        batch_size=batch_size if target_codes else 0,
        batch_count=total_batches,
        mismatch_rows_before=0,
        mismatch_rows_after=0,
        normalized_rows_synced=total_synced_rows,
    )


def load_normalized_available_fields(db: PostgresCli) -> set[str]:
    normalized_rows = int(db.run_sql("SELECT COUNT(*) FROM normalized_market_daily;").strip() or "0")
    if normalized_rows == 0:
        return set()
    available = {"close_price_adj"}
    constraint_rows = int(db.run_sql("SELECT COUNT(*) FROM raw_trading_constraints_daily;").strip() or "0")
    if constraint_rows > 0:
        available.update({"adj_factor", "is_suspended", "is_st", "limit_up_price", "limit_down_price"})
    return available


def load_feature_available_fields(db: PostgresCli) -> set[str]:
    feature_rows = int(db.run_sql("SELECT COUNT(*) FROM research_feature_daily;").strip() or "0")
    if feature_rows == 0:
        return set()
    available: set[str] = set()
    for field_name in sorted(FEATURE_FIELDS):
        count = int(
            db.run_sql(
                f"SELECT COUNT(*) FROM research_feature_daily WHERE {field_name} IS NOT NULL;"
            ).strip()
            or "0"
        )
        if count > 0:
            available.add(field_name)
    return available


def _upsert_ingest_source_file_state(
    db: PostgresCli,
    file_states: Iterable[IncrementalFileState],
) -> None:
    values: List[str] = []
    for state in file_states:
        latest_trade_date = (
            f"'{_sql_literal(state.latest_trade_date)}'::date"
            if state.latest_trade_date
            else "NULL"
        )
        latest_trade_row_hash = (
            f"'{_sql_literal(state.latest_trade_row_hash)}'"
            if state.latest_trade_row_hash
            else "NULL"
        )
        values.append(
            "("
            f"'{_sql_literal(state.source_path)}',"
            f"'{_sql_literal(state.stock_code)}',"
            f"'{state.file_hash}',"
            f"{state.file_size_bytes},"
            f"{state.file_mtime_ns},"
            f"{state.row_count},"
            f"{latest_trade_date},"
            f"{latest_trade_row_hash}"
            ")"
        )
    if not values:
        return
    db.run_sql(
        f"""
INSERT INTO ingest_source_file_state (
  source_path,
  stock_code,
  file_hash,
  file_size_bytes,
  file_mtime_ns,
  row_count,
  latest_trade_date,
  latest_trade_row_hash
)
VALUES
  {", ".join(values)}
ON CONFLICT (source_path) DO UPDATE SET
  stock_code = EXCLUDED.stock_code,
  file_hash = EXCLUDED.file_hash,
  file_size_bytes = EXCLUDED.file_size_bytes,
  file_mtime_ns = EXCLUDED.file_mtime_ns,
  row_count = EXCLUDED.row_count,
  latest_trade_date = EXCLUDED.latest_trade_date,
  latest_trade_row_hash = EXCLUDED.latest_trade_row_hash,
  last_ingested_at = NOW();
"""
    )


def _record_base_incremental_run(
    db: PostgresCli,
    source_dir: Path,
    status: str,
    inserted_rows: int,
    conflict_rows: int,
    notes: List[str],
) -> None:
    notes_json = json.dumps(notes, ensure_ascii=False)
    db.run_sql(
        f"""
INSERT INTO ingest_runs (run_type, source_path, status, inserted_rows, conflict_rows, notes)
VALUES (
  'base_incremental',
  '{_sql_literal(str(source_dir))}',
  '{_sql_literal(status)}',
  {inserted_rows},
  {conflict_rows},
  '{_sql_literal(notes_json)}'::jsonb
);
"""
    )


def run_base_incremental_ingest(
    source_dir: Path,
    sample_size: int = 50,
    constraints_dir: Path | None = None,
    stock_codes: Iterable[str] | None = None,
    db: PostgresCli | None = None,
) -> BaseIncrementalIngestSummary:
    plan = build_base_incremental_ingest_plan()
    snapshot = inspect_stock_history(source_dir, sample_size=sample_size)
    notes = list(plan.notes)

    if snapshot is None:
        inventory = build_data_inventory(snapshot)
        notes.append("Local stock_history seed source was not found.")
        return BaseIncrementalIngestSummary(
            generated_at=datetime.now().isoformat(timespec="seconds"),
            status="missing_seed_source",
            source_snapshot=None,
            inventory=inventory,
            modules=plan.modules,
            notes=notes,
        )

    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()

    known_file_hashes = load_ingest_source_file_state(pg)
    constraints_result = run_trading_constraints_ingest(pg, constraints_dir, known_file_hashes)

    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_csv = Path(tmpdir) / "raw_market_daily_incremental.csv"
        bundle_meta = build_incremental_bundle(
            source_dir,
            bundle_csv,
            known_file_hashes,
            stock_codes=stock_codes,
        )

        if bundle_meta["files_changed"] == 0 and constraints_result.files_changed == 0:
            normalized_available_fields = load_normalized_available_fields(pg)
            _record_base_incremental_run(
                pg,
                source_dir,
                status="no_changes",
                inserted_rows=0,
                conflict_rows=0,
                notes=["No source file changes detected during base incremental ingest."],
            )
            execution = {
                "database": pg.config.db_name,
                "source_path": str(source_dir),
                "files_scanned": bundle_meta["files_scanned"],
                "files_changed": 0,
                "changed_stock_codes": [],
                "rows_prepared": 0,
                "inserted_rows": 0,
                "conflict_rows": 0,
                "unchanged_rows": 0,
                "normalized_rows_synced": 0,
                "trading_constraints": constraints_result.to_dict(),
            }
            inventory = build_data_inventory(snapshot, normalized_available_fields=normalized_available_fields)
            notes.append("No source file changes detected; database ingest was skipped.")
            if constraints_result.status in {"missing_source", "not_configured", "empty_source"}:
                notes.append(f"Trading constraints source status: {constraints_result.status}.")
            return BaseIncrementalIngestSummary(
                generated_at=datetime.now().isoformat(timespec="seconds"),
                status="no_changes",
                source_snapshot=snapshot,
                inventory=inventory,
                modules=plan.modules,
                execution=execution,
                notes=notes,
            )

        sql_path = Path(tmpdir) / "base_incremental.sql"
        sql_path.write_text(
            f"""
CREATE TEMP TABLE staging_raw_market_daily (
  stock_code TEXT,
  trade_date DATE,
  open_price NUMERIC,
  high_price NUMERIC,
  low_price NUMERIC,
  close_price NUMERIC,
  volume NUMERIC,
  turnover NUMERIC,
  raw_line_hash TEXT,
  raw_payload JSONB
);

\\copy staging_raw_market_daily FROM '{bundle_csv}' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE base_incremental_insert_candidates AS
SELECT
  staging.stock_code,
  staging.trade_date,
  staging.open_price,
  staging.high_price,
  staging.low_price,
  staging.close_price,
  staging.volume,
  staging.turnover,
  staging.raw_line_hash,
  staging.raw_payload
FROM staging_raw_market_daily AS staging
LEFT JOIN raw_market_daily AS existing
  ON existing.stock_code = staging.stock_code
 AND existing.trade_date = staging.trade_date
WHERE existing.id IS NULL
  AND NOT EXISTS (
    SELECT 1
    FROM raw_market_daily AS by_hash
    WHERE by_hash.raw_line_hash = staging.raw_line_hash
  );

CREATE TEMP TABLE base_incremental_conflict_candidates AS
SELECT
  existing.stock_code,
  existing.trade_date,
  existing.raw_line_hash AS existing_raw_line_hash,
  staging.raw_line_hash AS incoming_raw_line_hash,
  existing.raw_payload AS existing_payload,
  staging.raw_payload AS incoming_payload
FROM staging_raw_market_daily AS staging
JOIN raw_market_daily AS existing
  ON existing.stock_code = staging.stock_code
 AND existing.trade_date = staging.trade_date
WHERE {_material_change_predicate('existing', 'staging')};

INSERT INTO ingest_conflict_log (
  stock_code,
  trade_date,
  existing_raw_line_hash,
  incoming_raw_line_hash,
  existing_payload,
  incoming_payload,
  resolution
)
SELECT
  conflict.stock_code,
  conflict.trade_date,
  conflict.existing_raw_line_hash,
  conflict.incoming_raw_line_hash,
  conflict.existing_payload,
  conflict.incoming_payload,
  'manual_review_required'
FROM base_incremental_conflict_candidates AS conflict
WHERE NOT EXISTS (
    SELECT 1
    FROM ingest_conflict_log AS logged
    WHERE logged.stock_code = conflict.stock_code
      AND logged.trade_date = conflict.trade_date
      AND logged.existing_raw_line_hash = conflict.existing_raw_line_hash
      AND logged.incoming_raw_line_hash = conflict.incoming_raw_line_hash
  );

INSERT INTO raw_market_daily (
  stock_code,
  trade_date,
  open_price,
  high_price,
  low_price,
  close_price,
  volume,
  turnover,
  raw_line_hash,
  raw_payload
)
SELECT
  candidate.stock_code,
  candidate.trade_date,
  candidate.open_price,
  candidate.high_price,
  candidate.low_price,
  candidate.close_price,
  candidate.volume,
  candidate.turnover,
  candidate.raw_line_hash,
  candidate.raw_payload
FROM base_incremental_insert_candidates AS candidate;

INSERT INTO ingest_runs (run_type, source_path, status, inserted_rows, conflict_rows, notes)
SELECT
  'base_incremental',
  '{_sql_literal(str(source_dir))}',
  CASE
    WHEN (SELECT COUNT(*) FROM base_incremental_conflict_candidates) > 0
      THEN 'completed_with_conflicts'
    ELSE 'success'
  END,
  (SELECT COUNT(*) FROM base_incremental_insert_candidates),
  (SELECT COUNT(*) FROM base_incremental_conflict_candidates),
  jsonb_build_array('base incremental stock_history import')
;
""",
            encoding="utf-8",
        )
        subprocess.run(
            [str(pg.config.psql_bin), pg.config.db_url, "-v", "ON_ERROR_STOP=1", "-f", str(sql_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    run_fields = (
        pg.run_sql(
            """
SELECT status, inserted_rows, conflict_rows
FROM ingest_runs
WHERE run_type = 'base_incremental'
ORDER BY id DESC
LIMIT 1;
"""
        )
        .strip()
        .split("|")
    )
    status = run_fields[0]
    inserted_rows = int(run_fields[1]) if len(run_fields) > 1 else 0
    conflict_rows = int(run_fields[2]) if len(run_fields) > 2 else 0
    unchanged_rows = int(bundle_meta["rows_prepared"]) - inserted_rows - conflict_rows
    changed_stock_codes = [
        state.stock_code
        for state in bundle_meta["file_states"]
        if (
            known_file_hashes.get(state.source_path) is None
            or state.file_hash != known_file_hashes[state.source_path].file_hash
        )
    ]
    normalized_rows_synced = run_normalized_market_sync(
        pg,
        list(changed_stock_codes) + constraints_result.changed_stock_codes,
    )
    _upsert_ingest_source_file_state(pg, bundle_meta["file_states"])
    inventory = build_data_inventory(
        snapshot,
        normalized_available_fields=load_normalized_available_fields(pg),
    )

    execution = {
        "database": pg.config.db_name,
        "source_path": str(source_dir),
        "files_scanned": bundle_meta["files_scanned"],
        "files_changed": bundle_meta["files_changed"],
        "changed_stock_codes": sorted(set(changed_stock_codes)),
        "rows_prepared": bundle_meta["rows_prepared"],
        "inserted_rows": inserted_rows,
        "conflict_rows": conflict_rows,
        "unchanged_rows": unchanged_rows,
        "normalized_rows_synced": normalized_rows_synced,
        "trading_constraints": constraints_result.to_dict(),
    }
    notes.append("Base incremental ingest wrote new rows to raw_market_daily.")
    notes.append("Normalized market rows were upserted from raw_market_daily for changed stock files.")
    if constraints_result.files_changed:
        notes.append("Trading constraints source files were ingested and merged into normalized_market_daily.")
    elif constraints_result.status in {"missing_source", "not_configured", "empty_source"}:
        notes.append(f"Trading constraints source status: {constraints_result.status}.")
    if conflict_rows:
        notes.append("Conflicting same-day revisions were written to ingest_conflict_log.")
    else:
        notes.append("No row-level conflicts were detected during incremental ingest.")

    return BaseIncrementalIngestSummary(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        source_snapshot=snapshot,
        inventory=inventory,
        modules=plan.modules,
        execution=execution,
        notes=notes,
    )


def run_bootstrap_ingest(
    source_dir: Path,
    db: PostgresCli | None = None,
    limit_files: Optional[int] = None,
) -> BootstrapIngestResult:
    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()

    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_csv = Path(tmpdir) / "raw_market_daily_bootstrap.csv"
        bundle_meta = build_bootstrap_bundle(source_dir, bundle_csv, limit_files=limit_files)
        sql_path = Path(tmpdir) / "bootstrap.sql"
        sql_path.write_text(
            f"""
CREATE TEMP TABLE staging_raw_market_daily (
  stock_code TEXT,
  trade_date DATE,
  open_price NUMERIC,
  high_price NUMERIC,
  low_price NUMERIC,
  close_price NUMERIC,
  volume NUMERIC,
  turnover NUMERIC,
  raw_line_hash TEXT,
  raw_payload JSONB
);

\\copy staging_raw_market_daily FROM '{bundle_csv}' WITH (FORMAT csv, HEADER true)

INSERT INTO ingest_conflict_log (
  stock_code,
  trade_date,
  existing_raw_line_hash,
  incoming_raw_line_hash,
  existing_payload,
  incoming_payload,
  resolution
)
SELECT
  existing.stock_code,
  existing.trade_date,
  existing.raw_line_hash,
  staging.raw_line_hash,
  existing.raw_payload,
  staging.raw_payload,
  'manual_review_required'
FROM staging_raw_market_daily AS staging
JOIN raw_market_daily AS existing
  ON existing.stock_code = staging.stock_code
 AND existing.trade_date = staging.trade_date
WHERE {_material_change_predicate('existing', 'staging')};

INSERT INTO raw_market_daily (
  stock_code,
  trade_date,
  open_price,
  high_price,
  low_price,
  close_price,
  volume,
  turnover,
  raw_line_hash,
  raw_payload
)
SELECT
  staging.stock_code,
  staging.trade_date,
  staging.open_price,
  staging.high_price,
  staging.low_price,
  staging.close_price,
  staging.volume,
  staging.turnover,
  staging.raw_line_hash,
  staging.raw_payload
FROM staging_raw_market_daily AS staging
LEFT JOIN raw_market_daily AS existing
  ON existing.stock_code = staging.stock_code
 AND existing.trade_date = staging.trade_date
WHERE existing.id IS NULL
  AND NOT EXISTS (
    SELECT 1
    FROM raw_market_daily AS by_hash
    WHERE by_hash.raw_line_hash = staging.raw_line_hash
  );

INSERT INTO ingest_runs (run_type, source_path, status, inserted_rows, conflict_rows, notes)
SELECT
  'bootstrap',
  '{source_dir}',
  'success',
  (SELECT COUNT(*) FROM staging_raw_market_daily AS staging
   LEFT JOIN raw_market_daily AS existing
     ON existing.stock_code = staging.stock_code
    AND existing.trade_date = staging.trade_date
   WHERE existing.raw_line_hash = staging.raw_line_hash),
  (SELECT COUNT(*)
   FROM staging_raw_market_daily AS staging
   JOIN raw_market_daily AS existing
     ON existing.stock_code = staging.stock_code
    AND existing.trade_date = staging.trade_date
   WHERE existing.raw_line_hash <> staging.raw_line_hash),
  jsonb_build_array('bootstrap stock_history import');
""",
            encoding="utf-8",
        )
        subprocess.run(
            [str(pg.config.psql_bin), pg.config.db_url, "-v", "ON_ERROR_STOP=1", "-f", str(sql_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    inserted_rows = int(pg.run_sql("SELECT COUNT(*) FROM raw_market_daily;").strip() or "0")
    conflict_rows = int(pg.run_sql("SELECT COUNT(*) FROM ingest_conflict_log;").strip() or "0")
    return BootstrapIngestResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status="success",
        database=pg.config.db_name,
        source_path=str(source_dir),
        files_processed=bundle_meta["files_processed"],
        rows_prepared=bundle_meta["rows_prepared"],
        inserted_rows=inserted_rows,
        conflict_rows=conflict_rows,
        notes=["Bootstrap import wrote to raw_market_daily and ingest_conflict_log."],
    )
