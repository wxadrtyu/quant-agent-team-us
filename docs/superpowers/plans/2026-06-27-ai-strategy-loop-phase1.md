# AI Strategy Loop — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the trustworthy backtest core — non-zero transaction costs, a look-ahead guard, a purged walk-forward splitter, the 3-year window split, and a return-focused evaluation gate — plus the data-layer enablers (cross-platform DB config, `market` discriminator).

**Architecture:** Add small, pure-Python, independently testable modules (`cost_model.py`, `walk_forward.py`, `point_in_time.py`) and extend the existing `backtest_runner.py`, `evaluation.py`, and `db.py`. Each unit is testable without a live database or network, matching the existing suite's pattern of in-memory pandas frames and `unittest.TestCase`.

**Tech Stack:** Python ≥3.9, `pandas`, `numpy` (already used), `unittest` run via `pytest` (configured in `pyproject.toml` with `pythonpath = ["src"]`).

**Source spec:** [`docs/superpowers/specs/2026-06-27-ai-strategy-generation-loop-design.md`](../specs/2026-06-27-ai-strategy-generation-loop-design.md) (Chinese mirror `.zh-CN.md`). This plan implements spec §5.3 (cost model, look-ahead guard, purged walk-forward), §4.1 (3-year split), §5.5 (acceptance gate, thresholds from request), and the Phase 1 slice of §5.7 (data layer).

## Global Constraints

- Python ≥ 3.9 (`pyproject.toml`); no new third-party dependencies in Phase 1 (Optuna arrives in Phase 2).
- Transaction-cost defaults MUST be non-zero (spec §1.3, §5.3).
- Acceptance thresholds MUST come from a passed-in criteria object — no hardcoded module defaults on the new path (spec §5.5).
- Tests use `unittest.TestCase`; every test file starts with the `src` path shim used across `tests/` (copy verbatim from existing tests).
- The single retained performance floor is max drawdown ≤ 30%; win-rate and Sharpe gates are dropped on the new path (spec §1.1–1.2).
- Commit after each task.

---

### Task 1: Transaction cost model

**Files:**
- Create: `src/quant_agent_team/cost_model.py`
- Test: `tests/test_cost_model.py`

**Interfaces:**
- Produces: `CostModel(commission_bps: float = 5.0, slippage_bps: float = 10.0)` with methods `entry_fill_price(reference_price: float) -> float`, `exit_fill_price(reference_price: float) -> float`, `commission(notional: float) -> float`, and classmethod `for_market(market: str) -> CostModel` (`"cn"` / `"us"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_model.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.cost_model import CostModel


class CostModelTest(unittest.TestCase):
    def test_entry_fill_is_worse_than_reference(self) -> None:
        model = CostModel(commission_bps=5.0, slippage_bps=10.0)
        self.assertAlmostEqual(model.entry_fill_price(100.0), 100.1)

    def test_exit_fill_is_worse_than_reference(self) -> None:
        model = CostModel(commission_bps=5.0, slippage_bps=10.0)
        self.assertAlmostEqual(model.exit_fill_price(100.0), 99.9)

    def test_commission_scales_with_notional(self) -> None:
        model = CostModel(commission_bps=5.0, slippage_bps=10.0)
        self.assertAlmostEqual(model.commission(1_000_000.0), 500.0)

    def test_zero_model_is_frictionless(self) -> None:
        model = CostModel(commission_bps=0.0, slippage_bps=0.0)
        self.assertEqual(model.entry_fill_price(100.0), 100.0)
        self.assertEqual(model.exit_fill_price(100.0), 100.0)
        self.assertEqual(model.commission(1_000_000.0), 0.0)

    def test_for_market_presets_are_non_zero(self) -> None:
        cn = CostModel.for_market("cn")
        us = CostModel.for_market("us")
        self.assertGreater(cn.commission_bps + cn.slippage_bps, 0.0)
        self.assertGreater(us.commission_bps + us.slippage_bps, 0.0)
        with self.assertRaises(ValueError):
            CostModel.for_market("jp")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cost_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.cost_model'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/cost_model.py
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_COMMISSION_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 10.0
_BPS = 10_000.0


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = DEFAULT_COMMISSION_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def entry_fill_price(self, reference_price: float) -> float:
        return reference_price * (1.0 + self.slippage_bps / _BPS)

    def exit_fill_price(self, reference_price: float) -> float:
        return reference_price * (1.0 - self.slippage_bps / _BPS)

    def commission(self, notional: float) -> float:
        return abs(notional) * self.commission_bps / _BPS

    @classmethod
    def for_market(cls, market: str) -> "CostModel":
        if market == "cn":
            return cls(commission_bps=5.0, slippage_bps=10.0)
        if market == "us":
            return cls(commission_bps=1.0, slippage_bps=5.0)
        raise ValueError(f"Unknown market: {market!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cost_model.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/cost_model.py tests/test_cost_model.py
git commit -m "feat: add transaction cost model with non-zero defaults"
```

---

### Task 2: Wire the cost model into the backtest simulation

**Files:**
- Modify: `src/quant_agent_team/backtest_runner.py` (`run_backtest`, `_simulate_strategy`)
- Test: `tests/test_backtest_costs.py`

**Interfaces:**
- Consumes: `CostModel` from Task 1.
- Produces: `_simulate_strategy(spec, frame, initial_capital, cost_model: CostModel | None = None)` and `run_backtest(spec, start_date=None, end_date=None, initial_capital=1_000_000.0, db=None, cost_model: CostModel | None = None)`. When `cost_model is None`, a default `CostModel()` (non-zero) is used.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backtest_costs.py
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.backtest_runner import _simulate_strategy
from quant_agent_team.cost_model import CostModel


def _two_day_entry_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_code": "000001", "trade_date": pd.Timestamp("2025-01-02"),
                "open_price": 10.0, "high_price": 10.1, "low_price": 9.9,
                "close_price": 10.0, "close_price_adj": 10.0, "volume": 1000.0,
                "turnover": 10000.0, "adj_factor": 1.0, "is_suspended": False,
                "is_st": False, "limit_up_price": None, "limit_down_price": None,
                "ret_1d": 0.0, "ranking_score": 1.0, "day_seq": 0,
                "next_trade_date": pd.Timestamp("2025-01-03"), "next_open_price": 10.0,
                "next_open_gap_pct": 0.0,
            },
            {
                "stock_code": "000001", "trade_date": pd.Timestamp("2025-01-03"),
                "open_price": 10.0, "high_price": 10.2, "low_price": 9.8,
                "close_price": 10.5, "close_price_adj": 10.5, "volume": 1000.0,
                "turnover": 10500.0, "adj_factor": 1.0, "is_suspended": False,
                "is_st": False, "limit_up_price": None, "limit_down_price": None,
                "ret_1d": 0.05, "ranking_score": 1.0, "day_seq": 1,
                "next_trade_date": pd.NaT, "next_open_price": float("nan"),
                "next_open_gap_pct": float("nan"),
            },
        ]
    )

def _spec() -> SimpleNamespace:
    return SimpleNamespace(
        spec_id="spec-test", strategy_id="demo",
        ranking_formula=SimpleNamespace(formula="1", sort_direction="desc"),
        position_rules=SimpleNamespace(max_positions=1, min_holding_days_before_exit=0, rebalance_frequency="daily"),
        filters=[],
        entry_rules=[SimpleNamespace(rule_id="buy", logic="AND", conditions=[{"field": "ret_1d", "operator": "between", "value": [-0.01, 0.01]}])],
        exit_rules=[],
    )


class BacktestCostTest(unittest.TestCase):
    def test_costs_reduce_return_without_changing_trade_structure(self) -> None:
        zero = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0, cost_model=CostModel(0.0, 0.0))
        default = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0)
        self.assertEqual(default.trade_count, zero.trade_count)
        self.assertEqual(default.trade_count, 1)
        self.assertLess(default.total_return, zero.total_return)

    def test_default_cost_model_is_non_zero(self) -> None:
        default = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0)
        frictionless = _simulate_strategy(_spec(), _two_day_entry_frame(), initial_capital=100000.0, cost_model=CostModel(0.0, 0.0))
        self.assertNotAlmostEqual(default.total_return, frictionless.total_return)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest_costs.py -v`
Expected: FAIL with `TypeError: _simulate_strategy() got an unexpected keyword argument 'cost_model'`

- [ ] **Step 3: Write minimal implementation**

In `src/quant_agent_team/backtest_runner.py`, add the import near the top (after `from .models import StrategySpec, TradingRule`):

```python
from .cost_model import CostModel
```

Change the `run_backtest` signature and its call to `_simulate_strategy`:

```python
def run_backtest(
    spec: StrategySpec,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_capital: float = 1_000_000.0,
    db: PostgresCli | None = None,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()
    frame = load_backtest_frame(pg, spec, start_date=start_date, end_date=end_date)
    if frame.empty:
        raise ValueError("No market/feature rows available for the requested backtest range.")
    return _simulate_strategy(spec, frame, initial_capital=initial_capital, cost_model=cost_model)
```

Change the `_simulate_strategy` signature:

```python
def _simulate_strategy(
    spec: StrategySpec,
    frame: pd.DataFrame,
    initial_capital: float,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    costs = cost_model if cost_model is not None else CostModel()
    frame = frame.copy()
```

In the entry-execution block (the `for order in pending_entries.pop(trade_date, []):` loop), replace the fill/cash lines:

```python
            raw_entry_price = _numeric(row.get("open_price"))
            if not raw_entry_price or not np.isfinite(raw_entry_price):
                continue
            entry_price = costs.entry_fill_price(raw_entry_price)
            slot_capital = cash / max(1, max_positions - len(open_positions))
            if slot_capital <= 0:
                continue
            shares = slot_capital / entry_price
            cash -= slot_capital
            cash -= costs.commission(slot_capital)
```

In the exit-execution block (the `for order in pending_exits.pop(trade_date, []):` loop), replace the exit price/cash lines:

```python
            row = _row_for_stock(day_frame, stock_code)
            raw_exit_price = _numeric(row.get("open_price")) if row is not None else position["last_close"]
            exit_price = costs.exit_fill_price(raw_exit_price)
            proceeds = position["shares"] * exit_price
            cash += proceeds
            cash -= costs.commission(proceeds)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest_costs.py tests/test_backtest.py -v`
Expected: PASS (new cost tests pass; existing `test_backtest.py` trade-count/date assertions still pass — costs change prices, not counts or dates)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/backtest_runner.py tests/test_backtest_costs.py
git commit -m "feat: apply non-zero costs by default in backtest simulation"
```

---

### Task 3: Three-year window split

**Files:**
- Create: `src/quant_agent_team/walk_forward.py`
- Test: `tests/test_walk_forward.py`

**Interfaces:**
- Produces: `WindowSplit(development_start, development_end, holdout_start, holdout_end)` (all `datetime.date`) and `split_three_year_window(end_date: date, development_years: int = 2, holdout_years: int = 1) -> WindowSplit`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_walk_forward.py
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.walk_forward import split_three_year_window


class WindowSplitTest(unittest.TestCase):
    def test_split_three_year_window_boundaries(self) -> None:
        split = split_three_year_window(date(2026, 6, 27))
        self.assertEqual(split.holdout_end, date(2026, 6, 27))
        self.assertEqual(split.holdout_start, date(2025, 6, 28))
        self.assertEqual(split.development_end, date(2025, 6, 27))
        self.assertEqual(split.development_start, date(2023, 6, 28))

    def test_split_handles_leap_day_end(self) -> None:
        split = split_three_year_window(date(2024, 2, 29))
        self.assertEqual(split.holdout_start, date(2023, 3, 1))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_walk_forward.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.walk_forward'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/walk_forward.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_walk_forward.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/walk_forward.py tests/test_walk_forward.py
git commit -m "feat: add 3-year development/holdout window split"
```

---

### Task 4: Purged walk-forward fold splitter

**Files:**
- Modify: `src/quant_agent_team/walk_forward.py`
- Test: `tests/test_walk_forward.py` (add a class)

**Interfaces:**
- Produces: `Fold(train: list[date], test: list[date])` and `purged_walk_forward(dates: list[date], n_folds: int, embargo: int = 1, min_train: int = 1) -> list[Fold]`. `dates` must be sorted ascending and unique. `embargo` is the number of bars dropped immediately before each test block (covers label-overlap purge + embargo). Folds whose train side would be shorter than `min_train` are skipped.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_walk_forward.py
from datetime import date, timedelta

from quant_agent_team.walk_forward import purged_walk_forward


class PurgedWalkForwardTest(unittest.TestCase):
    def _dates(self, n: int) -> list:
        start = date(2025, 1, 1)
        return [start + timedelta(days=i) for i in range(n)]

    def test_two_folds_purge_embargo_bar(self) -> None:
        dates = self._dates(10)
        folds = purged_walk_forward(dates, n_folds=2, embargo=1)
        self.assertEqual(len(folds), 1)  # first block has no train side
        fold = folds[0]
        self.assertEqual(fold.test, dates[5:10])
        self.assertEqual(fold.train, dates[0:4])  # index 4 dropped as embargo
        self.assertNotIn(dates[4], fold.train)

    def test_no_train_overlaps_test(self) -> None:
        dates = self._dates(12)
        for fold in purged_walk_forward(dates, n_folds=3, embargo=1):
            self.assertTrue(max(fold.train) < min(fold.test))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_walk_forward.py::PurgedWalkForwardTest -v`
Expected: FAIL with `ImportError: cannot import name 'purged_walk_forward'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/quant_agent_team/walk_forward.py`:

```python
from typing import List


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_walk_forward.py -v`
Expected: PASS (all window + purged-walk-forward tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/walk_forward.py tests/test_walk_forward.py
git commit -m "feat: add purged walk-forward fold splitter"
```

---

### Task 5: Look-ahead guard

**Files:**
- Create: `src/quant_agent_team/point_in_time.py`
- Test: `tests/test_point_in_time.py`

**Interfaces:**
- Produces: `LookAheadError(ValueError)`, `as_of(frame: pd.DataFrame, asof_date, date_column: str = "trade_date") -> pd.DataFrame` (rows with `date <= asof`), and `assert_no_lookahead(frame: pd.DataFrame, asof_date, date_column: str = "trade_date") -> None` (raises `LookAheadError` if any row's date exceeds `asof_date`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_point_in_time.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.point_in_time import LookAheadError, as_of, assert_no_lookahead


class PointInTimeTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame({"trade_date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]), "x": [1, 2, 3]})

    def test_as_of_excludes_future_rows(self) -> None:
        sliced = as_of(self._frame(), "2025-01-02")
        self.assertEqual(sliced["x"].tolist(), [1, 2])

    def test_assert_no_lookahead_passes_for_clean_frame(self) -> None:
        assert_no_lookahead(as_of(self._frame(), "2025-01-02"), "2025-01-02")

    def test_assert_no_lookahead_raises_on_future_row(self) -> None:
        with self.assertRaises(LookAheadError):
            assert_no_lookahead(self._frame(), "2025-01-02")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_point_in_time.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.point_in_time'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/point_in_time.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_point_in_time.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/point_in_time.py tests/test_point_in_time.py
git commit -m "feat: add point-in-time look-ahead guard"
```

---

### Task 6: Return-focused evaluation gate

**Files:**
- Modify: `src/quant_agent_team/evaluation.py`
- Test: `tests/test_evaluation_honesty.py`

**Interfaces:**
- Consumes: `BacktestResult` from `backtest_runner.py`.
- Produces: `AcceptanceCriteria(min_annualized_return: float, max_drawdown_limit: float, min_trade_count: int)` and `evaluate_strategy(result: BacktestResult, criteria: AcceptanceCriteria) -> EvaluationResult`. `criteria` is required (no default) — calling without it raises `TypeError`. Gate checks only: annualized return ≥ floor, max drawdown ≤ limit, trade count ≥ minimum. The existing `evaluate_backtest_result` is left untouched for backward compatibility.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evaluation_honesty.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.backtest_runner import BacktestResult
from quant_agent_team.evaluation import AcceptanceCriteria, evaluate_strategy


def _result(annualized_return: float, max_drawdown: float, trade_count: int) -> BacktestResult:
    return BacktestResult(
        generated_at="2026-06-27T00:00:00", spec_id="s", strategy_id="d",
        start_date="2023-06-28", end_date="2025-06-27", trade_count=trade_count,
        trade_win_rate=0.0, annualized_return=annualized_return, total_return=0.0,
        max_drawdown=max_drawdown, sharpe=0.0, average_holding_days=0.0,
        equity_curve_points=500,
    )


class EvaluationHonestyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.criteria = AcceptanceCriteria(min_annualized_return=0.30, max_drawdown_limit=0.30, min_trade_count=20)

    def test_passes_when_all_gates_met(self) -> None:
        ev = evaluate_strategy(_result(0.35, 0.25, 30), self.criteria)
        self.assertTrue(ev.passed)
        self.assertEqual(ev.failed_checks, [])

    def test_fails_on_low_return(self) -> None:
        ev = evaluate_strategy(_result(0.10, 0.25, 30), self.criteria)
        self.assertFalse(ev.passed)
        self.assertIn("annualized_return", ev.failed_checks)

    def test_fails_on_excess_drawdown(self) -> None:
        ev = evaluate_strategy(_result(0.40, 0.35, 30), self.criteria)
        self.assertIn("max_drawdown", ev.failed_checks)

    def test_fails_on_too_few_trades(self) -> None:
        ev = evaluate_strategy(_result(0.40, 0.20, 5), self.criteria)
        self.assertIn("trade_count", ev.failed_checks)

    def test_criteria_is_required(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_strategy(_result(0.40, 0.20, 30))  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evaluation_honesty.py -v`
Expected: FAIL with `ImportError: cannot import name 'AcceptanceCriteria'`

- [ ] **Step 3: Write minimal implementation**

In `src/quant_agent_team/evaluation.py`, add after the `EvaluationResult` dataclass:

```python
@dataclass
class AcceptanceCriteria:
    min_annualized_return: float
    max_drawdown_limit: float
    min_trade_count: int


def evaluate_strategy(result: BacktestResult, criteria: AcceptanceCriteria) -> EvaluationResult:
    failed_checks: List[str] = []
    if result.annualized_return < criteria.min_annualized_return:
        failed_checks.append("annualized_return")
    if result.max_drawdown > criteria.max_drawdown_limit:
        failed_checks.append("max_drawdown")
    if result.trade_count < criteria.min_trade_count:
        failed_checks.append("trade_count")

    notes = (
        ["Strategy did not satisfy the return-focused acceptance gate."]
        if failed_checks
        else ["Strategy satisfied the return-focused acceptance gate."]
    )
    return EvaluationResult(
        spec_id=result.spec_id,
        strategy_id=result.strategy_id,
        passed=not failed_checks,
        thresholds={
            "min_annualized_return": criteria.min_annualized_return,
            "max_drawdown_limit": criteria.max_drawdown_limit,
            "min_trade_count": float(criteria.min_trade_count),
        },
        observed_metrics={
            "annualized_return": result.annualized_return,
            "max_drawdown": result.max_drawdown,
            "trade_count": float(result.trade_count),
        },
        failed_checks=failed_checks,
        notes=notes,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_evaluation_honesty.py tests/test_backtest.py -v`
Expected: PASS (new gate tests pass; existing `evaluate_backtest_result` test still passes)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/evaluation.py tests/test_evaluation_honesty.py
git commit -m "feat: add return-focused acceptance gate with required criteria"
```

---

### Task 7: Cross-platform database configuration

**Files:**
- Modify: `src/quant_agent_team/db.py` (`DatabaseConfig`, `PostgresCli.ensure_database`)
- Test: `tests/test_db_config.py`

**Interfaces:**
- Produces: `DatabaseConfig.from_env()` resolves `psql_bin`/`createdb_bin` from `QUANT_PSQL_BIN`/`QUANT_CREATEDB_BIN`, falling back to `shutil.which("psql")`/`shutil.which("createdb")`, then bare `"psql"`/`"createdb"`. `DatabaseConfig.db_name` parses both `postgresql:///name?host=/tmp` and `postgresql://host:port/name` forms.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_config.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import DatabaseConfig


class DbConfigTest(unittest.TestCase):
    def test_db_name_parses_socket_url(self) -> None:
        cfg = DatabaseConfig(db_url="postgresql:///quant_agent_team?host=/tmp")
        self.assertEqual(cfg.db_name, "quant_agent_team")

    def test_db_name_parses_host_url(self) -> None:
        cfg = DatabaseConfig(db_url="postgresql://localhost:5432/quant_agent_team")
        self.assertEqual(cfg.db_name, "quant_agent_team")

    def test_from_env_reads_psql_bin(self, ) -> None:
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"QUANT_PSQL_BIN": "/custom/psql"}):
            cfg = DatabaseConfig.from_env()
        self.assertEqual(cfg.psql_bin, Path("/custom/psql"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db_config.py -v`
Expected: FAIL on `test_db_name_parses_host_url` (`ValueError: Unsupported db url format`) and `test_from_env_reads_psql_bin` (env var ignored)

- [ ] **Step 3: Write minimal implementation**

In `src/quant_agent_team/db.py`, add `import shutil` at the top with the other imports. Replace the `DatabaseConfig.from_env` classmethod and `db_name` property:

```python
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
```

Add this module-level helper just above the `DatabaseConfig` dataclass:

```python
def _resolve_bin(env_var: str, command: str, fallback: Path) -> Path:
    override = os.getenv(env_var)
    if override:
        return Path(override)
    found = shutil.which(command)
    if found:
        return Path(found)
    return fallback if fallback.exists() else Path(command)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/db.py tests/test_db_config.py
git commit -m "feat: resolve psql binaries and db name cross-platform"
```

---

### Task 8: `market` discriminator column

**Files:**
- Modify: `src/quant_agent_team/db.py` (`RAW_MARKET_DDL`)
- Test: `tests/test_db_schema.py`

**Interfaces:**
- Produces: `raw_market_daily` and `normalized_market_daily` gain a `market TEXT NOT NULL DEFAULT 'cn'` column via idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. (Backfills existing A-share rows to `'cn'`; US ingestion in Phase 4 writes `'us'`.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_schema.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import RAW_MARKET_DDL


class DbSchemaTest(unittest.TestCase):
    def test_market_column_added_to_raw_and_normalized(self) -> None:
        self.assertIn("ALTER TABLE raw_market_daily", RAW_MARKET_DDL)
        self.assertIn("ALTER TABLE normalized_market_daily", RAW_MARKET_DDL)
        self.assertEqual(RAW_MARKET_DDL.count("ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'cn'"), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db_schema.py -v`
Expected: FAIL (`market` column ALTERs not present; count is 0)

- [ ] **Step 3: Write minimal implementation**

In `src/quant_agent_team/db.py`, append these two statements inside the `RAW_MARKET_DDL` string, immediately before the closing `"""`:

```sql

ALTER TABLE raw_market_daily
  ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'cn';

ALTER TABLE normalized_market_daily
  ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'cn';
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db_schema.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/db.py tests/test_db_schema.py
git commit -m "feat: add market discriminator column to market tables"
```

---

### Task 9: Phase 1 regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -v`
Expected: PASS for all non-DB tests. DB-integration tests in `tests/test_workflow.py` that call `self.skipTest("PostgreSQL CLI is not available...")` will SKIP on machines without a local PostgreSQL — that is expected, not a failure.

- [ ] **Step 2: Commit (if any incidental fixes were needed)**

```bash
git add -A
git commit -m "test: confirm Phase 1 suite green"
```

---

## Deferred to later plans / phases

- **Point-in-time survivorship-free universe (data sourcing).** Spec §5.7 marks this the highest-importance data task, but acquiring historical constituent/delisting data is an operational data task, not unit-testable in isolation. It gets its own plan (loader + membership-query logic with fixture data) before Phase 4's US work.
- **`strategy_data_sync` hard gate (`MissingDependencyError`).** Small but belongs with the Phase 2 orchestration that actually invokes the gate before a backtest; specced there.
- **Phase 2:** Optuna HPO + linear-composite factor scoring + acceptance gate wired into the walk-forward objective.
- **Phase 3:** LLM generation outer loop + `OverfittingScore` + deflated performance + null test.
- **Phase 4:** `HoldoutVault` + `PaperTradeRunner` + US market provider.

## Self-Review

- **Spec coverage (Phase 1 slice):** cost model §5.3 → Tasks 1–2; look-ahead guard §5.3 → Task 5; purged walk-forward §5.3 + 3-year split §4.1 → Tasks 3–4; return-focused gate with required thresholds §5.5 → Task 6; data-layer enablers §5.7 (market column) → Task 8; portability prerequisite → Task 7. The PIT survivorship-free universe (§5.7) is explicitly deferred above with rationale. No Phase 1 requirement is left without a task or an explicit deferral.
- **Placeholder scan:** every code step contains complete code; no "TBD"/"add error handling"/"similar to Task N".
- **Type consistency:** `CostModel` constructor and methods (`entry_fill_price`, `exit_fill_price`, `commission`, `for_market`) are used identically in Tasks 1–2; `_simulate_strategy(..., cost_model=...)` keyword matches between definition and tests; `AcceptanceCriteria` field names (`min_annualized_return`, `max_drawdown_limit`, `min_trade_count`) match between Task 6 implementation and test; `purged_walk_forward`/`Fold` names match across Task 4; `DatabaseConfig.from_env`/`db_name`/`_resolve_bin` match across Task 7.
