from __future__ import annotations

import pandas as pd


class LookAheadError(ValueError):
    """Raised when a frame contains rows dated after the as-of cutoff."""


def as_of(frame: pd.DataFrame, asof_date, date_column: str = "trade_date") -> pd.DataFrame:
    cutoff = pd.Timestamp(asof_date)
    dates = pd.to_datetime(frame[date_column])
    return frame.loc[dates <= cutoff]


def assert_no_lookahead(frame: pd.DataFrame, asof_date, date_column: str = "trade_date") -> None:
    cutoff = pd.Timestamp(asof_date)
    dates = pd.to_datetime(frame[date_column])
    future = frame.loc[dates > cutoff]
    if not future.empty:
        raise LookAheadError(
            f"{len(future)} row(s) dated after as-of cutoff {cutoff.date()} in column {date_column!r}"
        )
