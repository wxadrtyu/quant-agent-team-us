## [LRN-20260317-001] correction

**Logged**: 2026-03-17T16:22:56Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
Do not model `strategy_spec` and `DecisionResult` as near-duplicates; the user sees them as overlapping and wants a clearer boundary.

### Details
During architecture discussion, I described `strategy_spec` as the strategy implementation artifact and `DecisionResult` as the strategy output at a decision point. The user pointed out that `规格层` and `决策层` looked functionally overlapping. The correction is that `strategy_spec` must remain a stable, reusable strategy definition, while `DecisionResult` must only be a time-specific application of that definition to a prepared decision context. If the two look too similar, the architecture boundary is wrong or unnecessary.

### Suggested Action
Reframe the architecture around stable definition versus time-specific evaluation, and consider collapsing the decision layer if it adds no distinct value beyond executing `strategy_spec`.

### Metadata
- Source: user_feedback
- Related Files: /Users/laisicong/quant-agent-team/docs/current-architecture-draft.md
- Tags: correction, architecture, strategy_spec, decision_result

---
## [LRN-20260320-001] correction

**Logged**: 2026-03-20T09:13:00+08:00
**Priority**: high
**Status**: pending
**Area**: workflow

### Summary
Before moving into scheduling work, explicitly align the next task with the user; do not infer the next milestone after a successful ingest milestone.

### Details
After finishing the first full-load ingest and daily-update entrypoint work, I moved directly into scheduling-oriented implementation without first confirming the intended next task. The user clarified that the immediate next step was to verify whether the imported data itself was correct. I also should have aligned the daily scheduling logic with the user before implementing it.

### Suggested Action
When a milestone completes and multiple plausible next steps exist, pause and align on the next objective before editing code. For this project, verify imported data correctness before resuming any scheduling or automation work.

### Metadata
- Source: user_feedback
- Related Files: /Users/laisicong/quant-agent-team/src/quant_agent_team/workflow.py, /Users/laisicong/quant-agent-team/src/quant_agent_team/cli.py
- Tags: correction, workflow, alignment, scheduling

---
## [LRN-20260322-001] correction

**Logged**: 2026-03-22T12:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: workflow

### Summary
Daily market fetch windows must be computed per stock file, not from the database-wide max trade date.

### Details
I previously set the default daily fetch start date to `MAX(trade_date)` from `raw_market_daily` plus one day. That is wrong for heterogeneous source coverage. In this project, some stock files had already been updated through `2026-03-20`, while others still only had data through `2025-12-31`. Using the global max date caused lagging stocks to start fetching from `2026-03-07`, permanently skipping `2026-01-05` through `2026-03-06`. The correct default is `latest_trade_date_in_this_stock_file + 1 day`, with explicit backfill mode when repairing older gaps.

### Suggested Action
Keep per-stock start-date resolution in the fetch layer, add regression coverage for it, and treat global-date shortcuts as unsafe whenever file-level coverage may diverge.

### Metadata
- Source: user_feedback
- Related Files: /Users/laisicong/quant-agent-team/scripts/run_daily_pipeline.py, /Users/laisicong/quant-agent-team/src/quant_agent_team/market_fetch.py
- Tags: correction, fetch, daily_update, data_gap

---
## [LRN-20260329-001] correction

**Logged**: 2026-03-29T23:10:00+08:00
**Priority**: high
**Status**: pending
**Area**: workflow

### Summary
When the user asks for a new strategy direction, do not recycle prior local research conclusions; use fresh external research to choose the direction and only use local project materials as execution constraints.

### Details
I started a new strategy line by leaning on the project's existing local candidate research. The user corrected that this defeats the purpose because those local directions had already been explored once. The right workflow is: choose the direction from fresh external research or genuinely new reasoning first, then check whether the current project data can support an executable v1. Local research can help with implementation constraints, but it must not be the source of novelty when the user explicitly asks for a new direction.

### Suggested Action
For future new-strategy research in this project, separate "direction discovery" from "local feasibility". Document the external source anchors in the brief, then convert that direction into a short-window fast-screen spec.

### Metadata
- Source: user_feedback
- Related Files: /Users/laisicong/quant-agent-team-strategy/strategies, /Users/laisicong/quant-agent-team-strategy/research/candidates
- Tags: correction, strategy_research, novelty, workflow

---
