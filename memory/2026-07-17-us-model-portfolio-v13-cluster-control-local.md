# 2026-07-17 US model portfolio v13 cluster control

## Summary

Stage: model-portfolio-combination-layer

The current live monitoring pool remains unchanged at 425 strategies. No strategy was deleted or filtered out because of current underperformance. The 2026-07-16 live report was regenerated after creating the v13 candidate model portfolio.

This round stopped hard-scanning the recent `diffusion` and `industrylowcrowd` single-strategy spaces because rounds 293 and 295 did not add strategies and their best candidates were limited by rolling information ratio / random significance. The work moved to portfolio-level construction from persistent outperforming 5/7-strategy sleeves.

## What changed

- Added strategy-cluster parsing in `scripts/us_build_current_model_portfolio.py`.
- Added per-stock cluster diagnostics:
  - `cluster_count`
  - `max_cluster_share`
  - `dominant_cluster`
  - `cluster_concentration_penalty`
- Applied a quadratic penalty when one strategy cluster dominates a stock's support.
- Generated candidate-only model portfolio:
  - `reports/us/live/current/us_current_model_portfolio_20260716_v13.csv`
  - `reports/us/live/current/us_current_model_portfolio_20260716_v13.json`

## Result

The v13 portfolio has 20 stocks, total weight 100%, no drag-symbol holdings, max single-stock weight about 8%, and max sector weight about 25.68%.

The cluster control improves ranking pressure against single-cluster stocks, but it cannot fully remove single-cluster holdings because the persistent outperforming current pool still has limited multi-cluster stock overlap. Several symbols still have `cluster_count = 1` and `max_cluster_share = 1.0`; these are retained only after penalty and because there are not enough stronger multi-cluster alternatives under the existing 20-stock target.

## Validation

- `python scripts\tmp_validate_us_live_20260716.py`
  - current strategies: 425
  - outperformers: 246
  - underperformers retained: 179
  - persistent outperformers: 246
  - valuation date: 2026-07-16
  - holding distribution: 5/7/10/20 only
  - invalid holding count: 0
  - fallback stock name: false
- `$env:PYTHONPATH='.'; pytest -q`
  - 181 passed, 8 skipped

## Next step

Do not keep tightening cluster penalty alone. The bottleneck is source diversity: the current persistent outperforming pool does not yet provide enough independent multi-cluster support for all 20 stocks. Next research should either add genuinely new factor/data dimensions or build a two-layer portfolio where 5/7 alpha sleeves and 20-stock stabilizer sleeves are evaluated separately before blending.
