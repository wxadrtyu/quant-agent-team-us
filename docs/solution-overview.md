# Quant Agent Team — Solution Overview & Gap Analysis

Status: v2, optimized solution draft, 2026-06-27. Cross-referenced against [`current-architecture-draft.md`](current-architecture-draft.md) (the approved target architecture in Chinese) and the actual codebase under `src/quant_agent_team/`. See §6 for the full list of changes from v1.

## 1. What this project actually is today

`quant-agent-team` is **not** an autonomous AI-trading system. It is a research-and-backtest production pipeline for A-share (Chinese equity) daily-frequency strategies, designed around a human-in-the-loop workflow:

1. A user supplies a KPI target (win rate, return, max drawdown).
2. A researcher (human today, AI agent in the target design) proposes a `strategy_brief`.
3. The brief is formalized into an implementation-level `strategy_spec`.
4. The system resolves and backfills the data the spec needs.
5. `backtest_runner` simulates the strategy historically.
6. `evaluation` checks the result against the KPI.
7. A human approves or rejects.
8. (Target only) Approved strategies move into a daily `scan_runner` that emits buy candidates, pushed via Feishu by `monitoring`.

Of this nine-step loop, **steps 1–6 are implemented**. Steps 8–9 (scanning and notification) exist only as names in the architecture draft — no code. There is no order placement and none is planned for v1; the explicit target is "emit signals, human buys manually."

## 2. Confirmed module map

| Module | Path | Status |
|---|---|---|
| Market data ingestion | `src/quant_agent_team/ingestion.py`, `market_fetch.py` | Working — AkShare/PyTDX/YFinance with fallback, hash-based dedup into `raw_market_daily` |
| DB layer / schema | `src/quant_agent_team/db.py` | Working, but hardcoded macOS paths (see §3.1) |
| Market context (northbound flow, attention, themes, events) | `market_context.py` | Working, depends on unstable free third-party endpoints |
| Feature computation | `feature_refresh.py` → `research_feature_daily` | Working |
| Strategy data model | `models.py` (`KpiVersion`, `StrategyBrief`, `StrategySpec`, `TradingRule`, `StrategyFactor`) | Working, manually authored — no generator |
| Dependency resolution | `dependency_registry.py`, `strategy_data_sync.py` | Working as a planner only; not wired into backtest as a gate |
| Backtesting | `backtest_runner.py` | Working — rule-based row simulation, ranked entry, position sizing. No commission/slippage/order-queue modeling |
| Evaluation | `evaluation.py` | Working, but KPI thresholds are hardcoded defaults rather than always reading the user's `KpiVersion` |
| Data quality reporting | `data_quality.py`, `lagging_status.py` | Working — coverage/conflict/lag reports to `reports/data_quality/latest.json` |
| Workflow/CLI | `workflow.py`, `cli.py` | Working orchestration layer, no stage-gate enforcement |
| Dashboard | `apps/db_dashboard.py` | Working Streamlit viewer, manual inspection only |
| **Strategy generation via AI** | — | **Not implemented.** No LLM/Claude/OpenAI calls anywhere in `src/`. Agent roles in docs (`quant-researcher`, `strategy-engineer`) are role *descriptions*, not code. |
| **Scan / signal output** | — | **Not implemented.** `scan_runner` does not exist as code. |
| **Monitoring / notification (Feishu)** | — | **Not implemented.** `monitoring` does not exist as code. |
| **Deployable trading output** | — | **Not implemented.** Pipeline output today stops at `reports/backtests/*.json`; no broker/order export format exists. |

## 3. Architectural flaws and risks (evidence-based)

### 3.1 Platform portability — Critical
`db.py` hardcodes a macOS-only psql binary path and a Unix-socket connection string:
```python
PSQL_BIN = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/psql")
DEFAULT_DB_URL = f"postgresql:///{DEFAULT_DB_NAME}?host=/tmp"
```
Only `QUANT_DB_URL` is overridable; the psql binary path is not. The framework cannot run as-is on Linux or Windows.

### 3.2 No scanning/monitoring implementation — Critical, functional gap
The approved architecture (§5–7 of `current-architecture-draft.md`) treats `scan_runner` and `monitoring` as core pipeline stages. Neither exists in code. **This is the single largest gap between the stated goal ("output deployable trading solutions") and reality** — the pipeline currently has no path from an approved backtested strategy to an actionable daily signal.

### 3.3 No AI integration for strategy generation — Critical, functional gap
`StrategyBrief`/`StrategySpec` are populated by hand-written JSON. There is no prompt template, no agent loop, no LLM client anywhere in the codebase. The "AI generates strategies" half of the original framing does not exist yet; it is documented intent only.

### 3.4 Unmanaged external data dependencies — High
`market_fetch.py` and `market_context.py` call multiple free, rate-limited, occasionally geo-restricted third-party endpoints (AkShare, PyTDX, Eastmoney mirrors) with minimal retry/backoff and provider fallback that is acknowledged in-code as "noisy" (`NOISY_FALLBACK_PROVIDERS`). A single upstream outage can silently degrade or fail the daily ingest.

### 3.5 Thin error handling in the daily pipeline — High
`scripts/run_daily_pipeline.py` catches per-stock fetch exceptions but only prints them — failures are not surfaced to data-quality reporting or retried, so partial-day failures can go unnoticed until manually inspected.

### 3.6 Dependency gate not enforced — Medium
`strategy_data_sync.py` computes a sync plan for a spec but nothing consumes its output to block backtesting when required data is missing. A spec can enter `backtest_runner` and fail with a raw SQL/column error instead of a clear "missing data source" message.

### 3.7 Hardcoded KPI thresholds — Medium
`evaluation.py` defaults (`min_trade_win_rate=0.80`, `min_annualized_return=0.20`, `max_drawdown_limit=0.30`) are function defaults rather than always being sourced from the user-supplied `KpiVersion`, risking evaluation against the wrong target if a caller omits them.

### 3.8 Naive backtest economics — Medium
`backtest_runner.py` does not model commissions, slippage, or order-queue/fill mechanics. Backtest KPIs will be systematically optimistic relative to live execution.

### 3.9 Minimal automated test coverage — Medium
Only a handful of test files exist (`test_backtest.py`, `test_workflow.py`, `test_market_context.py`); no CI workflow runs them. Regressions in ingestion or backtest logic are unlikely to be caught before they reach the data quality report.

### 3.10 Repository hygiene — Medium
The repository root currently carries 50+ untracked, ad-hoc scripts (`convert_dump*.py`, `decompress_*.py`, `restore_*.py/.bat/.sh`, `duckdb_viewer.py`, etc.) plus large PostgreSQL dump files tracked via git-lfs (`data/large_tables/*.dump`). These are one-off DB migration/debugging artifacts, not part of the core framework, and should not live in the same root as `src/quant_agent_team/`. Their presence increases clone size and makes it harder for a new contributor to identify what is load-bearing.

### 3.11 No audit trail on strategy approval — Low-Medium
`StrategySpec` has no `approved_by`/`approved_at` fields; "approved strategy pool" is described as eventually keyed off `status = approved` only, which is not auditable if more than one user/agent participates in approval.

## 4. Optimized solution — prioritized work items

Each item below maps to a flaw in §3, states the concrete change, and gives an acceptance criterion so "done" is checkable.

### P0 — close the stated end-to-end claim
These are the items that actually make the system produce a usable daily output; nothing else matters until this tier lands.

1. **Implement `scan_runner`.** (closes 3.2) Load every `StrategySpec` with `status == "approved"`; for each, pull the latest trading day's row from `research_feature_daily` + `normalized_market_daily`, evaluate `entry_rules` using the same condition evaluator already in `backtest_runner.py` (do not fork the rule engine — import and reuse it), rank by `ranking_key`, cap at `max_positions`.
   *Acceptance:* running `scan_runner` against a known approved spec and a known historical date reproduces the same entries `backtest_runner` would have opened on that date.

2. **Implement `monitoring`.** (closes 3.2) Format `scan_runner` output into a Feishu webhook payload; explicitly handle and message the zero-signal case (per the architecture draft's requirement) rather than sending nothing.
   *Acceptance:* a scan with 0 hits and a scan with N hits both produce a delivered Feishu message.

3. **Make `strategy_data_sync` a hard gate.** (closes 3.6) Before `backtest_runner` or `scan_runner` runs against a spec, call `strategy_data_sync.plan()`; if any planned item is unresolved, raise a typed `MissingDependencyError` listing the missing source tables instead of letting execution reach a raw SQL error.
   *Acceptance:* a spec referencing a not-yet-ingested field fails with a one-line named error, not a stack trace from `psycopg`/`pandas`.

### P1 — make the system portable and operable
4. **Remove hardcoded macOS paths in `db.py`.** (closes 3.1) Introduce `QUANT_PSQL_BIN` env var alongside the existing `QUANT_DB_URL`; fall back to `shutil.which("psql")` rather than a fixed Homebrew Cellar path; drop the `/tmp`-socket-only default in favor of a standard `localhost:5432` default that works cross-platform, overridable via `QUANT_DB_URL`.
   *Acceptance:* `db.py` imports and connects on a clean Linux/Windows box with only `QUANT_DB_URL` set, no code edits.

5. **Add retry/backoff + structured failure surfacing for external providers.** (closes 3.4, 3.5) Wrap each provider call in `market_fetch.py`/`market_context.py` with bounded retry (e.g. 3 attempts, exponential backoff); on exhaustion, write a structured failure record consumed by `data_quality.py`'s report instead of only `print()`-ing it from `run_daily_pipeline.py`.
   *Acceptance:* `reports/data_quality/latest.json` contains a `provider_failures` section after a forced-failure test run; nothing is print-only.

6. **Clean up repository root.** (closes 3.10) Move the 50+ ad-hoc dump/conversion/restore scripts currently sitting untracked in repo root into `tools/db-migration/` (or delete if truly one-off and no longer needed — confirm with the user first since they're currently untracked, not yet committed). Re-evaluate whether `data/large_tables/*.dump` need to be committed via git-lfs at all, or whether they're a one-time local artifact that belongs in `.gitignore` instead.
   *Acceptance:* `git status` at repo root shows only files under `src/`, `scripts/`, `apps/`, `docs/`, `tests/`, config files — no loose one-off scripts.

### P2 — strengthen evaluation fidelity and trust
7. **Add commission/slippage to `backtest_runner`.** (closes 3.8) Add `commission_bps` and `slippage_bps` parameters (simple fixed-bps deduction on entry and exit) to the simulation loop; default them to a conservative non-zero value rather than 0, so existing callers don't silently get optimistic numbers.
   *Acceptance:* re-running an existing backtest spec with default bps produces a lower (or equal) return than the current zero-cost simulation.

8. **Source KPI thresholds only from `KpiVersion`.** (closes 3.7) Remove the hardcoded defaults from `evaluate_backtest_result()`'s signature; require a `KpiVersion` argument; fail loudly if one isn't supplied instead of silently using 0.80/0.20/0.30.
   *Acceptance:* calling `evaluate_backtest_result()` without a `KpiVersion` raises `TypeError`, not a silent pass/fail against defaults.

9. **Add an audit trail to `StrategySpec` approval.** (closes 3.11) Add `approved_by: str | None` and `approved_at: datetime | None`; require both to be set together with `status = "approved"` (validate in the setter/constructor, not by convention).
   *Acceptance:* attempting to set `status = "approved"` without `approved_by`/`approved_at` raises a validation error.

10. **Add CI.** (closes 3.9) Add a GitHub Actions workflow running `pytest` on every PR against `tests/test_backtest.py`, `test_workflow.py`, `test_market_context.py`, plus new tests for items 1, 3, 7, 8 above as they land.
    *Acceptance:* a PR with a failing test is blocked from merge by a required status check.

### P3 — deliver on "AI generates strategies"
This tier is new scope, not a missing piece of existing code — treat it as its own design effort (recommend running it through the brainstorming → design-doc → implementation-plan process before coding starts).

11. **Build the `quant-researcher` agent loop.** (closes 3.3, half) An LLM call that, given a `KpiVersion` and the factor/research-dimension taxonomy already defined in `models.py`, drafts a `StrategyBrief`. Needs its own design pass: prompt structure, which LLM/API, how brief quality is checked before a human sees it.

12. **Build the `strategy-engineer` step.** (closes 3.3, other half) Turns an approved `StrategyBrief` into a `StrategySpec`, LLM-assisted, but the output must validate against the existing dataclass schema before being accepted — reject and retry on schema failure rather than passing through.

## 5. Bottom line

The data-ingestion and backtesting halves of the pipeline are real and reasonably solid engineering. The "AI strategy generation" and "deployable trading output" halves — the parts that justify calling this an AI trading-loop framework — do not exist in code yet; they are architecture-draft intent. §4 sequences closing that gap (P0–P1) ahead of fidelity and trust improvements (P2) ahead of the AI-generation build-out (P3), since P0/P1 are the smallest changes that make the existing backtested-strategy output actually usable end to end.

## 6. Revision log (v1 → v2)

| # | Change | Reason |
|---|---|---|
| 1 | §4 rewritten from a one-line-per-item roadmap into per-item technical proposals with explicit acceptance criteria | A roadmap line like "implement scan_runner" wasn't actionable on its own; each item now states *how* and *how to verify done* |
| 2 | P0 item 1 now explicitly requires reusing `backtest_runner`'s condition evaluator instead of a new one | Prevents drift between backtest and live-scan rule semantics, which would invalidate backtested KPI numbers |
| 3 | P0 item 3 specifies a named `MissingDependencyError` exception | Makes the §3.6 fix concrete and testable, not just "wire it in" |
| 4 | P1 item 4 specifies `shutil.which("psql")` fallback and a cross-platform default DB URL | Original v1 wording only said "make configurable," which doesn't fix the no-env-var-set case |
| 5 | P1 item 5 specifies where failures get surfaced (`data_quality.py` report) instead of just "add error handling" | Vague "add error handling" was flagged as a flaw itself (3.5); the fix needed to name the destination |
| 6 | P1 item 6 now asks for user confirmation before deleting ad-hoc scripts, rather than assuming deletion | These files are currently untracked/uncommitted local work; deleting them outright would be a destructive, unconfirmed action |
| 7 | P2 item 7 changed from "add commission/slippage parameters" to also requiring a non-zero default | A zero-default parameter is easy to add but changes nothing in practice; this closes that loophole |
| 8 | P2 item 8 changed from "make evaluation always source thresholds" to "remove defaults and require the argument, fail loudly" | "Always source from X" is unenforceable by convention; making the argument required is the actual fix |
| 9 | Added P2 item 9 (approval audit trail) as its own numbered item with a constructor-level validation requirement | Was previously folded into flaw 3.11 narrative only, with no concrete fix proposed |
| 10 | P3 items 11–12 now explicitly recommend a brainstorming/design pass before implementation, referencing the project's own brainstorming skill gate | Matches the user's house process (creative/implementation work requires a design step first) rather than treating P3 as a backlog item to code directly |
| 11 | Added this revision log (§6) | Requested by user to track what changed between drafts |
