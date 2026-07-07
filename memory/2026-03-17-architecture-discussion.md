# Architecture Discussion - 2026-03-17

## Context

- MCP memory server `codex-mcp-memory` is unavailable in this session.
- Fallback to local project memory as required by project policy.
- This stage focuses on discussing the quant code implementation architecture, not writing the full engine yet.

## Summary

- Keep the project as a research-driven pipeline, not a strategy-template runner.
- Separate code architecture into six layers:
  - workflow orchestration
  - domain models
  - data access
  - feature computation
  - strategy execution
  - review and monitoring output
- `strategy_brief` should remain the contract between research intent and executable strategy spec.
- Initial implementation should avoid a general-purpose expression engine; use Python strategy modules plus typed config objects first.
- Backtest logic should be independent from data ingestion and feature persistence.
- Event, category, market-context, technical, and fundamental factors should all map into one unified factor input schema before strategy scoring.

## Proposed implementation direction

### Layer 1. workflow

- Own stage transitions and artifact paths.
- Trigger:
  - brief creation
  - data requirement confirmation
  - feature materialization
  - backtest run
  - review packet generation
  - monitor snapshot generation

### Layer 2. domain

- Typed models for:
  - `StrategyBrief`
  - `DataRequirement`
  - `FactorDefinition`
  - `SignalRule`
  - `PortfolioRule`
  - `BacktestConfig`
  - `ReviewDecision`

### Layer 3. data

- Repositories over PostgreSQL tables:
  - `raw_market_daily`
  - `normalized_market_daily`
  - `research_feature_store`
  - `fundamental_indicator_daily`
  - `market_event_timeline`
- Hide SQL details behind repository interfaces.

### Layer 4. feature

- Feature builders compute reusable factor series and write them into `research_feature_store`.
- Prefer batch jobs by date range and universe.

### Layer 5. strategy

- A strategy instance should be assembled from:
  - universe selector
  - factor loader
  - signal scorer
  - portfolio constructor
  - rebalance scheduler
- This layer should output ranked candidates and portfolio decisions.

### Layer 6. backtest and review

- Backtest engine consumes:
  - normalized bars
  - feature snapshots
  - strategy rules
- Review layer consumes:
  - backtest metrics
  - risk diagnostics
  - explainability artifacts

## Constraints

- Do not freeze a fully generic DSL too early.
- Do not couple strategy logic directly to raw CSV ingestion.
- Do not mix feature persistence with backtest accounting.

## Next step

- Finalize the directory/module layout for:
  - repositories
  - feature builders
  - strategy runtime
  - backtest engine
- Then decide whether first executable strategy should be:
  - trend + category rotation
  - event + sector mapping
  - technical + fundamental composite ranking
