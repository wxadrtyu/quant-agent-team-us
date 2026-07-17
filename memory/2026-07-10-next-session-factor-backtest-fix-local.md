# 2026-07-10 Next-Session Factor Backtest Fix

- summary: Fixed factor and weighted factor backtests to execute rebalance signals on the next trading session instead of same-day close. Entry and normal exit prefer `open_price`, with `close_price_adj` as fallback when open is unavailable. Final-period exit can mark at the final available close when no next execution session exists.
- stage: execution-realism
- kpi_version: v1.0-us
- tags:
  - project:quant-agent-team
  - market:cn_a
  - market:us
  - freq:daily
  - stage:execution-realism
  - status:local-memory-fallback
- evidence:
  - `python -m pytest tests/test_factor_backtest.py tests/test_weighted_backtest.py tests/test_hpo_objective.py tests/test_hpo_optimize.py tests/test_hpo_multiobjective.py tests/test_search_strategy.py tests/test_holdout.py tests/test_null_test.py tests/test_risk_overlay.py tests/test_pipeline_v51.py tests/test_a6_a7.py tests/test_cost_model.py -q` -> 31 passed.
  - `python -m pytest -q` -> 130 passed, 8 skipped.
- next_step: Revisit remaining reliability issues after US data is available: tradability/universe membership, PIT/survivorship, provider provenance, and holdout pressure.
- note: MCP memory tools were not available in this session, so this was saved as local fallback memory.
