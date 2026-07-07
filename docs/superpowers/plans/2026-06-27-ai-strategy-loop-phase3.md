# AI Strategy Loop — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the AI generation outer loop and the honesty instrumentation — an overfitting-risk score, a deflated-performance haircut, a null test on shuffled data, and an LLM-driven refinement loop that proposes factor hypotheses and iterates against the Phase 2 search.

**Architecture:** Pure-Python scoring modules (`overfitting.py`) and a null test (`null_test.py`) that compose the Phase 2 `search_strategy`. The generation loop (`refinement.py`) is built around a `HypothesisProposer` protocol so it is fully testable with a fake proposer; the real `ClaudeHypothesisProposer` (`claude_proposer.py`) wraps the Anthropic SDK with an **injectable client**, so its tests run without the SDK or network. Claude calls use `claude-opus-4-8` with structured JSON output validated against the Phase 1/2 dataclasses.

**Tech Stack:** Python ≥3.9, `pandas`, `numpy`, `optuna` (Phases 1–2), plus **`anthropic`** (new, optional — only needed when no client is injected). `unittest` via `pytest`.

**Source spec:** [`docs/superpowers/specs/2026-06-27-ai-strategy-generation-loop-design.md`](../specs/2026-06-27-ai-strategy-generation-loop-design.md) §5.1 (LLM proposes hypothesis), §5.5 (`OverfittingScore`, deflated performance, null test), and the outer loop in §4.

**Builds on Phase 2:** `from .hypothesis import FactorHypothesis, FactorDef`; `from .hpo import HyperParamSpace, SearchResult, search_strategy`; `from .evaluation import AcceptanceCriteria`.

## Global Constraints

- Python ≥ 3.9; new dependency `anthropic` declared as optional (lazy-imported only when a client isn't injected).
- LLM model id is `claude-opus-4-8` (default; overridable). Read text via `next(b.text for b in resp.content if b.type == "text")`. Reliable JSON via `output_config={"format": {"type": "json_schema", "schema": ...}}`.
- Overfitting score is in `[0, 1]`, higher = riskier; no bare return is reported without it (spec §2, §5.5).
- Deflated performance is monotonic in trial count: more trials → larger haircut (spec §5.4–5.5).
- Outer loop budget defaults to **10 iterations**, then returns `stopped_reason="budget_exhausted"` for the caller to prompt the user (spec §1 decision: prompt to continue after 10).
- Invalid LLM output is rejected and recorded as a consumed iteration, never silently coerced (spec §5.1).
- Tests use `unittest.TestCase` with the standard `src` path shim; commit after each task.

---

### Task 1: Overfitting-risk score

**Files:**
- Create: `src/quant_agent_team/overfitting.py`
- Test: `tests/test_overfitting.py`

**Interfaces:**
- Produces:
  - `OverfittingInputs(outer_iterations: int, total_trials: int, hp_dimensions: int, trade_count: int, dev_return: float | None = None, holdout_return: float | None = None)`.
  - `overfitting_score(inputs: OverfittingInputs) -> float` — returns a value in `[0, 1]`; higher = riskier. Monotone: ↑ in iterations / trials / hp_dimensions / dev-vs-holdout degradation, ↓ in trade_count.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overfitting.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.overfitting import OverfittingInputs, overfitting_score


class OverfittingScoreTest(unittest.TestCase):
    def _base(self, **kw) -> OverfittingInputs:
        params = dict(outer_iterations=1, total_trials=10, hp_dimensions=2, trade_count=100)
        params.update(kw)
        return OverfittingInputs(**params)

    def test_score_in_unit_interval(self) -> None:
        score = overfitting_score(self._base())
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_more_trials_is_riskier(self) -> None:
        low = overfitting_score(self._base(total_trials=10))
        high = overfitting_score(self._base(total_trials=1000))
        self.assertGreater(high, low)

    def test_fewer_trades_is_riskier(self) -> None:
        many = overfitting_score(self._base(trade_count=500))
        few = overfitting_score(self._base(trade_count=5))
        self.assertGreater(few, many)

    def test_degradation_increases_risk(self) -> None:
        none = overfitting_score(self._base())
        degraded = overfitting_score(self._base(dev_return=0.40, holdout_return=0.05))
        self.assertGreater(degraded, none)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_overfitting.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.overfitting'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/overfitting.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OverfittingInputs:
    outer_iterations: int
    total_trials: int
    hp_dimensions: int
    trade_count: int
    dev_return: Optional[float] = None
    holdout_return: Optional[float] = None


def _saturating(x: float, scale: float) -> float:
    # 0 at x=0, approaches 1 as x grows; higher = riskier
    return 1.0 - math.exp(-max(x, 0.0) / scale)


def overfitting_score(inputs: OverfittingInputs) -> float:
    components: List[float] = [
        _saturating(inputs.outer_iterations, 10.0),
        _saturating(inputs.total_trials, 200.0),
        _saturating(inputs.hp_dimensions, 8.0),
        math.exp(-max(inputs.trade_count, 0) / 30.0),  # few trades -> near 1 (risky)
    ]
    if (
        inputs.dev_return is not None
        and inputs.holdout_return is not None
        and inputs.dev_return != 0
    ):
        degradation = (inputs.dev_return - inputs.holdout_return) / abs(inputs.dev_return)
        components.append(min(1.0, max(0.0, degradation)))
    return float(sum(components) / len(components))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_overfitting.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/overfitting.py tests/test_overfitting.py
git commit -m "feat: add overfitting-risk score"
```

---

### Task 2: Deflated performance haircut

**Files:**
- Modify: `src/quant_agent_team/overfitting.py`
- Test: `tests/test_deflation.py`

**Interfaces:**
- Produces: `deflate_return(raw_return: float, n_trials: int) -> float` — shrinks `raw_return` toward zero as `n_trials` grows; `n_trials <= 1` returns `raw_return` unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deflation.py
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.overfitting import deflate_return


class DeflationTest(unittest.TestCase):
    def test_single_trial_is_unchanged(self) -> None:
        self.assertAlmostEqual(deflate_return(0.40, 1), 0.40)

    def test_more_trials_shrinks_more(self) -> None:
        few = deflate_return(0.40, 10)
        many = deflate_return(0.40, 1000)
        self.assertLess(many, few)
        self.assertLess(few, 0.40)

    def test_deflation_preserves_sign(self) -> None:
        self.assertLess(deflate_return(-0.20, 100), 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_deflation.py -q`
Expected: FAIL with `ImportError: cannot import name 'deflate_return'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/quant_agent_team/overfitting.py`:

```python
def deflate_return(raw_return: float, n_trials: int) -> float:
    factor = 1.0 / (1.0 + math.log(max(n_trials, 1)))
    return raw_return * factor
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_deflation.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/overfitting.py tests/test_deflation.py
git commit -m "feat: add trial-count deflation of reported return"
```

---

### Task 3: Null test on shuffled data

**Files:**
- Create: `src/quant_agent_team/null_test.py`
- Test: `tests/test_null_test.py`

**Interfaces:**
- Consumes: `search_strategy`, `HyperParamSpace` (Phase 2); `FactorHypothesis` (Phase 1/2); `AcceptanceCriteria`, `CostModel` (Phase 1).
- Produces: `NullTestResult(n_runs: int, passes: int, pass_rate: float)` and `run_null_test(frame, hypothesis, space, criteria, n_runs=5, base_seed=0, n_trials=10, cost_model=None) -> NullTestResult`. Each run shuffles every factor source column independently (destroying any signal), runs `search_strategy`, and counts how often the acceptance gate passes. A healthy pipeline yields a low pass rate.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_null_test.py
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
from quant_agent_team.null_test import run_null_test


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


class NullTestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hyp = FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])
        self.space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])

    def test_impossible_bar_never_passes_on_noise(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=10.0, max_drawdown_limit=1.0, min_trade_count=1)
        result = run_null_test(
            _frame(), self.hyp, self.space, criteria, n_runs=3, base_seed=0, n_trials=3, cost_model=CostModel(0.0, 0.0)
        )
        self.assertEqual(result.n_runs, 3)
        self.assertEqual(result.passes, 0)
        self.assertEqual(result.pass_rate, 0.0)

    def test_pass_rate_is_consistent_with_counts(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.30, max_drawdown_limit=1.0, min_trade_count=1)
        result = run_null_test(
            _frame(), self.hyp, self.space, criteria, n_runs=4, base_seed=1, n_trials=3, cost_model=CostModel(0.0, 0.0)
        )
        self.assertGreaterEqual(result.pass_rate, 0.0)
        self.assertLessEqual(result.pass_rate, 1.0)
        self.assertAlmostEqual(result.pass_rate, result.passes / result.n_runs)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_null_test.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.null_test'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/null_test.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .cost_model import CostModel
from .evaluation import AcceptanceCriteria
from .hpo import HyperParamSpace, search_strategy
from .hypothesis import FactorHypothesis


@dataclass
class NullTestResult:
    n_runs: int
    passes: int
    pass_rate: float


def _shuffle_factors(frame: pd.DataFrame, hypothesis: FactorHypothesis, rng: np.random.Generator) -> pd.DataFrame:
    shuffled = frame.copy()
    for factor in hypothesis.factors:
        values = shuffled[factor.source_field].to_numpy()
        shuffled[factor.source_field] = rng.permutation(values)
    return shuffled


def run_null_test(
    frame: pd.DataFrame,
    hypothesis: FactorHypothesis,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    n_runs: int = 5,
    base_seed: int = 0,
    n_trials: int = 10,
    cost_model: CostModel | None = None,
) -> NullTestResult:
    passes = 0
    for i in range(n_runs):
        rng = np.random.default_rng(base_seed + i)
        shuffled = _shuffle_factors(frame, hypothesis, rng)
        result = search_strategy(
            shuffled, hypothesis, space, criteria, n_trials=n_trials, seed=base_seed + i, cost_model=cost_model
        )
        if result.evaluation.passed:
            passes += 1
    pass_rate = passes / n_runs if n_runs else 0.0
    return NullTestResult(n_runs=n_runs, passes=passes, pass_rate=pass_rate)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_null_test.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/null_test.py tests/test_null_test.py
git commit -m "feat: add null test on shuffled factor data"
```

---

### Task 4: Hypothesis proposer protocol and refinement loop

**Files:**
- Create: `src/quant_agent_team/refinement.py`
- Test: `tests/test_refinement.py`

**Interfaces:**
- Consumes: `FactorHypothesis` (Phase 1/2); `HyperParamSpace`, `SearchResult`, `search_strategy` (Phase 2); `AcceptanceCriteria`, `CostModel` (Phase 1).
- Produces:
  - `ProposalContext(market: str, return_target: float, available_factors: list[str], history: list[IterationRecord])`.
  - `IterationRecord(hypothesis: FactorHypothesis | None, best_score: float | None, passed: bool, note: str)`.
  - `InvalidHypothesisError(Exception)`.
  - `HypothesisProposer` protocol with `propose(context: ProposalContext) -> FactorHypothesis`.
  - `RefinementResult(accepted: SearchResult | None, iterations: list[IterationRecord], stopped_reason: str)`.
  - `run_refinement(frame, proposer, space, criteria, market, return_target, available_factors, max_iterations=10, n_trials=20, seed=0, cost_model=None) -> RefinementResult`. Loops: propose → `search_strategy` → record; stop early on acceptance (`stopped_reason="accepted"`), else stop at `max_iterations` (`stopped_reason="budget_exhausted"`). A proposer that raises `InvalidHypothesisError` consumes one iteration recorded with `passed=False`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_refinement.py
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
from quant_agent_team.refinement import (
    InvalidHypothesisError,
    ProposalContext,
    run_refinement,
)


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


class _FixedProposer:
    def __init__(self) -> None:
        self.calls = 0

    def propose(self, context: ProposalContext) -> FactorHypothesis:
        self.calls += 1
        return FactorHypothesis(market="cn", factors=[FactorDef("momentum_20d", "momentum_20d", "long_high")])


class _RaisingProposer:
    def propose(self, context: ProposalContext) -> FactorHypothesis:
        raise InvalidHypothesisError("bad output")


class RefinementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.space = HyperParamSpace(top_n_choices=[1], rebalance_days_choices=[1, 2])

    def test_stops_on_acceptance(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1)
        proposer = _FixedProposer()
        result = run_refinement(
            _frame(), proposer, self.space, criteria, market="cn", return_target=0.0,
            available_factors=["momentum_20d"], max_iterations=10, n_trials=5, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(result.stopped_reason, "accepted")
        self.assertEqual(proposer.calls, 1)
        self.assertIsNotNone(result.accepted)

    def test_budget_exhausted_when_never_passing(self) -> None:
        # return-independent impossible gate (the toy UP stock annualizes astronomically high)
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=10_000)
        result = run_refinement(
            _frame(), _FixedProposer(), self.space, criteria, market="cn", return_target=10.0,
            available_factors=["momentum_20d"], max_iterations=3, n_trials=3, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(result.stopped_reason, "budget_exhausted")
        self.assertEqual(len(result.iterations), 3)
        self.assertIsNone(result.accepted)

    def test_invalid_hypothesis_consumes_iteration(self) -> None:
        criteria = AcceptanceCriteria(min_annualized_return=0.0, max_drawdown_limit=1.0, min_trade_count=1)
        result = run_refinement(
            _frame(), _RaisingProposer(), self.space, criteria, market="cn", return_target=0.0,
            available_factors=["momentum_20d"], max_iterations=2, n_trials=3, cost_model=CostModel(0.0, 0.0),
        )
        self.assertEqual(result.stopped_reason, "budget_exhausted")
        self.assertEqual(len(result.iterations), 2)
        self.assertFalse(result.iterations[0].passed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_refinement.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.refinement'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/quant_agent_team/refinement.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

import pandas as pd

from .cost_model import CostModel
from .evaluation import AcceptanceCriteria
from .hpo import HyperParamSpace, SearchResult, search_strategy
from .hypothesis import FactorHypothesis


class InvalidHypothesisError(Exception):
    """Raised by a proposer when its output cannot be parsed/validated."""


@dataclass
class IterationRecord:
    hypothesis: Optional[FactorHypothesis]
    best_score: Optional[float]
    passed: bool
    note: str


@dataclass
class ProposalContext:
    market: str
    return_target: float
    available_factors: List[str]
    history: List[IterationRecord] = field(default_factory=list)


class HypothesisProposer(Protocol):
    def propose(self, context: "ProposalContext") -> FactorHypothesis: ...


@dataclass
class RefinementResult:
    accepted: Optional[SearchResult]
    iterations: List[IterationRecord]
    stopped_reason: str


def run_refinement(
    frame: pd.DataFrame,
    proposer: HypothesisProposer,
    space: HyperParamSpace,
    criteria: AcceptanceCriteria,
    market: str,
    return_target: float,
    available_factors: List[str],
    max_iterations: int = 10,
    n_trials: int = 20,
    seed: int = 0,
    cost_model: CostModel | None = None,
) -> RefinementResult:
    history: List[IterationRecord] = []
    for i in range(max_iterations):
        context = ProposalContext(
            market=market, return_target=return_target,
            available_factors=available_factors, history=history,
        )
        try:
            hypothesis = proposer.propose(context)
        except InvalidHypothesisError as exc:
            history.append(IterationRecord(hypothesis=None, best_score=None, passed=False, note=f"invalid: {exc}"))
            continue

        result = search_strategy(
            frame, hypothesis, space, criteria, n_trials=n_trials, seed=seed + i, cost_model=cost_model
        )
        history.append(
            IterationRecord(
                hypothesis=hypothesis,
                best_score=result.hpo.best_score,
                passed=result.evaluation.passed,
                note="; ".join(result.evaluation.notes),
            )
        )
        if result.evaluation.passed:
            return RefinementResult(accepted=result, iterations=history, stopped_reason="accepted")

    return RefinementResult(accepted=None, iterations=history, stopped_reason="budget_exhausted")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_refinement.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/refinement.py tests/test_refinement.py
git commit -m "feat: add hypothesis proposer protocol and refinement loop"
```

---

### Task 5: Claude-backed hypothesis proposer

**Files:**
- Create: `src/quant_agent_team/claude_proposer.py`
- Modify: `pyproject.toml` (add `anthropic` to optional `llm` extra)
- Test: `tests/test_claude_proposer.py`

**Interfaces:**
- Consumes: `ProposalContext`, `InvalidHypothesisError` (Task 4); `FactorHypothesis`, `FactorDef` (Phase 1/2).
- Produces: `ClaudeHypothesisProposer(client=None, model="claude-opus-4-8", max_tokens=2000)` implementing `propose(context) -> FactorHypothesis`. Calls `client.messages.create(...)` with a JSON-schema `output_config`, reads the text block, `json.loads` it, and builds a validated `FactorHypothesis` (`market` taken from the context). Parse/validation failure raises `InvalidHypothesisError`. When `client` is `None`, the Anthropic SDK is lazy-imported and `anthropic.Anthropic()` is constructed on first use.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_claude_proposer.py
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.claude_proposer import ClaudeHypothesisProposer
from quant_agent_team.refinement import InvalidHypothesisError, ProposalContext


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


def _context() -> ProposalContext:
    return ProposalContext(market="cn", return_target=0.30, available_factors=["momentum_20d", "volatility_20d"], history=[])


class ClaudeProposerTest(unittest.TestCase):
    def test_parses_valid_json_into_hypothesis(self) -> None:
        payload = (
            '{"factors": [{"name": "momentum_20d", "source_field": "momentum_20d", '
            '"direction": "long_high"}], "sector_neutral": false}'
        )
        client = _FakeClient(payload)
        proposer = ClaudeHypothesisProposer(client=client)
        hyp = proposer.propose(_context())
        self.assertEqual(hyp.market, "cn")
        self.assertEqual(len(hyp.factors), 1)
        self.assertEqual(hyp.factors[0].name, "momentum_20d")
        self.assertEqual(client.messages.last_kwargs["model"], "claude-opus-4-8")

    def test_invalid_json_raises_invalid_hypothesis(self) -> None:
        proposer = ClaudeHypothesisProposer(client=_FakeClient("not json"))
        with self.assertRaises(InvalidHypothesisError):
            proposer.propose(_context())

    def test_schema_violation_raises_invalid_hypothesis(self) -> None:
        # bad direction value -> FactorDef validation fails
        payload = '{"factors": [{"name": "x", "source_field": "x", "direction": "sideways"}], "sector_neutral": false}'
        proposer = ClaudeHypothesisProposer(client=_FakeClient(payload))
        with self.assertRaises(InvalidHypothesisError):
            proposer.propose(_context())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_claude_proposer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quant_agent_team.claude_proposer'`

- [ ] **Step 3: Implement and declare the optional dependency**

In `pyproject.toml`, under `[project.optional-dependencies]`, add an `llm` extra (leave the existing `test` extra in place):

```toml
[project.optional-dependencies]
test = ["pytest"]
llm = ["anthropic"]
```

```python
# src/quant_agent_team/claude_proposer.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List

from .hypothesis import FactorDef, FactorHypothesis
from .refinement import InvalidHypothesisError, ProposalContext

HYPOTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_field": {"type": "string"},
                    "direction": {"type": "string", "enum": ["long_high", "long_low"]},
                },
                "required": ["name", "source_field", "direction"],
                "additionalProperties": False,
            },
        },
        "sector_neutral": {"type": "boolean"},
    },
    "required": ["factors", "sector_neutral"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are a quantitative researcher proposing a linear multi-factor stock-selection "
    "hypothesis. Choose 1-8 factors from the available list. Respond only with JSON "
    "matching the provided schema."
)


def _build_prompt(context: ProposalContext) -> str:
    lines = [
        f"Market: {context.market}",
        f"Target annualized return (net of costs, out-of-sample): >= {context.return_target:.0%}",
        f"Available factor fields: {', '.join(context.available_factors)}",
    ]
    if context.history:
        lines.append("Past attempts (most recent last):")
        for record in context.history[-5:]:
            lines.append(
                f"- passed={record.passed} score={record.best_score} note={record.note}"
            )
        lines.append("Propose a different hypothesis that addresses the failures above.")
    return "\n".join(lines)


@dataclass
class ClaudeHypothesisProposer:
    client: Any = None
    model: str = "claude-opus-4-8"
    max_tokens: int = 2000

    def _resolve_client(self) -> Any:
        if self.client is not None:
            return self.client
        import anthropic

        self.client = anthropic.Anthropic()
        return self.client

    def propose(self, context: ProposalContext) -> FactorHypothesis:
        client = self._resolve_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(context)}],
            output_config={"format": {"type": "json_schema", "schema": HYPOTHESIS_SCHEMA}},
        )
        try:
            text = next(block.text for block in response.content if block.type == "text")
            data = json.loads(text)
            factors: List[FactorDef] = [
                FactorDef(name=f["name"], source_field=f["source_field"], direction=f["direction"])
                for f in data["factors"]
            ]
            return FactorHypothesis(
                market=context.market,
                factors=factors,
                sector_neutral=bool(data["sector_neutral"]),
            )
        except (StopIteration, ValueError, KeyError, TypeError) as exc:
            raise InvalidHypothesisError(str(exc)) from exc
```

Note: `json.loads` raises `json.JSONDecodeError`, a subclass of `ValueError`, so the `except` clause above catches malformed JSON.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_claude_proposer.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/quant_agent_team/claude_proposer.py tests/test_claude_proposer.py pyproject.toml
git commit -m "feat: add Claude-backed hypothesis proposer (injectable client)"
```

---

### Task 6: Phase 3 regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all Phase 1–3 tests PASS; the 8 PostgreSQL-dependent tests SKIP. No failures.

- [ ] **Step 2: Commit (if incidental fixes were needed)**

```bash
git add -A
git commit -m "test: confirm Phase 3 suite green"
```

---

## Deferred to Phase 4

- `HoldoutVault` (one-shot holdout evaluation; feeds `dev_return`/`holdout_return` into `overfitting_score`).
- `PaperTradeRunner` (forward test).
- US market provider + survivorship-free universe.
- Daily mark-to-market in the factor backtest; sector-neutral data wiring.
- A top-level orchestrator that runs `run_refinement`, attaches `overfitting_score` + `deflate_return` to the accepted candidate, and runs `run_null_test` as a calibration gate.

## Self-Review

- **Spec coverage:** §5.5 `OverfittingScore` → Task 1; deflated performance → Task 2; null test → Task 3; §4 outer loop + §5.1 invalid-output handling → Task 4; §5.1 LLM proposes schema-valid hypothesis → Task 5.
- **Placeholder scan:** every code step is complete; the `json.JSONDecodeError ⊂ ValueError` behavior is stated so the `except` is correct.
- **Type consistency:** `OverfittingInputs`/`overfitting_score`/`deflate_return` names match across Tasks 1–2 and the test files; `NullTestResult`/`run_null_test` match Task 3; `ProposalContext`/`IterationRecord`/`InvalidHypothesisError`/`HypothesisProposer`/`RefinementResult`/`run_refinement` match Task 4 and are imported unchanged by Task 5; `ClaudeHypothesisProposer.propose` returns a `FactorHypothesis` built with the Phase 1/2 dataclasses; `search_strategy`/`HyperParamSpace`/`SearchResult` reused from Phase 2 with their existing signatures; `AcceptanceCriteria`/`CostModel` reused from Phase 1.
