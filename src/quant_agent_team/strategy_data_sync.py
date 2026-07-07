from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Set

from .dependency_registry import DEFAULT_DEPENDENCY_REGISTRY, DependencyEntry, DependencyRegistry
from .models import StrategySpec


@dataclass
class StrategyDataSyncResult:
    strategy_id: str
    spec_version: str
    resolved_requirements: List[str] = field(default_factory=list)
    satisfied_requirements: List[str] = field(default_factory=list)
    synced_requirements: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    failed_requirements: List[str] = field(default_factory=list)
    resolver_plan: Dict[str, List[str]] = field(default_factory=dict)
    ready_for_backtest: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class StrategyDataSync:
    def __init__(
        self,
        registry: DependencyRegistry | None = None,
        available_items: Iterable[str] | None = None,
    ) -> None:
        self.registry = registry or DEFAULT_DEPENDENCY_REGISTRY
        self.available_items: Set[str] = set(available_items or [])

    def plan(self, spec: StrategySpec) -> StrategyDataSyncResult:
        result = StrategyDataSyncResult(strategy_id=spec.strategy_id, spec_version=spec.version)
        requested = self._collect_dependencies(spec)
        result.resolved_requirements = sorted(requested)

        missing_entries: List[DependencyEntry] = []
        for name in result.resolved_requirements:
            if name in self.available_items:
                result.satisfied_requirements.append(name)
                continue

            entry = self.registry.resolve(name)
            resolver_bucket = result.resolver_plan.setdefault(entry.resolver, [])
            resolver_bucket.append(name)
            missing_entries.append(entry)

        result.synced_requirements = sorted(
            name for names in result.resolver_plan.values() for name in names
        )
        result.missing_requirements = list(result.synced_requirements)
        result.ready_for_backtest = not result.missing_requirements and not result.failed_requirements
        if result.missing_requirements:
            result.notes.append("Additional strategy-driven data sync is required before backtest.")
        else:
            result.notes.append("All declared dependencies are available for backtest.")
        return result

    def _collect_dependencies(self, spec: StrategySpec) -> Set[str]:
        requested: Set[str] = set()
        queue: List[str] = []
        for group in spec.required_field_groups.values():
            queue.extend(group)

        while queue:
            name = queue.pop(0)
            if name in requested:
                continue
            entry = self.registry.resolve(name)
            requested.add(entry.name)
            for dependency in entry.dependencies:
                if dependency not in requested:
                    queue.append(dependency)

        return requested
