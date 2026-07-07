from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _validate_choice(value: str, field_name: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}, got {value!r}")


@dataclass
class KpiTarget:
    trade_win_rate: float
    annualized_return: float
    max_drawdown_limit: float
    notes: str = ""


@dataclass
class KpiVersion:
    version_id: str
    created_at: str
    target: KpiTarget
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyFactor:
    name: str
    group: str
    purpose: str
    direction: str
    expression_hint: str = ""
    source_hint: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        _validate_choice(
            self.group,
            "group",
            {"technical", "fundamental", "event", "market_context", "category"},
        )
        _validate_choice(
            self.purpose,
            "purpose",
            {"filter", "ranking", "trigger", "confirmation", "risk_control"},
        )
        _validate_choice(
            self.direction,
            "direction",
            {"positive", "negative", "neutral", "contextual"},
        )


@dataclass
class StrategyBrief:
    strategy_id: str
    title: str
    thesis: str
    summary: str = ""
    market_rationale: str = ""
    expected_market_regime: str = ""
    invalid_conditions: List[str] = field(default_factory=list)
    technical_factors: List[StrategyFactor] = field(default_factory=list)
    fundamental_factors: List[StrategyFactor] = field(default_factory=list)
    event_factors: List[StrategyFactor] = field(default_factory=list)
    market_context_factors: List[StrategyFactor] = field(default_factory=list)
    category_factors: List[StrategyFactor] = field(default_factory=list)
    required_market_fields: List[str] = field(default_factory=list)
    required_fundamental_fields: List[str] = field(default_factory=list)
    required_event_fields: List[str] = field(default_factory=list)
    required_label_fields: List[str] = field(default_factory=list)
    derived_features_needed: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DerivedFeatureSpec:
    feature_name: str
    formula: str
    dependencies: List[str] = field(default_factory=list)
    window: Optional[int] = None
    output_type: str = "numeric"
    notes: str = ""


@dataclass
class RuleCondition:
    field: str
    operator: str
    value: Any = None
    value_from: Optional[str] = None
    window: Optional[int] = None
    notes: str = ""

    def __post_init__(self) -> None:
        _validate_choice(
            self.operator,
            "operator",
            {
                ">",
                ">=",
                "<",
                "<=",
                "=",
                "!=",
                "in",
                "not_in",
                "contains",
                "not_contains",
                "between",
                "is_true",
                "is_false",
            },
        )
        if self.value is not None and self.value_from is not None:
            raise ValueError("value and value_from are mutually exclusive")


@dataclass
class RuleConditionGroup:
    logic: str
    conditions: List[RuleCondition] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_choice(self.logic, "logic", {"AND", "OR"})


@dataclass
class TradingRule:
    rule_id: str
    logic: str
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        _validate_choice(self.logic, "logic", {"AND", "OR"})


@dataclass
class PositionRules:
    position_sizing_method: str
    max_positions: int
    min_positions: int = 1
    min_holding_days_before_exit: int = 0
    holding_period_hint: str = ""
    rebalance_frequency: str = ""
    ranking_key: str = ""

    def __post_init__(self) -> None:
        _validate_choice(
            self.position_sizing_method,
            "position_sizing_method",
            {"equal_weight", "score_weight", "fixed_slots"},
        )


@dataclass
class RiskConstraints:
    max_drawdown_limit: float
    max_single_position_weight: float
    exclude_st: bool = True
    exclude_suspended: bool = True
    exclude_limit_up: bool = True
    exclude_limit_down: bool = False


@dataclass
class RankingFormula:
    score_name: str = ""
    formula: str = ""
    components: List[str] = field(default_factory=list)
    sort_direction: str = "desc"
    notes: str = ""

    def __post_init__(self) -> None:
        _validate_choice(self.sort_direction, "sort_direction", {"asc", "desc"})


@dataclass
class ExecutionTiming:
    signal_generation_time: str = "after_close"
    trade_reference_time: str = "next_open_reference"
    data_cutoff_rule: str = "use only data available by market close"


@dataclass
class ReviewSpec:
    required_metrics: List[str] = field(default_factory=list)
    review_focus: List[str] = field(default_factory=list)
    known_risks: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)


@dataclass
class StrategySpec:
    spec_id: str
    strategy_id: str
    version: str
    status: str
    derived_from_brief_id: str
    created_at: str
    updated_at: str
    market_inputs: List[str] = field(default_factory=list)
    fundamental_inputs: List[str] = field(default_factory=list)
    event_inputs: List[str] = field(default_factory=list)
    label_inputs: List[str] = field(default_factory=list)
    derived_features: List[DerivedFeatureSpec] = field(default_factory=list)
    filters: List[TradingRule] = field(default_factory=list)
    entry_rules: List[TradingRule] = field(default_factory=list)
    exit_rules: List[TradingRule] = field(default_factory=list)
    ranking_formula: Optional[RankingFormula] = None
    position_rules: Optional[PositionRules] = None
    risk_constraints: Optional[RiskConstraints] = None
    execution_timing: ExecutionTiming = field(default_factory=ExecutionTiming)
    review_spec: ReviewSpec = field(default_factory=ReviewSpec)

    def __post_init__(self) -> None:
        _validate_choice(
            self.status,
            "status",
            {
                "draft",
                "data_required",
                "data_ready",
                "implementation_pending",
                "backtesting",
                "review_pending",
                "approved",
                "rejected",
                "monitoring",
            },
        )

    @property
    def required_field_groups(self) -> Dict[str, List[str]]:
        return {
            "market": list(self.market_inputs),
            "fundamental": list(self.fundamental_inputs),
            "event": list(self.event_inputs),
            "label": list(self.label_inputs),
            "derived": [feature.feature_name for feature in self.derived_features],
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
