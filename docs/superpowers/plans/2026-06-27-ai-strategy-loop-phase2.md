# AI Strategy Loop — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the linear multi-factor strategy core — composite z-score scoring, a periodic-rebalance factor backtest with costs, a purged walk-forward CV objective, and an Optuna hyperparameter search — wired through to the Phase 1 acceptance gate, on a fixed factor hypothesis.

**Architecture:** New pure-Python modules (`hypothesis.py`, `factor_scoring.py`, `factor_backtest.py`, `hpo.py`) that compose Phase 1's `CostModel`, `walk_forward`, and `evaluation.AcceptanceCriteria`. The factor model is a separate path from the existing rule-based `backtest_runner._simulate_strategy` — it selects top-N by composite score and rebalances periodically. Scoring, the backtest, and the CV objective are testable without Optuna or a database; only the thin `optimize()` wrapper needs Optuna.

**Tech Stack:** Python ≥3.9, `pandas`, `numpy` (Phase 1), plus **`optuna`** (new dependency). `unittest` via `pytest`.

**Source spec:** [`docs/superpowers/specs/2026-06-27-ai-strategy-generation-loop-design.md`](../specs/2026-06-27-ai-strategy-generation-loop-design.md). Implements §5.1 (hypothesis/hyperparameter representation), §5.2 (linear composite scoring), §5.4 (Optuna HPO + CV objective + trial bookkeeping), and the Phase 2 wiring of §5.5 (acceptance gate).

**Builds on Phase 1:** `from .cost_model import CostModel`; `from .walk_forward import purged_walk_forward, Fold`; `from .evaluation import AcceptanceCriteria, evaluate_strategy`; `from .backtest_runner import BacktestResult`.

## Global Constraints

- Python ≥ 3.9; new dependency `optuna` declared in `pyproject.toml`.
- Transaction costs always applied via Phase 1 `CostModel` with non-zero default (spec §1.3).
- HPO objective is scored on **out-of-sample** walk-forward folds only — never in-sample (spec §2, §5.4).
- Max drawdown ≤ 30% is a hard penalty in the objective; min trade count is a hard penalty (spec §1.2, validity gates).
- Total Optuna trial count is recorded on the result for the later (Phase 3) deflation (spec §5.4).
- Combination model is fixed to `linear_zscore` this phase (spec §5.2; ML ranker deferred).
- Tests use `unittest.TestCase` with the standard `src` path shim; commit after each task.

---

### Task 1: Hypothesis and hyperparameter representation

**Files:**
- Create: `src/quant_agent_team/hypothesis.py`
- Test: `tests/test_hypothesis.py`

**Interfaces:**
- Produces:
  - `FactorDef(name: str, source_field: str, direction: str)` — `direction` in `{"long_high", "long_low"}`, validated.
  - `FactorHypothesis(market: str, factors: list[FactorDef], sector_neutral: bool = False, combination: str = "linear_zscore")` — `market` in `{"cn", "us"}`; 1–8 factors (parsimony cap), validated; `combination` must be `"linear_zscore"`.
  - `FactorConfig(weights: dict[str, float], top_n: int, rebalance_days: int)` — a resolved point in hyperparameter space (what HPO produces).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hypothesis.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


class HypothesisTest(unittest.TestCase):
    def test_factor_def_validates_direction(self) -> None:
        FactorDef(name="momentum_20d", source_field="momentum_20d", direction="long_high")
        with self.assertRaises(ValueError):
            FactorDef(name="x", source_field="x", direction="sideways")

    def test_hypothesis_validates_market_and_factor_count(self) -> None:
        factors = [FactorDef("momentum_20d", "momentum_20d", "long_high")]
        h = FactorHypothesis(market="cn", factors=factors)
        self.assertEqual(h.combination, "linear_zscore")
        with self.assertRaises(ValueError):
            FactorHypothesis(market="jp", factors=factors)
        with self.assertRaises(ValueError):
            FactorHypothesis(market="cn", factors=[])

    def test_hypothesis_enforces_parsimony_cap(self) -> None:
        too_many = [FactorDef(f"f{i}", f"f{i}", "long_high") for i in range(9)]
        with self.assertRaises(ValueError):
            FactorHypothesis(market="cn", factors=too_many)

    def test_factor_config_holds_resolved_params(self) -> None:
        cfg = FactorConfig(weights={"momentum_20d": 1.0}, top_n=10, rebalance_days=5)
        self.assertEqual(cfg.top_n, 10)
        self.assertEqual(cfg.rebalance_days, 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hypothesis.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.hypothesis'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/hypothesis.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

MAX_FACTORS = 8


@dataclass(frozen=True)
class FactorDef:
    name: str
    source_field: str
    direction: str

    def __post_init__(self) -> None:
        if self.direction not in {"long_high", "long_low"}:
            raise ValueError(f"direction must be 'long_high' or 'long_low', got {self.direction!r}")


@dataclass
class FactorHypothesis:
    market: str
    factors: List[FactorDef]
    sector_neutral: bool = False
    combination: str = "linear_zscore"

    def __post_init__(self) -> None:
        if self.market not in {"cn", "us"}:
            raise ValueError(f"market must be 'cn' or 'us', got {self.market!r}")
        if not self.factors:
            raise ValueError("a hypothesis needs at least one factor")
        if len(self.factors) > MAX_FACTORS:
            raise ValueError(f"at most {MAX_FACTORS} factors allowed (parsimony cap), got {len(self.factors)}")
        if self.combination != "linear_zscore":
            raise ValueError(f"combination must be 'linear_zscore', got {self.combination!r}")


@dataclass
class FactorConfig:
    weights: Dict[str, float]
    top_n: int
    rebalance_days: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hypothesis.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/hypothesis.py tests/test_hypothesis.py
git commit -m "feat: add factor hypothesis and hyperparameter dataclasses"
```

---

### Task 2: Linear composite factor scoring

**Files:**
- Create: `src/quant_agent_team/factor_scoring.py`
- Test: `tests/test_factor_scoring.py`

**Interfaces:**
- Consumes: `FactorDef` from Task 1.
- Produces:
  - `composite_scores(frame: pd.DataFrame, factors: list[FactorDef], weights: dict[str, float], sector_neutral: bool = False, sector_column: str = "sector_name") -> pd.DataFrame` — operates on rows for a single trade date; returns a copy with a `composite_score` column (cross-sectional z-score per factor, sign-adjusted by direction, weighted sum).
  - `select_top_n(scored: pd.DataFrame, top_n: int) -> pd.DataFrame` — top rows by `composite_score` descending.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_factor_scoring.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.factor_scoring import composite_scores, select_top_n
from quant_agent_team.hypothesis import FactorDef


class FactorScoringTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "stock_code": ["A", "B", "C"],
                "momentum_20d": [0.10, 0.00, -0.10],
                "volatility_20d": [0.30, 0.20, 0.10],
            }
        )

    def test_long_high_factor_ranks_higher_value_first(self) -> None:
        factors = [FactorDef("momentum_20d", "momentum_20d", "long_high")]
        scored = composite_scores(self._frame(), factors, {"momentum_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "A")

    def test_long_low_factor_inverts_ranking(self) -> None:
        factors = [FactorDef("volatility_20d", "volatility_20d", "long_low")]
        scored = composite_scores(self._frame(), factors, {"volatility_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "C")  # lowest volatility wins

    def test_zero_variance_factor_contributes_zero(self) -> None:
        frame = pd.DataFrame({"stock_code": ["A", "B"], "f": [5.0, 5.0]})
        factors = [FactorDef("f", "f", "long_high")]
        scored = composite_scores(frame, factors, {"f": 1.0})
        self.assertEqual(scored["composite_score"].tolist(), [0.0, 0.0])

    def test_weights_combine_multiple_factors(self) -> None:
        factors = [
            FactorDef("momentum_20d", "momentum_20d", "long_high"),
            FactorDef("volatility_20d", "volatility_20d", "long_low"),
        ]
        scored = composite_scores(self._frame(), factors, {"momentum_20d": 1.0, "volatility_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "C")  # high mom OR low vol; C wins on vol


if __name__ == "__main__":
    unittest.main()
```

Note on the last assertion: A has momentum z = +1.2247, vol z = +1.2247 → long_low contributes −1.2247 → composite 0.0. C has momentum z = −1.2247, vol z = −1.2247 → long_low contributes +1.2247 → composite 0.0. B is 0.0 on both. All three tie at 0.0; `sort_values` is stable so the first row (A) would win — adjust the test to a non-tying case.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_factor_scoring.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.factor_scoring'`

- [ ] **Step 3: Fix the tying test case, then write minimal implementation**

Replace `test_weights_combine_multiple_factors` with a non-degenerate case:

```python
    def test_weights_combine_multiple_factors(self) -> None:
        frame = pd.DataFrame(
            {
                "stock_code": ["A", "B", "C"],
                "momentum_20d": [0.20, 0.00, -0.05],
                "volatility_20d": [0.10, 0.20, 0.30],
            }
        )
        factors = [
            FactorDef("momentum_20d", "momentum_20d", "long_high"),
            FactorDef("volatility_20d", "volatility_20d", "long_low"),
        ]
        scored = composite_scores(frame, factors, {"momentum_20d": 1.0, "volatility_20d": 1.0})
        top = select_top_n(scored, 1)
        self.assertEqual(top.iloc[0]["stock_code"], "A")  # high momentum and low volatility
```

```python
# src/quant_agent_team/factor_scoring.py
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .hypothesis import FactorDef


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=series.index)
    return (numeric - numeric.mean()) / std


def composite_scores(
    frame: pd.DataFrame,
    factors: List[FactorDef],
    weights: Dict[str, float],
    sector_neutral: bool = False,
    sector_column: str = "sector_name",
) -> pd.DataFrame:
    frame = frame.copy()
    total = pd.Series(0.0, index=frame.index)
    for factor in factors:
        column = frame[factor.source_field]
        if sector_neutral and sector_column in frame.columns:
            z = column.groupby(frame[sector_column]).transform(_zscore)
        else:
            z = _zscore(column)
        sign = 1.0 if factor.direction == "long_high" else -1.0
        weight = weights.get(factor.name, 0.0)
        total = total + weight * sign * z.fillna(0.0)
    frame["composite_score"] = total
    return frame


def select_top_n(scored: pd.DataFrame, top_n: int) -> pd.DataFrame:
    return scored.sort_values("composite_score", ascending=False).head(top_n)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_factor_scoring.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/factor_scoring.py tests/test_factor_scoring.py
git commit -m "feat: add linear composite z-score factor scoring"
```

---

### Task 3: Periodic-rebalance factor backtest

**Files:**
- Create: `src/quant_agent_team/factor_backtest.py`
- Test: `tests/test_factor_backtest.py`

**Interfaces:**
- Consumes: `FactorHypothesis`, `FactorConfig` (Task 1); `composite_scores`, `select_top_n` (Task 2); `CostModel` (Phase 1); `BacktestResult` (Phase 1).
- Produces: `run_factor_backtest(frame: pd.DataFrame, hypothesis: FactorHypothesis, config: FactorConfig, cost_model: CostModel | None = None, initial_capital: float = 1_000_000.0) -> BacktestResult`. `frame` columns: `stock_code`, `trade_date` (datetime), `close_price_adj`, the factor source columns, optional `sector_name`. Rebalances every `config.rebalance_days` trading dates: at each rebalance date, score cross-sectionally, pick top-N, equal-weight allocate, hold to next rebalance date, liquidate, recompound. Costs applied on entry and exit. Returns a fully-populated `BacktestResult`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_factor_backtest.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.factor_backtest import run_factor_backtest
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


def _trending_frame() -> pd.DataFrame:
    # Two stocks over 5 dates. "UP" rises, "DN" falls. momentum_20d encodes the trend.
    rows = []
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
    up_prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    dn_prices = [10.0, 9.0, 8.0, 7.0, 6.0]
    for d, pu, pd_ in zip(dates, up_prices, dn_prices):
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": pu, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": pd_, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


def _hypothesis() -> FactorHypothesis:
    return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


class FactorBacktestTest(unittest.TestCase):
    def test_picks_uptrending_stock_and_makes_money_frictionless(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_factor_backtest(_trending_frame(), _hypothesis(), config, cost_model=CostModel(0.0, 0.0))
        self.assertGreater(result.total_return, 0.0)
        self.assertGreater(result.trade_count, 0)

    def test_costs_reduce_return(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        frictionless = run_factor_backtest(_trending_frame(), _hypothesis(), config, cost_model=CostModel(0.0, 0.0))
        with_costs = run_factor_backtest(_trending_frame(), _hypothesis(), config)
        self.assertLess(with_costs.total_return, frictionless.total_return)

    def test_drawdown_is_non_negative_fraction(self) -> None:
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_factor_backtest(_trending_frame(), _hypothesis(), config, cost_model=CostModel(0.0, 0.0))
        self.assertGreaterEqual(result.max_drawdown, 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_factor_backtest.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.factor_backtest'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/factor_backtest.py
from __future__ import annotations

import math
from datetime import datetime
from typing import List

import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_scoring import composite_scores, select_top_n
from .hypothesis import FactorConfig, FactorHypothesis


def _rebalance_dates(dates: List[pd.Timestamp], step: int) -> List[pd.Timestamp]:
    if step < 1:
        step = 1
    return list(dates[::step])


def run_factor_backtest(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    cost_model: CostModel | None = None,
    initial_capital: float = 1_000_000.0,
) -> BacktestResult:
    costs = cost_model if cost_model is not None else CostModel()
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    all_dates = sorted(frame["trade_date"].unique())
    rebalance_dates = _rebalance_dates(all_dates, config.rebalance_days)

    equity = initial_capital
    equity_points = [{"trade_date": all_dates[0], "equity": equity}]
    trade_count = 0
    period_returns: List[float] = []

    for i in range(len(rebalance_dates) - 1):
        entry_date = rebalance_dates[i]
        exit_date = rebalance_dates[i + 1]
        entry_rows = frame.loc[frame["trade_date"] == entry_date]
        scored = composite_scores(
            entry_rows, hypothesis.factors, config.weights, sector_neutral=hypothesis.sector_neutral
        )
        picks = select_top_n(scored, config.top_n)
        if picks.empty:
            equity_points.append({"trade_date": exit_date, "equity": equity})
            continue

        slot_capital = equity / len(picks)
        period_equity = 0.0
        for _, pick in picks.iterrows():
            code = pick["stock_code"]
            entry_price = float(pick["close_price_adj"])
            exit_row = frame.loc[(frame["trade_date"] == exit_date) & (frame["stock_code"] == code)]
            if exit_row.empty or entry_price <= 0:
                period_equity += slot_capital
                continue
            raw_exit_price = float(exit_row.iloc[0]["close_price_adj"])
            fill_entry = costs.entry_fill_price(entry_price)
            fill_exit = costs.exit_fill_price(raw_exit_price)
            shares = (slot_capital - costs.commission(slot_capital)) / fill_entry
            proceeds = shares * fill_exit
            proceeds -= costs.commission(proceeds)
            period_equity += proceeds
            trade_count += 1
        period_returns.append((period_equity / equity) - 1.0 if equity else 0.0)
        equity = period_equity
        equity_points.append({"trade_date": exit_date, "equity": equity})

    equity_df = pd.DataFrame(equity_points).sort_values("trade_date").reset_index(drop=True)
    equity_df["cummax"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = equity_df["equity"] / equity_df["cummax"] - 1.0
    equity_df["ret"] = equity_df["equity"].pct_change().fillna(0.0)

    total_return = (equity / initial_capital) - 1.0
    num_days = max(len(all_dates), 1)
    annualized_return = (equity / initial_capital) ** (252 / num_days) - 1.0
    std = float(equity_df["ret"].std(ddof=0))
    sharpe = 0.0 if std == 0 else float(equity_df["ret"].mean() / std * math.sqrt(252))
    win_rate = 0.0 if not period_returns else float(sum(r > 0 for r in period_returns) / len(period_returns))

    return BacktestResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        spec_id=f"factor-{hypothesis.market}",
        strategy_id=f"factor-{hypothesis.market}",
        start_date=pd.Timestamp(all_dates[0]).strftime("%Y-%m-%d"),
        end_date=pd.Timestamp(all_dates[-1]).strftime("%Y-%m-%d"),
        trade_count=trade_count,
        trade_win_rate=win_rate,
        annualized_return=float(annualized_return),
        total_return=float(total_return),
        max_drawdown=float(abs(equity_df["drawdown"].min())),
        sharpe=sharpe,
        average_holding_days=float(config.rebalance_days),
        equity_curve_points=len(equity_df),
        notes=["Linear composite factor model with periodic rebalance and transaction costs."],
        trades=[],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_factor_backtest.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/factor_backtest.py tests/test_factor_backtest.py
git commit -m "feat: add periodic-rebalance factor backtest with costs"
```

---

### Task 4: Walk-forward CV objective

**Files:**
- Create: `src/quant_agent_team/hpo.py`
- Test: `tests/test_hpo_objective.py`

**Interfaces:**
- Consumes: `purged_walk_forward`, `Fold` (Phase 1); `run_factor_backtest` (Task 3); `FactorHypothesis`, `FactorConfig` (Task 1); `CostModel` (Phase 1).
- Produces: `walk_forward_objective(frame, hypothesis, config, n_folds=3, embargo=1, max_drawdown_limit=0.30, min_trade_count=1, cost_model=None) -> float`. Runs `run_factor_backtest` on each fold's **test** dates (out-of-sample), averages annualized return net of costs; returns a large negative penalty if any fold breaches the drawdown limit or the aggregate trade count is below `min_trade_count`. Higher is better (Optuna maximizes).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hpo_objective.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.hpo import PENALTY, walk_forward_objective
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


def _frame(n_dates: int = 12) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class HpoObjectiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        self.config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)

    def test_positive_score_for_profitable_oos(self) -> None:
        score = walk_forward_objective(_frame(), self.hyp, self.config, n_folds=3, cost_model=CostModel(0.0, 0.0))
        self.assertGreater(score, 0.0)

    def test_penalty_when_min_trade_count_not_met(self) -> None:
        score = walk_forward_objective(
            _frame(), self.hyp, self.config, n_folds=3, min_trade_count=10_000, cost_model=CostModel(0.0, 0.0)
        )
        self.assertEqual(score, PENALTY)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hpo_objective.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.hpo'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/hpo.py
from __future__ import annotations

from typing import List

import pandas as pd

from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .hypothesis import FactorConfig, FactorHypothesis
from .walk_forward import purged_walk_forward

PENALTY = -1.0e9


def walk_forward_objective(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    n_folds: int = 3,
    embargo: int = 1,
    max_drawdown_limit: float = 0.30,
    min_trade_count: int = 1,
    cost_model: CostModel | None = None,
) -> float:
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    all_dates = sorted(d.date() for d in frame["trade_date"].unique())
    folds = purged_walk_forward(all_dates, n_folds=n_folds, embargo=embargo)
    if not folds:
        return PENALTY

    oos_returns: List[float] = []
    total_trades = 0
    for fold in folds:
        test_set = {pd.Timestamp(d) for d in fold.test}
        test_frame = frame.loc[frame["trade_date"].isin(test_set)]
        if test_frame.empty:
            continue
        result = run_factor_backtest(test_frame, hypothesis, config, cost_model=cost_model)
        if result.max_drawdown > max_drawdown_limit:
            return PENALTY
        oos_returns.append(result.annualized_return)
        total_trades += result.trade_count

    if not oos_returns or total_trades < min_trade_count:
        return PENALTY
    return float(sum(oos_returns) / len(oos_returns))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hpo_objective.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/hpo.py tests/test_hpo_objective.py
git commit -m "feat: add purged walk-forward CV objective for HPO"
```

---

### Task 5: Optuna hyperparameter search

**Files:**
- Modify: `src/quant_agent_team/hpo.py`
- Modify: `pyproject.toml` (add `optuna` dependency)
- Test: `tests/test_hpo_optimize.py`

**Interfaces:**
- Consumes: `walk_forward_objective` (Task 4); `FactorHypothesis`, `FactorConfig` (Task 1).
- Produces:
  - `HyperParamSpace(top_n_choices: list[int], rebalance_days_choices: list[int], weight_low: float = 0.0, weight_high: float = 1.0)`.
  - `HpoResult(best_config: FactorConfig, best_score: float, n_trials: int)`.
  - `optimize(frame, hypothesis, space, n_trials=20, seed=0, n_folds=3, cost_model=None) -> HpoResult` — uses Optuna (TPE sampler, fixed seed) to sample one weight per factor plus `top_n`/`rebalance_days`, maximizes `walk_forward_objective`, returns the best `FactorConfig` and the total trial count.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hpo_optimize.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.hpo import HyperParamSpace, optimize
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis


def _frame(n_dates: int = 16) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class HpoOptimizeTest(unittest.TestCase):
    def test_optimize_returns_config_within_space_and_tracks_trials(self) -> None:
        hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])
        result = optimize(_frame(), hyp, space, n_trials=5, seed=0, n_folds=3, cost_model=CostModel(0.0, 0.0))
        self.assertEqual(result.n_trials, 5)
        self.assertIn(result.best_config.top_n, [1])
        self.assertIn(result.best_config.rebalance_days, [1, 2])
        self.assertIn("momentum_20d", result.best_config.weights)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hpo_optimize.py -q`
Expected: FAIL with `ImportError: cannot import name 'HyperParamSpace'` (and `optuna` may be missing)

- [ ] **Step 3: Install optuna, declare it, then implement**

```bash
python -m pip install optuna
```

In `pyproject.toml`, add `"optuna"` to the `dependencies` list (after `"pycryptodome",`).

Append to `src/quant_agent_team/hpo.py`:

```python
from dataclasses import dataclass, field
from typing import Dict

import optuna


@dataclass
class HyperParamSpace:
    top_n_choices: list
    rebalance_days_choices: list
    weight_low: float = 0.0
    weight_high: float = 1.0


@dataclass
class HpoResult:
    best_config: FactorConfig
    best_score: float
    n_trials: int


def optimize(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    n_trials: int = 20,
    seed: int = 0,
    n_folds: int = 3,
    cost_model: CostModel | None = None,
) -> HpoResult:
    def _suggest(trial: "optuna.Trial") -> FactorConfig:
        weights: Dict[str, float] = {
            factor.name: trial.suggest_float(f"w_{factor.name}", space.weight_low, space.weight_high)
            for factor in hypothesis.factors
        }
        top_n = trial.suggest_categorical("top_n", space.top_n_choices)
        rebalance_days = trial.suggest_categorical("rebalance_days", space.rebalance_days_choices)
        return FactorConfig(weights=weights, top_n=top_n, rebalance_days=rebalance_days)

    def _objective(trial: "optuna.Trial") -> float:
        config = _suggest(trial)
        return walk_forward_objective(
            frame, hypothesis, config, n_folds=n_folds, cost_model=cost_model
        )

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(_objective, n_trials=n_trials)

    best = study.best_trial
    weights = {factor.name: best.params[f"w_{factor.name}"] for factor in hypothesis.factors}
    best_config = FactorConfig(
        weights=weights, top_n=best.params["top_n"], rebalance_days=best.params["rebalance_days"]
    )
    return HpoResult(best_config=best_config, best_score=float(best.value), n_trials=len(study.trials))
```

Note: move the `from dataclasses import dataclass, field` / `from typing import Dict` imports to the top of the file with the other imports rather than mid-file; shown here inline only to indicate what's needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hpo_optimize.py -q`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/hpo.py tests/test_hpo_optimize.py pyproject.toml
git commit -m "feat: add Optuna hyperparameter search over factor configs"
```

---

### Task 6: End-to-end search-and-evaluate

**Files:**
- Modify: `src/quant_agent_team/hpo.py`
- Test: `tests/test_search_strategy.py`

**Interfaces:**
- Consumes: `optimize`, `HyperParamSpace`, `HpoResult` (Task 5); `run_factor_backtest` (Task 3); `AcceptanceCriteria`, `evaluate_strategy` (Phase 1); `BacktestResult` (Phase 1).
- Produces: `search_strategy(frame, hypothesis, space, criteria: AcceptanceCriteria, n_trials=20, seed=0, n_folds=3, cost_model=None) -> SearchResult`, where `SearchResult(hpo: HpoResult, development_result: BacktestResult, evaluation: EvaluationResult)`. After HPO finds the best config, runs a full-development-window factor backtest with it and applies the Phase 1 acceptance gate. (Holdout is Phase 4.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_search_strategy.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.evaluation import AcceptanceCriteria
from quant_agent_team.hpo import HyperParamSpace, search_strategy
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis


def _frame(n_dates: int = 16) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class SearchStrategyTest(unittest.TestCase):
    def test_search_returns_hpo_result_and_evaluation(self) -> None:
        hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1)
        result = search_strategy(_frame(), hyp, space, criteria, n_trials=5, seed=0, cost_model=CostModel(0.0, 0.0))
        self.assertEqual(result.hpo.n_trials, 5)
        self.assertTrue(result.evaluation.passed)
        self.assertGreater(result.development_result.trade_count, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_search_strategy.py -q`
Expected: FAIL with `ImportError: cannot import name 'search_strategy'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/quant_agent_team/hpo.py` (and add `from .evaluation import AcceptanceCriteria, EvaluationResult, evaluate_strategy` and `from .backtest_runner import BacktestResult` to the top imports):

```python
@dataclass
class SearchResult:
    hpo: HpoResult
    development_result: BacktestResult
    evaluation: EvaluationResult


def search_strategy(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    n_trials: int = 20,
    seed: int = 0,
    n_folds: int = 3,
    cost_model: CostModel | None = None,
) -> SearchResult:
    hpo = optimize(
        frame, hypothesis, space, n_trials=n_trials, seed=seed, n_folds=n_folds, cost_model=cost_model
    )
    development_result = run_factor_backtest(frame, hypothesis, hpo.best_config, cost_model=cost_model)
    evaluation = evaluate_strategy(development_result, criteria)
    return SearchResult(hpo=hpo, development_result=development_result, evaluation=evaluation)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_search_strategy.py -q`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/hpo.py tests/test_search_strategy.py
git commit -m "feat: wire HPO search through to acceptance gate"
```

---

### Task 7: Phase 2 regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all Phase 1 + Phase 2 tests PASS; the 8 PostgreSQL-dependent tests SKIP (no local Postgres). No failures.

- [ ] **Step 2: Commit (if incidental fixes were needed)**

```bash
git add -A
git commit -m "test: confirm Phase 2 suite green"
```

---

## Deferred to later phases

- **Phase 3:** LLM generation outer loop (proposes `FactorHypothesis`), `OverfittingScore`, deflated performance (uses `HpoResult.n_trials`), null test.
- **Phase 4:** `HoldoutVault` (one-shot holdout on `search_strategy`'s best config), `PaperTradeRunner`, US market provider, daily mark-to-market in the factor backtest, sector-neutral data wiring.

## Self-Review

- **Spec coverage:** §5.1 hypothesis/hyperparameters → Task 1; §5.2 linear composite scoring → Task 2; factor backtest with costs (basis for §5.3 on the factor path) → Task 3; §5.4 purged walk-forward CV objective → Task 4; §5.4 Optuna search + trial bookkeeping (`n_trials`) → Task 5; §5.5 acceptance gate wiring → Task 6.
- **Placeholder scan:** every code step is complete and runnable; the one tying-test caveat in Task 2 is resolved in Step 3 before implementation.
- **Type consistency:** `FactorHypothesis`/`FactorDef`/`FactorConfig` field names match across Tasks 1–6; `composite_scores`/`select_top_n` signatures match between Task 2 and Task 3; `run_factor_backtest(frame, hypothesis, config, cost_model=...)` matches across Tasks 3, 4, 6; `walk_forward_objective(...)` matches Task 4 and Task 5; `HyperParamSpace`/`HpoResult`/`optimize`/`search_strategy`/`SearchResult` names match across Tasks 5–6; `AcceptanceCriteria`/`evaluate_strategy`/`BacktestResult` reused from Phase 1 with their existing signatures.
- **Import note:** Task 5 and Task 6 add imports (`dataclass`, `field`, `Dict`, `optuna`, `evaluation` symbols, `BacktestResult`) that should be consolidated at the top of `hpo.py` during implementation rather than mid-file.
