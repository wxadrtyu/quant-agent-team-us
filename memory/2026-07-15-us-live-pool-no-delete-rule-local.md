# 2026-07-15 US Live Pool No-Delete Rule Local Memory

## Summary

User explicitly clarified that strategies already entered into the live pool or current monitoring pool must not be deleted unless the user explicitly asks for deletion or removal. The user wants to observe the real forward effectiveness of live-pool strategies.

## Stage

review-decision / monitoring-observation

## KPI Version

US daily large-mid tradable universe. Applies to all live-pool, paper-live, monitoring, compact-pool, overlap-aware review, and future strategy-production workflows.

## Rule

- Do not delete strategies that have already entered the live pool or current monitoring pool unless the user explicitly says to delete or remove them.
- Future optimization may add strategies, create candidate pools, build compact views, mark review status, flag delayed observation, or create backup/snapshot tables.
- Future optimization must not destructively prune existing live-pool records merely because a new compact pool or ranking layer is better.
- If a compact pool is needed, implement it as a separate view/table/report or create a full backup first and clearly state what changed.

## Current State When Rule Was Recorded

- `us_live_monitoring_strategies_current`: 73 rows.
- `us_live_monitoring_holdings_current`: 787 rows.
- `us_live_pool_strategies`: 330 rows.
- `us_live_pool_holdings`: 3617 rows.
- Interrupted exploration process was stopped to prevent further background writes.

## Tags

project:quant-agent-team-us, market:us, freq:daily, stage:review-decision, status:active-rule

## Next Step

Continue strategy exploration additively. If a strategy fails later, mark or segment it rather than deleting it, unless the user explicitly approves deletion.
