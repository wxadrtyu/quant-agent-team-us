# 2026-03-27 Data Request: Northbound Attention Resonance

Requester: `quant-researcher`

Target candidate:

- `cn-a-northbound-attention-resonance`

## Why this request exists

The current pure price/volume factor family has already produced one good economic baseline, but repeated optimization failed to turn it into a high-hit-rate strategy.

The next candidate needs new information, not more parameter tweaking.

## Priority 1: Capital Flow

Required fields:

- `northbound_holding_change_1d`
- `northbound_holding_change_5d`
- `northbound_holding_ratio`
- `northbound_net_flow_proxy_1d`
- `northbound_net_flow_proxy_5d`

Why needed:

- confirm whether a technical setup is backed by external incremental capital
- help reject purely technical false-positive entries

Preferred granularity:

- stock-date daily table

## Priority 2: Theme / Category Context

Required fields:

- `industry_name`
- `sector_name`
- `theme_tags`
- `theme_breadth_score`

Why needed:

- the candidate assumes higher hit rate when a setup belongs to an active market main line
- current market data lacks a structured theme context layer

Preferred granularity:

- stock-date daily table for tags if possible
- at least point-in-time tag snapshots if daily is too expensive initially

## Priority 3: Event / Attention

Required fields:

- `policy_event_tag`
- `announcement_event_tag`
- `attention_level`
- `attention_change_3d`
- `attention_change_5d`

Why needed:

- the strategy hypothesis depends on narrative propagation and attention expansion
- attention should help distinguish supported continuation from weak technical drift

Preferred proxy sources:

- public news / announcement feeds
- public forum / click / search / mention proxies

## Delivery Preference

Minimum viable first delivery:

1. northbound stock-date daily table
2. industry/theme tag mapping
3. one attention proxy with stable historical coverage

## Expected downstream use

- add normalized storage tables
- derive daily research features
- validate whether a capital-flow-plus-attention strategy can beat the current `trend-pullback v4` baseline on hit rate
