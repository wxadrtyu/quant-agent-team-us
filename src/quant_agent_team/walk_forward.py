from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


def _shift_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # Feb 29 -> Feb 28 in a non-leap target year (clamp to end of February)
        return date(value.year + years, 2, 28)


@dataclass(frozen=True)
class WindowSplit:
    development_start: date
    development_end: date
    holdout_start: date
    holdout_end: date


def split_three_year_window(
    end_date: date,
    development_years: int = 2,
    holdout_years: int = 1,
) -> WindowSplit:
    holdout_end = end_date
    holdout_start = _shift_years(end_date, -holdout_years) + timedelta(days=1)
    development_end = holdout_start - timedelta(days=1)
    development_start = _shift_years(holdout_start, -development_years)
    return WindowSplit(
        development_start=development_start,
        development_end=development_end,
        holdout_start=holdout_start,
        holdout_end=holdout_end,
    )


@dataclass(frozen=True)
class Fold:
    train: List[date]
    test: List[date]


def _contiguous_blocks(n: int, n_folds: int) -> List[range]:
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    base, extra = divmod(n, n_folds)
    blocks: List[range] = []
    start = 0
    for i in range(n_folds):
        size = base + (1 if i < extra else 0)
        if size == 0:
            continue
        blocks.append(range(start, start + size))
        start += size
    return blocks


def purged_walk_forward(
    dates: List[date],
    n_folds: int,
    embargo: int = 1,
    min_train: int = 1,
) -> List[Fold]:
    if list(dates) != sorted(set(dates)):
        raise ValueError("dates must be sorted ascending and unique")
    folds: List[Fold] = []
    for block in _contiguous_blocks(len(dates), n_folds):
        test_start = block.start
        train_end = test_start - embargo
        if train_end < min_train:
            continue
        train = list(dates[:train_end])
        test = list(dates[block.start:block.stop])
        folds.append(Fold(train=train, test=test))
    return folds
