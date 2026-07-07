from __future__ import annotations

from math import sqrt
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List

from .db import PostgresCli


@dataclass
class FeatureRefreshResult:
    generated_at: str
    status: str
    database: str
    stock_codes_considered: int
    stock_codes_refreshed: int
    features_upserted: int
    rows_upserted: int
    expected_unavailable_stock_dates: int = 0
    missing_refresh_stock_dates: int = 0
    stock_codes_with_missing_refresh: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


FEATURE_SPECS = {
    "ma_5": {"window_size": 5},
    "ma_10": {"window_size": 10},
    "ma_20": {"window_size": 20},
    "ma_60": {"window_size": 60},
    "avg_volume_20d": {"window_size": 20},
    "avg_turnover_20d": {"window_size": 20},
    "volume_ratio_20d": {"window_size": 20},
    "ret_1d": {"window_size": 2},
    "ret_5d": {"window_size": 6},
    "ret_20d": {"window_size": 21},
    "momentum_20d": {"window_size": 20},
    "volatility_20d": {"window_size": 21},
}

FEATURE_COLUMNS = list(FEATURE_SPECS.keys())


def run_feature_refresh(
    db: PostgresCli | None = None,
    stock_codes: Iterable[str] | None = None,
    include_gap_diagnostics: bool = True,
) -> FeatureRefreshResult:
    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()

    if stock_codes:
        selected_codes = sorted({code for code in stock_codes if code})
    else:
        selected_codes = _load_codes_needing_refresh(pg)

    if not selected_codes:
        return FeatureRefreshResult(
            generated_at=datetime.now().isoformat(timespec="seconds"),
            status="no_changes",
            database=pg.config.db_name,
            stock_codes_considered=0,
            stock_codes_refreshed=0,
            features_upserted=0,
            rows_upserted=0,
            notes=["No stock codes needed feature refresh."],
        )

    rows_upserted = 0
    refreshed_codes = 0

    for stock_code in selected_codes:
        upserted = _refresh_stock_features(pg, stock_code)
        if upserted:
            refreshed_codes += 1
            rows_upserted += upserted

    status = "success" if rows_upserted else "no_changes"
    diagnostics = {
        "expected_unavailable_stock_dates": 0,
        "missing_refresh_stock_dates": 0,
        "stock_codes_with_missing_refresh": 0,
    }
    if include_gap_diagnostics:
        diagnostics = _load_feature_gap_diagnostics(pg, selected_codes)
    notes = ["Feature refresh uses research_feature_daily as the persisted feature store."]
    if rows_upserted:
        notes.append(
            "Feature refresh recalculates from the earliest missing feature date forward, with historical lookback for calculation windows."
        )
    notes.append(
        "Expected unavailable feature dates are the leading window warm-up period and are not treated as refresh gaps."
    )
    if not include_gap_diagnostics:
        notes.append("Gap diagnostics were skipped for this run.")

    return FeatureRefreshResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        database=pg.config.db_name,
        stock_codes_considered=len(selected_codes),
        stock_codes_refreshed=refreshed_codes,
        features_upserted=len(FEATURE_COLUMNS),
        rows_upserted=rows_upserted,
        expected_unavailable_stock_dates=diagnostics["expected_unavailable_stock_dates"],
        missing_refresh_stock_dates=diagnostics["missing_refresh_stock_dates"],
        stock_codes_with_missing_refresh=diagnostics["stock_codes_with_missing_refresh"],
        notes=notes,
    )


def _load_codes_needing_refresh(db: PostgresCli) -> List[str]:
    rows = db.run_sql(
        f"""
WITH ordered_market AS (
  SELECT
    market.stock_code,
    market.trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY market.stock_code
      ORDER BY market.trade_date
    ) AS seq_num
  FROM normalized_market_daily AS market
),
feature_flags AS (
  SELECT
    market.stock_code,
    market.trade_date,
    market.seq_num
  FROM ordered_market AS market
  LEFT JOIN research_feature_daily AS feature
    ON feature.stock_code = market.stock_code
   AND feature.trade_date = market.trade_date
  WHERE feature.trade_date IS NULL
     OR (
       market.seq_num >= {_max_window_size()}
       AND ({_missing_feature_predicate('feature')})
     )
)
SELECT DISTINCT stock_code
FROM feature_flags
ORDER BY stock_code;
"""
    ).splitlines()
    return [row.strip() for row in rows if row.strip()]


def _refresh_stock_features(db: PostgresCli, stock_code: str) -> int:
    refresh_from_date = db.run_sql(
        f"""
WITH ordered_market AS (
  SELECT
    market.trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY market.stock_code
      ORDER BY market.trade_date
    ) AS seq_num
  FROM normalized_market_daily AS market
  WHERE market.stock_code = '{stock_code}'
)
SELECT MIN(market.trade_date)
FROM ordered_market AS market
LEFT JOIN research_feature_daily AS feature
  ON feature.stock_code = '{stock_code}'
 AND feature.trade_date = market.trade_date
WHERE feature.trade_date IS NULL
   OR (
     market.seq_num >= {_max_window_size()}
     AND ({_missing_feature_predicate('feature')})
   );
"""
    ).strip()

    start_date = _load_lookback_start_date(db, stock_code, refresh_from_date)

    sql = f"""
SELECT stock_code, trade_date, close_price_adj, volume, turnover
FROM normalized_market_daily
WHERE stock_code = '{stock_code}'
"""
    if start_date:
        sql += f"\n  AND trade_date >= '{start_date}'::date"
    sql += "\nORDER BY trade_date;"

    rows = []
    for line in db.run_sql(sql).splitlines():
        if not line:
            continue
        code, trade_date, close_price_adj, volume, turnover = line.split("|", 4)
        rows.append((code, trade_date, float(close_price_adj), float(volume), float(turnover)))

    if not rows:
        return 0

    values: List[str] = []
    feature_value_count = 0
    closes = [item[2] for item in rows]
    volumes = [item[3] for item in rows]
    turnovers = [item[4] for item in rows]
    for index, (code, trade_date, close_price_adj, volume, turnover) in enumerate(rows):
        feature_row = {name: "NULL" for name in FEATURE_COLUMNS}

        if index >= 4:
            feature_row["ma_5"] = str(sum(closes[index - 4 : index + 1]) / 5)
        if index >= 9:
            feature_row["ma_10"] = str(sum(closes[index - 9 : index + 1]) / 10)
        if index >= 19:
            feature_row["ma_20"] = str(sum(closes[index - 19 : index + 1]) / 20)
            avg_volume_20d = sum(volumes[index - 19 : index + 1]) / 20
            feature_row["avg_volume_20d"] = str(avg_volume_20d)
            avg_turnover_20d = sum(turnovers[index - 19 : index + 1]) / 20
            feature_row["avg_turnover_20d"] = str(avg_turnover_20d)
            feature_row["volume_ratio_20d"] = str(volume / avg_volume_20d if avg_volume_20d else 0.0)
            feature_row["momentum_20d"] = str(close_price_adj / closes[index - 19] - 1.0)
        if index >= 59:
            feature_row["ma_60"] = str(sum(closes[index - 59 : index + 1]) / 60)
        if index >= 1:
            feature_row["ret_1d"] = str(close_price_adj / closes[index - 1] - 1.0)
        if index >= 5:
            feature_row["ret_5d"] = str(close_price_adj / closes[index - 5] - 1.0)
        if index >= 20:
            feature_row["ret_20d"] = str(close_price_adj / closes[index - 20] - 1.0)
            daily_returns = [
                closes[pos] / closes[pos - 1] - 1.0
                for pos in range(index - 19, index + 1)
            ]
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((item - mean_return) ** 2 for item in daily_returns) / len(daily_returns)
            feature_row["volatility_20d"] = str(sqrt(variance))

        if refresh_from_date and trade_date < refresh_from_date:
            continue
        feature_value_count += sum(1 for value in feature_row.values() if value != "NULL")
        values.append(_feature_row_sql(code, trade_date, feature_row))

    if not values:
        return 0

    columns_sql = ", ".join(FEATURE_COLUMNS)
    updates_sql = ",\n  ".join(f"{name} = EXCLUDED.{name}" for name in FEATURE_COLUMNS)
    for batch in _chunked(values, 500):
        db.run_sql(
            f"""
INSERT INTO research_feature_daily (
  stock_code,
  trade_date,
  {columns_sql}
)
VALUES
  {", ".join(batch)}
ON CONFLICT (stock_code, trade_date) DO UPDATE SET
  {updates_sql},
  updated_at = NOW();
"""
        )
    return feature_value_count


def _load_lookback_start_date(
    db: PostgresCli, stock_code: str, refresh_from_date: str
) -> str | None:
    if not refresh_from_date:
        return None

    return (
        db.run_sql(
            f"""
WITH ordered_market AS (
  SELECT
    market.trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY market.stock_code
      ORDER BY market.trade_date
    ) AS seq_num
  FROM normalized_market_daily AS market
  WHERE market.stock_code = '{stock_code}'
),
target_row AS (
  SELECT seq_num
  FROM ordered_market
  WHERE trade_date = '{refresh_from_date}'::date
)
SELECT MIN(lookback.trade_date)
FROM ordered_market AS lookback
CROSS JOIN target_row
WHERE lookback.seq_num >= GREATEST(target_row.seq_num - {_max_window_size()} + 1, 1)
  AND lookback.seq_num <= target_row.seq_num;
"""
        ).strip()
        or refresh_from_date
    )


def _load_feature_gap_diagnostics(db: PostgresCli, stock_codes: Iterable[str]) -> Dict[str, int]:
    codes = sorted({code for code in stock_codes if code})
    filter_sql = ""
    if codes:
        values = ", ".join(f"'{code}'" for code in codes)
        filter_sql = f"WHERE market.stock_code IN ({values})"

    rows = (
        db.run_sql(
            f"""
WITH ordered_market AS (
  SELECT
    market.stock_code,
    market.trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY market.stock_code
      ORDER BY market.trade_date
    ) AS seq_num
  FROM normalized_market_daily AS market
  {filter_sql}
)
SELECT
  CASE
    WHEN ordered_market.seq_num < {_max_window_size()} THEN 'expected_unavailable'
    ELSE 'missing_refresh'
  END AS gap_type,
  COUNT(*) AS stock_date_count,
  COUNT(DISTINCT ordered_market.stock_code) AS stock_code_count
FROM ordered_market
LEFT JOIN research_feature_daily AS feature
  ON feature.stock_code = ordered_market.stock_code
 AND feature.trade_date = ordered_market.trade_date
WHERE feature.trade_date IS NULL
   OR ({_missing_feature_predicate('feature')})
GROUP BY gap_type
ORDER BY gap_type;
"""
        )
        .strip()
        .splitlines()
    )

    result = {
        "expected_unavailable_stock_dates": 0,
        "missing_refresh_stock_dates": 0,
        "stock_codes_with_missing_refresh": 0,
    }
    for line in rows:
        if not line:
            continue
        gap_type, stock_date_count, stock_code_count = line.split("|", 2)
        if gap_type == "expected_unavailable":
            result["expected_unavailable_stock_dates"] = int(stock_date_count)
        elif gap_type == "missing_refresh":
            result["missing_refresh_stock_dates"] = int(stock_date_count)
            result["stock_codes_with_missing_refresh"] = int(stock_code_count)
    return result


def _max_window_size() -> int:
    return max(spec["window_size"] for spec in FEATURE_SPECS.values())


def _chunked(values: List[str], chunk_size: int) -> Iterable[List[str]]:
    for start in range(0, len(values), chunk_size):
        yield values[start : start + chunk_size]


def _missing_feature_predicate(alias: str) -> str:
    return " OR ".join(f"{alias}.{name} IS NULL" for name in FEATURE_COLUMNS)


def _feature_row_sql(stock_code: str, trade_date: str, feature_row: Dict[str, str]) -> str:
    values = ", ".join(feature_row[name] for name in FEATURE_COLUMNS)
    return (
        "("
        f"'{stock_code}',"
        f"'{trade_date}'::date,"
        f"{values}"
        ")"
    )
