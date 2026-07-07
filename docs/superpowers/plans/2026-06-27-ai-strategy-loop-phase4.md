# AI Strategy Loop — Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop — a one-shot locked-holdout vault, a forward paper-trade runner that emits the actionable signal, a US-equity price/volume provider, and a top-level orchestrator that wires refinement → holdout → overfitting score + deflation → null test into one report.

**Architecture:** Pure-Python modules composing Phases 1–3. `HoldoutVault` and `PaperTradeRunner` reuse `factor_backtest` + `factor_scoring`. `USEquityProvider` produces the existing `DailyBar` via an **injectable fetch function** (network/SDK stays out of unit tests). `orchestrator.run_pipeline` is the capstone: split the 3-year window, run the refinement loop on development, evaluate the accepted strategy once on the holdout, score overfitting and deflate the reported return, and run the null test as calibration.

**Tech Stack:** Python ≥3.9, `pandas`, `numpy`, `optuna`, `anthropic` (Phases 1–3), plus **`yfinance`** (new, optional — only when no fetch is injected). `unittest` via `pytest`.

**Source spec:** [`docs/superpowers/specs/2026-06-27-ai-strategy-generation-loop-design.md`](../specs/2026-06-27-ai-strategy-generation-loop-design.md) §5.6 (holdout vault, paper-trade), §5.7 (US provider), §3–4 (orchestration), §5.5 (scoring wired in).

**Builds on Phases 1–3:** `from .walk_forward import split_three_year_window`; `from .factor_backtest import run_factor_backtest`; `from .factor_scoring import composite_scores, select_top_n`; `from .backtest_runner import BacktestResult`; `from .cost_model import CostModel`; `from .hypothesis import FactorHypothesis, FactorConfig`; `from .hpo import HyperParamSpace, search_strategy`; `from .refinement import run_refinement, RefinementResult, HypothesisProposer`; `from .overfitting import OverfittingInputs, overfitting_score, deflate_return`; `from .null_test import run_null_test`; `from .evaluation import AcceptanceCriteria`; `from .market_fetch import DailyBar`.

## Global Constraints

- Python ≥ 3.9; new dependency `yfinance` declared as optional (`us` extra), lazy-imported only when no fetch is injected.
- The holdout is **one-shot per strategy**: a second evaluation of the same strategy id raises (spec §5.6). Touch count is tracked; exceeding the budget flags `degraded=True`.
- Costs always applied via `CostModel` (Phase 1 non-zero default) on every backtest/holdout/paper-trade run.
- No reported number without its overfitting score and deflated value — the orchestrator report carries both (spec §2, §5.5).
- US data is **price/volume only** (spec §1.4); `turnover` is a `close × volume` dollar-volume proxy (US feeds don't provide turnover).
- Tests use `unittest.TestCase` with the standard `src` path shim; commit after each task.

---

### Task 1: One-shot holdout vault

**Files:**
- Create: `src/quant_agent_team/holdout.py`
- Test: `tests/test_holdout.py`

**Interfaces:**
- Consumes: `run_factor_backtest` (Phase 2); `FactorHypothesis`, `FactorConfig` (Phase 2); `CostModel`, `BacktestResult` (Phase 1).
- Produces:
  - `HoldoutAlreadyUsedError(Exception)`.
  - `HoldoutResult(strategy_id: str, backtest: BacktestResult, touches: int, degraded: bool)`.
  - `HoldoutVault(holdout_start, holdout_end, touch_budget: int = 20, cost_model: CostModel | None = None)` with `evaluate(strategy_id: str, frame, hypothesis, config) -> HoldoutResult`. Slices `frame` to `[holdout_start, holdout_end]`, runs the factor backtest once, and refuses a repeat evaluation of the same `strategy_id`. `degraded` becomes `True` once cumulative touches exceed `touch_budget`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_holdout.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.holdout import HoldoutAlreadyUsedError, HoldoutVault
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range("2025-06-28", periods=20)  # all inside the holdout window below
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


def _hyp() -> FactorHypothesis:
    return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


def _config() -> FactorConfig:
    return FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)


class HoldoutVaultTest(unittest.TestCase):
    def test_evaluate_returns_result_and_increments_touches(self) -> None:
        vault = HoldoutVault("2025-06-28", "2026-06-27", cost_model=CostModel(0.0, 0.0))
        result = vault.evaluate("s1", _frame(), _hyp(), _config())
        self.assertEqual(result.strategy_id, "s1")
        self.assertEqual(result.touches, 1)
        self.assertGreater(result.backtest.trade_count, 0)
        self.assertFalse(result.degraded)

    def test_second_evaluation_of_same_strategy_raises(self) -> None:
        vault = HoldoutVault("2025-06-28", "2026-06-27", cost_model=CostModel(0.0, 0.0))
        vault.evaluate("s1", _frame(), _hyp(), _config())
        with self.assertRaises(HoldoutAlreadyUsedError):
            vault.evaluate("s1", _frame(), _hyp(), _config())

    def test_degraded_flag_after_budget_exceeded(self) -> None:
        vault = HoldoutVault("2025-06-28", "2026-06-27", touch_budget=1, cost_model=CostModel(0.0, 0.0))
        first = vault.evaluate("s1", _frame(), _hyp(), _config())
        second = vault.evaluate("s2", _frame(), _hyp(), _config())
        self.assertFalse(first.degraded)
        self.assertTrue(second.degraded)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_holdout.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.holdout'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/holdout.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Set

import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .hypothesis import FactorConfig, FactorHypothesis


class HoldoutAlreadyUsedError(Exception):
    """Raised when a strategy is evaluated against the holdout more than once."""


@dataclass
class HoldoutResult:
    strategy_id: str
    backtest: BacktestResult
    touches: int
    degraded: bool


class HoldoutVault:
    def __init__(
        self,
        holdout_start,
        holdout_end,
        touch_budget: int = 20,
        cost_model: CostModel | None = None,
    ) -> None:
        self._start = pd.Timestamp(holdout_start)
        self._end = pd.Timestamp(holdout_end)
        self._touch_budget = touch_budget
        self._cost_model = cost_model
        self._used: Set[str] = set()
        self._touches = 0

    def evaluate(
        self,
        strategy_id: str,
        frame: pd.DataFrame,
        hypothesis: FactorHypothesis,
        config: FactorConfig,
    ) -> HoldoutResult:
        if strategy_id in self._used:
            raise HoldoutAlreadyUsedError(
                f"strategy {strategy_id!r} has already consumed its one-shot holdout evaluation"
            )
        self._used.add(strategy_id)
        self._touches += 1

        frame = frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        window = frame.loc[(frame["trade_date"] >= self._start) & (frame["trade_date"] <= self._end)]
        backtest = run_factor_backtest(window, hypothesis, config, cost_model=self._cost_model)
        return HoldoutResult(
            strategy_id=strategy_id,
            backtest=backtest,
            touches=self._touches,
            degraded=self._touches > self._touch_budget,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_holdout.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/holdout.py tests/test_holdout.py
git commit -m "feat: add one-shot holdout vault"
```

---

### Task 2: Forward paper-trade runner

**Files:**
- Create: `src/quant_agent_team/paper_trade.py`
- Test: `tests/test_paper_trade.py`

**Interfaces:**
- Consumes: `run_factor_backtest` (Phase 2); `composite_scores`, `select_top_n` (Phase 2); `FactorHypothesis`, `FactorConfig` (Phase 2); `CostModel`, `BacktestResult` (Phase 1).
- Produces:
  - `PaperTradeResult(backtest: BacktestResult, latest_signal: list[str])`.
  - `run_paper_trade(frame, hypothesis, config, cost_model=None) -> PaperTradeResult`. Runs the factor backtest over the forward `frame` and computes the actionable signal: the top-N stock codes by composite score on the most recent date.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paper_trade.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.cost_model import CostModel
from quant_agent_team.hypothesis import FactorConfig, FactorDef, FactorHypothesis
from quant_agent_team.paper_trade import run_paper_trade


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=10)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.02
        dn *= 0.98
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class PaperTradeTest(unittest.TestCase):
    def test_latest_signal_picks_top_factor_and_runs_backtest(self) -> None:
        hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        config = FactorConfig(weights={"momentum_20d": 1.0}, top_n=1, rebalance_days=1)
        result = run_paper_trade(_frame(), hyp, config, cost_model=CostModel(0.0, 0.0))
        self.assertEqual(result.latest_signal, ["UP"])
        self.assertGreater(result.backtest.trade_count, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_paper_trade.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.paper_trade'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/paper_trade.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from .backtest_runner import BacktestResult
from .cost_model import CostModel
from .factor_backtest import run_factor_backtest
from .factor_scoring import composite_scores, select_top_n
from .hypothesis import FactorConfig, FactorHypothesis


@dataclass
class PaperTradeResult:
    backtest: BacktestResult
    latest_signal: List[str]


def run_paper_trade(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    config: FactorConfig,
    cost_model: CostModel | None = None,
) -> PaperTradeResult:
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    backtest = run_factor_backtest(frame, hypothesis, config, cost_model=cost_model)

    last_date = frame["trade_date"].max()
    last_rows = frame.loc[frame["trade_date"] == last_date]
    scored = composite_scores(
        last_rows, hypothesis.factors, config.weights, sector_neutral=hypothesis.sector_neutral
    )
    picks = select_top_n(scored, config.top_n)
    latest_signal = [str(code) for code in picks["stock_code"].tolist()]
    return PaperTradeResult(backtest=backtest, latest_signal=latest_signal)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_paper_trade.py -q`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/paper_trade.py tests/test_paper_trade.py
git commit -m "feat: add forward paper-trade runner with latest signal"
```

---

### Task 3: US equity price/volume provider

**Files:**
- Create: `src/quant_agent_team/us_market.py`
- Modify: `pyproject.toml` (add `us` optional extra)
- Test: `tests/test_us_market.py`

**Interfaces:**
- Consumes: `DailyBar` (from `market_fetch`).
- Produces:
  - `normalize_us_bars(symbol: str, rows: list[dict]) -> list[DailyBar]` — maps yfinance-style rows (`date`, `open`, `high`, `low`, `close`, `volume`) to `DailyBar`, with `turnover = close * volume` (dollar-volume proxy).
  - `USEquityProvider(fetch=None, name="us_yfinance")` with `fetch_daily_bars(stock_code, start_date=None, end_date=None) -> list[DailyBar]`. When `fetch` is `None`, yfinance is lazy-imported.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_us_market.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.us_market import USEquityProvider, normalize_us_bars


class UsMarketTest(unittest.TestCase):
    def test_normalize_builds_dailybar_with_turnover_proxy(self) -> None:
        rows = [{"date": "2026-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 1000.0}]
        bars = normalize_us_bars("AAPL", rows)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].stock_code, "AAPL")
        self.assertEqual(bars[0].trade_date, "2026-01-02")
        self.assertEqual(bars[0].close_price, 104.0)
        self.assertEqual(bars[0].turnover, 104.0 * 1000.0)

    def test_provider_uses_injected_fetch(self) -> None:
        captured = {}

        def fake_fetch(symbol, start, end):
            captured["args"] = (symbol, start, end)
            return [{"date": "2026-01-02", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0}]

        provider = USEquityProvider(fetch=fake_fetch)
        bars = provider.fetch_daily_bars("MSFT", start_date="2026-01-01", end_date="2026-01-31")
        self.assertEqual(provider.name, "us_yfinance")
        self.assertEqual(captured["args"], ("MSFT", "2026-01-01", "2026-01-31"))
        self.assertEqual(bars[0].stock_code, "MSFT")
        self.assertEqual(bars[0].turnover, 1.5 * 10.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_us_market.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.us_market'`

- [ ] **Step 3: Implement and declare the optional dependency**

In `pyproject.toml`, under `[project.optional-dependencies]`, add a `us` extra:

```toml
[project.optional-dependencies]
test = ["pytest"]
llm = ["anthropic"]
us = ["yfinance"]
```

```python
# src/quant_agent_team/us_market.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from .market_fetch import DailyBar


def normalize_us_bars(symbol: str, rows: List[dict]) -> List[DailyBar]:
    bars: List[DailyBar] = []
    for row in rows:
        close = float(row["close"])
        volume = float(row["volume"])
        bars.append(
            DailyBar(
                stock_code=symbol,
                trade_date=str(row["date"]),
                close_price=close,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                volume=volume,
                turnover=close * volume,  # US feeds lack turnover; dollar-volume proxy
            )
        )
    return bars


@dataclass
class USEquityProvider:
    fetch: Optional[Callable[[str, Optional[str], Optional[str]], List[dict]]] = None
    name: str = "us_yfinance"

    def _run_fetch(self, symbol: str, start: Optional[str], end: Optional[str]) -> List[dict]:
        if self.fetch is not None:
            return self.fetch(symbol, start, end)
        import yfinance  # lazy import; only needed for live fetches

        data = yfinance.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
        rows: List[dict] = []
        for index, record in data.iterrows():
            rows.append(
                {
                    "date": index.strftime("%Y-%m-%d"),
                    "open": record["Open"],
                    "high": record["High"],
                    "low": record["Low"],
                    "close": record["Close"],
                    "volume": record["Volume"],
                }
            )
        return rows

    def fetch_daily_bars(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[DailyBar]:
        rows = self._run_fetch(stock_code, start_date, end_date)
        return normalize_us_bars(stock_code, rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_us_market.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/us_market.py tests/test_us_market.py pyproject.toml
git commit -m "feat: add US equity price/volume provider (injectable fetch)"
```

---

### Task 4: End-to-end orchestrator

**Files:**
- Create: `src/quant_agent_team/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `split_three_year_window` (Phase 1); `run_refinement`, `RefinementResult`, `HypothesisProposer` (Phase 3); `HoldoutVault`, `HoldoutResult` (Task 1); `OverfittingInputs`, `overfitting_score`, `deflate_return`, `run_null_test` (Phase 3); `HyperParamSpace` (Phase 2); `AcceptanceCriteria`, `CostModel` (Phase 1).
- Produces:
  - `OrchestratorReport(refinement: RefinementResult, holdout: HoldoutResult | None, overfitting: float | None, deflated_holdout_return: float | None, null_pass_rate: float | None)`.
  - `run_pipeline(frame, proposer, space, criteria, market, return_target, available_factors, end_date, max_iterations=10, n_trials=20, seed=0, cost_model=None, run_null=True, null_runs=3) -> OrchestratorReport`. Splits the 3-year window at `end_date`; runs refinement on the development slice; if a strategy is accepted, evaluates it once on the holdout slice, computes the overfitting score (with dev-vs-holdout degradation) and the deflated holdout return, and runs the null test on the development slice. If nothing is accepted, returns a report with `holdout`/scores `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrator.py
from datetime import date
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
from quant_agent_team.hpo import HyperParamSpace
from quant_agent_team.hypothesis import FactorDef, FactorHypothesis
from quant_agent_team.orchestrator import run_pipeline
from quant_agent_team.refinement import ProposalContext


class _FixedProposer:
    def propose(self, context: ProposalContext) -> FactorHypothesis:
        return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


def _three_year_frame(end: date) -> pd.DataFrame:
    start = date(end.year - 3, end.month, 1)
    dates = pd.bdate_range(start, end)
    rows = []
    up = 10.0
    dn = 10.0
    for d in dates:
        up *= 1.01
        dn *= 0.99
        rows.append({"stock_code": "UP", "trade_date": d, "close_price_adj": up, "momentum_20d": 0.10})
        rows.append({"stock_code": "DN", "trade_date": d, "close_price_adj": dn, "momentum_20d": -0.10})
    return pd.DataFrame(rows)


class OrchestratorTest(unittest.TestCase):
    def test_full_pipeline_accepts_and_scores(self) -> None:
        end = date(2026, 6, 27)
        report = run_pipeline(
            _three_year_frame(end), _FixedProposer(),
            HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[5]),
            AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1),
            market="cn", return_target=0.0, available_factors=["momentum_20d"],
            end_date=end, max_iterations=2, n_trials=3, null_runs=2, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(report.refinement.stopped_reason, "accepted")
        self.assertIsNotNone(report.holdout)
        self.assertGreaterEqual(report.overfitting, 0.0)
        self.assertLessEqual(report.overfitting, 1.0)
        self.assertIsNotNone(report.deflated_holdout_return)
        self.assertGreaterEqual(report.null_pass_rate, 0.0)
        self.assertLessEqual(report.null_pass_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.orchestrator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/orchestrator.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import pandas as pd

from .cost_model import CostModel
from .evaluation import AcceptanceCriteria
from .holdout import HoldoutResult, HoldoutVault
from .hpo import HyperParamSpace
from .null_test import run_null_test
from .overfitting import OverfittingInputs, deflate_return, overfitting_score
from .refinement import HypothesisProposer, RefinementResult, run_refinement
from .walk_forward import split_three_year_window


@dataclass
class OrchestratorReport:
    refinement: RefinementResult
    holdout: Optional[HoldoutResult]
    overfitting: Optional[float]
    deflated_holdout_return: Optional[float]
    null_pass_rate: Optional[float]


def run_pipeline(
    frame: pd.DataFrame,
    proposer: HypothesisProposer,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    market: str,
    return_target: float,
    available_factors: List[str],
    end_date: date,
    max_iterations: int = 10,
    n_trials: int = 20,
    seed: int = 0,
    cost_model: CostModel | None = None,
    run_null: bool = True,
    null_runs: int = 3,
) -> OrchestratorReport:
    split = split_three_year_window(end_date)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    dev_start = pd.Timestamp(split.development_start)
    dev_end = pd.Timestamp(split.development_end)
    development = frame.loc[(frame["trade_date"] >= dev_start) & (frame["trade_date"] <= dev_end)]

    refinement = run_refinement(
        development, proposer, space, criteria,
        market=market, return_target=return_target, available_factors=available_factors,
        max_iterations=max_iterations, n_trials=n_trials, seed=seed, cost_model=cost_model,
    )
    if refinement.accepted is None:
        return OrchestratorReport(
            refinement=refinement, holdout=None, overfitting=None,
            deflated_holdout_return=None, null_pass_rate=None,
        )

    hypothesis = refinement.iterations[-1].hypothesis
    config = refinement.accepted.hpo.best_config

    vault = HoldoutVault(split.holdout_start, split.holdout_end, cost_model=cost_model)
    holdout = vault.evaluate("accepted", frame, hypothesis, config)

    dev_return = refinement.accepted.development_result.annualized_return
    holdout_return = holdout.backtest.annualized_return
    n_trials_total = refinement.accepted.hpo.n_trials
    overfitting = overfitting_score(
        OverfittingInputs(
            outer_iterations=len(refinement.iterations),
            total_trials=n_trials_total,
            hp_dimensions=len(hypothesis.factors) + 2,
            trade_count=holdout.backtest.trade_count,
            dev_return=dev_return,
            holdout_return=holdout_return,
        )
    )
    deflated = deflate_return(holdout_return, n_trials_total)

    null_pass_rate: Optional[float] = None
    if run_null:
        null_pass_rate = run_null_test(
            development, hypothesis, space, criteria,
            n_runs=null_runs, n_trials=n_trials, cost_model=cost_model,
        ).pass_rate

    return OrchestratorReport(
        refinement=refinement, holdout=holdout, overfitting=overfitting,
        deflated_holdout_return=deflated, null_pass_rate=null_pass_rate,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py -q`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add end-to-end pipeline orchestrator"
```

---

### Task 5: Phase 4 regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all Phase 1–4 tests PASS; the 8 PostgreSQL-dependent tests SKIP. No failures.

- [ ] **Step 2: Commit (if incidental fixes were needed)**

```bash
git add -A
git commit -m "test: confirm Phase 4 suite green"
```

---

## Still deferred (out of scope, integration/data tasks)

- **Point-in-time survivorship-free universe** (data sourcing) — required before any real-data run; not unit-testable in isolation.
- **Live data wiring to PostgreSQL** for the US provider (the `market` column exists; ingestion must write `market='us'`).
- **Daily mark-to-market** in `factor_backtest` (currently rebalance-granularity equity) for finer drawdown.
- **Sector-neutral data**: `composite_scores(sector_neutral=True)` works when a `sector_name` column is present; populating it for US is a data task.
- **CLI / scheduling** surface to invoke `run_pipeline` and the Feishu notification of `latest_signal` (the original architecture's `monitoring`).

## Self-Review

- **Spec coverage:** §5.6 holdout vault → Task 1; §5.6 paper-trade + actionable signal → Task 2; §5.7 US price/volume provider → Task 3; §3–4 orchestration + §5.5 scoring wired → Task 4.
- **Placeholder scan:** every code step is complete and runnable; the yfinance path is lazy-imported and excluded from unit tests via injected fetch.
- **Type consistency:** `HoldoutVault`/`HoldoutResult`/`HoldoutAlreadyUsedError` names match Task 1 and Task 4; `run_paper_trade`/`PaperTradeResult` match Task 2; `normalize_us_bars`/`USEquityProvider` match Task 3; `run_pipeline`/`OrchestratorReport` use `refinement.accepted` (a `SearchResult` with `.hpo.best_config`, `.hpo.n_trials`, `.development_result.annualized_return`) and `refinement.iterations[-1].hypothesis` exactly as Phase 3 defines them; `OverfittingInputs` field names match Phase 3; `DailyBar` constructed with the 8 fields confirmed in `market_fetch.py`.
