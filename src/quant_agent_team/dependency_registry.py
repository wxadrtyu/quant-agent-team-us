from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class DependencyEntry:
    name: str
    kind: str
    source_table: str
    source_field: str
    resolver: str
    dependencies: List[str] = field(default_factory=list)
    is_base_data: bool = False
    notes: str = ""


class DependencyRegistry:
    def __init__(self, entries: Iterable[DependencyEntry]) -> None:
        self._entries: Dict[str, DependencyEntry] = {entry.name: entry for entry in entries}

    def resolve(self, name: str) -> DependencyEntry:
        if name not in self._entries:
            raise KeyError(f"Unknown dependency: {name}")
        return self._entries[name]

    def contains(self, name: str) -> bool:
        return name in self._entries

    def all(self) -> List[DependencyEntry]:
        return list(self._entries.values())


DEFAULT_DEPENDENCY_REGISTRY = DependencyRegistry(
    [
        DependencyEntry(
            name="close_price",
            kind="market_field",
            source_table="normalized_market_daily",
            source_field="close_price",
            resolver="base_incremental_ingest",
            is_base_data=True,
            notes="Raw close price from normalized market data.",
        ),
        DependencyEntry(
            name="close_price_adj",
            kind="market_field",
            source_table="normalized_market_daily",
            source_field="close_price_adj",
            resolver="base_incremental_ingest",
            is_base_data=True,
            notes="Adjusted close price for price-based strategies.",
        ),
        DependencyEntry(
            name="volume",
            kind="market_field",
            source_table="normalized_market_daily",
            source_field="volume",
            resolver="base_incremental_ingest",
            is_base_data=True,
        ),
        DependencyEntry(
            name="turnover",
            kind="market_field",
            source_table="normalized_market_daily",
            source_field="turnover",
            resolver="base_incremental_ingest",
            is_base_data=True,
        ),
        DependencyEntry(
            name="industry_name",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="industry_name",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="sector_name",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="sector_name",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="theme_tags",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="theme_tags",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="roe",
            kind="fundamental_field",
            source_table="fundamental_indicator_daily",
            source_field="roe",
            resolver="strategy_data_sync.fundamental_ingest",
        ),
        DependencyEntry(
            name="pe_ttm",
            kind="fundamental_field",
            source_table="fundamental_indicator_daily",
            source_field="pe_ttm",
            resolver="strategy_data_sync.fundamental_ingest",
        ),
        DependencyEntry(
            name="hotness_score",
            kind="event_field",
            source_table="market_event_timeline",
            source_field="hotness_score",
            resolver="strategy_data_sync.event_ingest",
        ),
        DependencyEntry(
            name="northbound_hold_value",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="northbound_hold_value",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="northbound_estimated_increase_value",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="northbound_estimated_increase_value",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="attention_rank",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="attention_rank",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="attention_new_fans_ratio",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="attention_new_fans_ratio",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="attention_loyal_fans_ratio",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="attention_loyal_fans_ratio",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="attention_level",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="attention_level",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="attention_change_3d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="attention_change_3d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="attention_change_5d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="attention_change_5d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="northbound_holding_change_1d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="northbound_holding_change_1d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="northbound_holding_change_5d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="northbound_holding_change_5d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="northbound_net_flow_proxy_1d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="northbound_net_flow_proxy_1d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="northbound_net_flow_proxy_5d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="northbound_net_flow_proxy_5d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="theme_breadth_score",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="theme_breadth_score",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="policy_event_tag",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="policy_event_tag",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="announcement_event_tag",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="announcement_event_tag",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="announcement_count_1d",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="announcement_count_1d",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="earnings_event_tag",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="earnings_event_tag",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="earnings_event_direction",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="earnings_event_direction",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="earnings_event_strength_score",
            kind="market_context_field",
            source_table="research_market_context_daily",
            source_field="earnings_event_strength_score",
            resolver="market_context.refresh",
        ),
        DependencyEntry(
            name="ma_5",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ma_5",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="ma_10",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ma_10",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="ma_20",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ma_20",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="ma_60",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ma_60",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="avg_volume_20d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="avg_volume_20d",
            resolver="feature_builder",
            dependencies=["volume"],
        ),
        DependencyEntry(
            name="avg_turnover_20d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="avg_turnover_20d",
            resolver="feature_builder",
            dependencies=["turnover"],
        ),
        DependencyEntry(
            name="volume_ratio_20d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="volume_ratio_20d",
            resolver="feature_builder",
            dependencies=["volume"],
        ),
        DependencyEntry(
            name="ret_1d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ret_1d",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="ret_5d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ret_5d",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="ret_20d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="ret_20d",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="momentum_20d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="momentum_20d",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
        DependencyEntry(
            name="volatility_20d",
            kind="derived_feature",
            source_table="research_feature_daily",
            source_field="volatility_20d",
            resolver="feature_builder",
            dependencies=["close_price_adj"],
        ),
    ]
)
