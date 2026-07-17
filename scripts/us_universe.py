from __future__ import annotations

from pathlib import Path

import pandas as pd


PIT_COLUMNS = [
    "symbol",
    "universe_name",
    "start_date",
    "end_date",
    "membership_type",
    "source",
    "as_of_date",
]


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.replace("", pd.NA), errors="coerce")


def normalize_pit_membership(membership: pd.DataFrame, source: str, as_of_date: str) -> pd.DataFrame:
    required = {"symbol", "universe_name", "start_date", "end_date"}
    missing = required - set(membership.columns)
    if missing:
        raise ValueError(f"PIT membership missing columns: {sorted(missing)}")

    frame = membership.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["universe_name"] = frame["universe_name"].astype(str).str.strip()
    frame["start_date"] = _to_datetime(frame["start_date"])
    frame["end_date"] = _to_datetime(frame["end_date"])
    frame["membership_type"] = frame.get("membership_type", "pit_interval")
    frame["membership_type"] = frame["membership_type"].fillna("pit_interval").astype(str)
    frame.loc[frame["membership_type"].eq(""), "membership_type"] = "pit_interval"
    frame["source"] = source
    frame["as_of_date"] = pd.Timestamp(as_of_date).date().isoformat()
    frame = frame.dropna(subset=["symbol", "universe_name", "start_date"])
    frame = frame[frame["symbol"].ne("") & frame["universe_name"].ne("")]
    return frame[PIT_COLUMNS].sort_values(["universe_name", "symbol", "start_date"]).reset_index(drop=True)


def load_pit_membership(path: Path, source: str, as_of_date: str) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    return normalize_pit_membership(frame, source=source, as_of_date=as_of_date)


def filter_panel_by_pit(
    panel: pd.DataFrame,
    membership: pd.DataFrame,
    universe_names: list[str] | None = None,
) -> pd.DataFrame:
    if panel.empty or membership.empty:
        return panel.iloc[0:0].copy()

    left = panel.copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"])
    left["symbol"] = left["symbol"].astype(str).str.upper().str.strip()
    members = membership.copy()
    members["start_date"] = pd.to_datetime(members["start_date"])
    members["end_date"] = pd.to_datetime(members["end_date"], errors="coerce")
    if universe_names:
        allowed = {name.strip() for name in universe_names}
        members = members[members["universe_name"].isin(allowed)].copy()
    if members.empty:
        return left.iloc[0:0].copy()

    joined = left.merge(members[["symbol", "universe_name", "start_date", "end_date"]], on="symbol", how="inner")
    active = (joined["trade_date"] >= joined["start_date"]) & (
        joined["end_date"].isna() | (joined["trade_date"] <= joined["end_date"])
    )
    filtered = joined.loc[active, panel.columns].drop_duplicates().sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    return filtered


def build_dynamic_liquidity_membership(
    prices: pd.DataFrame,
    min_price: float,
    min_dollar_volume_20d: float,
) -> pd.DataFrame:
    required = {"symbol", "trade_date", "close", "dollar_volume_20d"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"prices missing columns: {sorted(missing)}")

    frame = prices.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["dollar_volume_20d"] = pd.to_numeric(frame["dollar_volume_20d"], errors="coerce")
    frame = frame[(frame["close"] >= min_price) & (frame["dollar_volume_20d"] >= min_dollar_volume_20d)].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["universe_name"] = "dynamic_liquidity"
    frame["membership_type"] = "daily_dynamic_liquidity"
    frame["start_date"] = frame["trade_date"]
    frame["end_date"] = frame["trade_date"]
    frame["source"] = "loaded_price_panel"
    frame["as_of_date"] = pd.Timestamp.now(tz="UTC").date().isoformat()
    return frame[PIT_COLUMNS].sort_values(["start_date", "symbol"]).reset_index(drop=True)
