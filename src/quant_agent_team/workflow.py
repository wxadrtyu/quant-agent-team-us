from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .dependency_registry import DEFAULT_DEPENDENCY_REGISTRY
from .backtest_runner import run_backtest
from .db import PostgresCli
from .data_quality import build_data_quality_report
from .evaluation import evaluate_backtest_result
from .feature_refresh import run_feature_refresh
from .market_context import refresh_market_context
from .ingestion import (
    build_data_inventory,
    inspect_stock_history,
    load_available_inventory_items,
    load_feature_available_fields,
    load_normalized_available_fields,
    repair_normalized_hash_mismatches,
    run_bootstrap_ingest,
    write_base_incremental_outputs,
)
from .io_utils import write_json
from .models import (
    DerivedFeatureSpec,
    ExecutionTiming,
    KpiTarget,
    KpiVersion,
    PositionRules,
    RankingFormula,
    ReviewSpec,
    RiskConstraints,
    StrategyBrief,
    StrategySpec,
    TradingRule,
)
from .strategy_data_sync import StrategyDataSync


class ProjectWorkflow:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create_kpi_version(
        self,
        trade_win_rate: float,
        annualized_return: float,
        max_drawdown_limit: float,
        notes: str = "",
    ) -> Path:
        now = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        version = KpiVersion(
            version_id=f"kpi-{now}",
            created_at=now,
            target=KpiTarget(
                trade_win_rate=trade_win_rate,
                annualized_return=annualized_return,
                max_drawdown_limit=max_drawdown_limit,
                notes=notes,
            ),
        )
        target = self.root / "inputs" / "kpi_versions" / f"{version.version_id}.json"
        write_json(target, version.to_dict())
        return target

    def create_strategy_brief(self, strategy_id: str, title: str, thesis: str) -> Path:
        brief = StrategyBrief(strategy_id=strategy_id, title=title, thesis=thesis)
        target = self.root / "strategies" / "generated" / f"{strategy_id}.json"
        write_json(target, brief.to_dict())
        return target

    def create_strategy_spec(
        self,
        strategy_id: str,
        spec_id: str,
        title_hint: str = "",
        market_inputs: Iterable[str] | None = None,
        fundamental_inputs: Iterable[str] | None = None,
        event_inputs: Iterable[str] | None = None,
        label_inputs: Iterable[str] | None = None,
        derived_features: Iterable[str] | None = None,
    ) -> Path:
        now = datetime.now().isoformat(timespec="seconds")
        features = [
            DerivedFeatureSpec(
                feature_name=name,
                formula=f"{name}()",
                notes="Stub feature definition generated from current architecture baseline.",
            )
            for name in (derived_features or [])
        ]
        spec = StrategySpec(
            spec_id=spec_id,
            strategy_id=strategy_id,
            version="v1",
            status="draft",
            derived_from_brief_id=title_hint or strategy_id,
            created_at=now,
            updated_at=now,
            market_inputs=list(market_inputs or []),
            fundamental_inputs=list(fundamental_inputs or []),
            event_inputs=list(event_inputs or []),
            label_inputs=list(label_inputs or []),
            derived_features=features,
            position_rules=PositionRules(
                position_sizing_method="fixed_slots",
                max_positions=5,
                min_positions=1,
                holding_period_hint="1-2 weeks",
                rebalance_frequency="daily",
                ranking_key="strategy_score",
            ),
            risk_constraints=RiskConstraints(
                max_drawdown_limit=0.15,
                max_single_position_weight=0.2,
            ),
            execution_timing=ExecutionTiming(),
            review_spec=ReviewSpec(
                required_metrics=["trade_win_rate", "annualized_return", "max_drawdown"]
            ),
        )
        target = self.root / "strategies" / "specs" / f"{spec.spec_id}.json"
        write_json(target, spec.to_dict())
        return target

    def create_review_stub(self, strategy_id: str) -> Path:
        target = self.root / "reports" / "reviews" / f"{strategy_id}-review.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "# Review Stub\n\n"
            f"- strategy_id: {strategy_id}\n"
            "- status: pending\n"
            "- reviewer: risk-reviewer\n"
            "- notes:\n",
            encoding="utf-8",
        )
        return target

    def plan_strategy_data_sync(
        self,
        spec: StrategySpec,
        available_items: Iterable[str] | None = None,
    ) -> Path:
        resolved_items = list(available_items or [])
        if not resolved_items:
            inventory_path = self.root / "configs" / "data_inventory.json"
            resolved_items = load_available_inventory_items(inventory_path)
        sync = StrategyDataSync(
            registry=DEFAULT_DEPENDENCY_REGISTRY,
            available_items=resolved_items,
        )
        result = sync.plan(spec)
        target = self.root / "reports" / "data_sync" / f"{spec.spec_id}-sync.json"
        write_json(target, result.to_dict())
        return target

    def run_base_incremental_ingest(
        self,
        source_dir: Path | None = None,
        sample_size: int = 50,
        constraints_dir: Path | None = None,
        stock_codes: Iterable[str] | None = None,
    ) -> Path:
        resolved_source = source_dir or Path.home() / "Downloads" / "stock_history"
        outputs = write_base_incremental_outputs(
            project_root=self.root,
            source_dir=resolved_source,
            sample_size=sample_size,
            constraints_dir=constraints_dir,
            stock_codes=stock_codes,
        )
        summary_path = outputs["summary"]
        self._refresh_changed_features(summary_path)
        return summary_path

    def run_bootstrap_ingest(
        self,
        source_dir: Path | None = None,
        limit_files: int | None = None,
    ) -> Path:
        resolved_source = source_dir or Path.home() / "Downloads" / "stock_history"
        result = run_bootstrap_ingest(resolved_source, limit_files=limit_files)
        target = self.root / "reports" / "ingestion" / "bootstrap_ingest_summary.json"
        write_json(target, result.to_dict())
        return target

    def run_daily_update(
        self,
        source_dir: Path | None = None,
        sample_size: int = 50,
        constraints_dir: Path | None = None,
        stock_codes: Iterable[str] | None = None,
    ) -> Path:
        summary_path = self.run_base_incremental_ingest(
            source_dir=source_dir,
            sample_size=sample_size,
            constraints_dir=constraints_dir,
            stock_codes=stock_codes,
        )
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        reports_dir = self.root / "reports" / "ingestion"
        history_dir = reports_dir / "daily_updates"
        history_dir.mkdir(parents=True, exist_ok=True)

        latest_path = reports_dir / "daily_update_latest.json"
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        archived_path = history_dir / f"daily_update_{timestamp}.json"

        write_json(latest_path, payload)
        write_json(archived_path, payload)
        return latest_path

    def run_feature_refresh(
        self,
        stock_codes: Iterable[str] | None = None,
        include_gap_diagnostics: bool = True,
    ) -> Path:
        result = run_feature_refresh(
            stock_codes=stock_codes,
            include_gap_diagnostics=include_gap_diagnostics,
        )
        target = self.root / "reports" / "features" / "feature_refresh_summary.json"
        write_json(target, result.to_dict())
        return target

    def run_data_quality_report(self) -> Path:
        result = build_data_quality_report()
        target = self.root / "reports" / "data_quality" / "latest.json"
        write_json(target, result.to_dict())
        return target

    def repair_normalized_sync(
        self,
        stock_codes: Iterable[str] | None = None,
        batch_size: int = 250,
    ) -> Path:
        pg = PostgresCli()
        pg.ensure_database()
        pg.ensure_schema()
        result = repair_normalized_hash_mismatches(
            pg,
            stock_codes=stock_codes,
            batch_size=batch_size,
        )
        target = self.root / "reports" / "data_quality" / "normalized_sync_repair_latest.json"
        write_json(target, result.to_dict())
        return target

    def run_market_context_refresh(
        self,
        stock_codes: Iterable[str] | None = None,
        top_n_attention: int = 100,
        attention_start_date: str | None = None,
        notice_start_date: str | None = None,
        context_start_date: str | None = "2025-01-01",
        theme_snapshot_date: str | None = None,
        include_industries: bool = True,
        include_concepts: bool = True,
        max_concepts: int = 60,
        max_industries: int | None = None,
    ) -> Path:
        result = refresh_market_context(
            stock_codes=stock_codes,
            top_n_attention=top_n_attention,
            attention_start_date=attention_start_date,
            notice_start_date=notice_start_date,
            context_start_date=context_start_date,
            theme_snapshot_date=theme_snapshot_date,
            include_industries=include_industries,
            include_concepts=include_concepts,
            max_concepts=max_concepts,
            max_industries=max_industries,
        )
        target = self.root / "reports" / "market_context" / "latest.json"
        write_json(target, result.to_dict())
        return target

    def run_backtest(
        self,
        spec_path: Path,
        start_date: str | None = None,
        end_date: str | None = None,
        initial_capital: float = 1_000_000.0,
    ) -> Path:
        spec = self.load_strategy_spec(spec_path)
        result = run_backtest(
            spec,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
        )
        target = self.root / "reports" / "backtests" / f"{spec.spec_id}-backtest.json"
        write_json(target, result.to_dict())
        return target

    def evaluate_backtest(
        self,
        backtest_path: Path,
        min_trade_win_rate: float = 0.80,
        min_annualized_return: float = 0.20,
        max_drawdown_limit: float = 0.30,
        min_sharpe: float = 2.0,
    ) -> Path:
        payload = json.loads(backtest_path.read_text(encoding="utf-8"))
        from .backtest_runner import BacktestResult, BacktestTrade

        result = BacktestResult(
            generated_at=payload["generated_at"],
            spec_id=payload["spec_id"],
            strategy_id=payload["strategy_id"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            trade_count=payload["trade_count"],
            trade_win_rate=payload["trade_win_rate"],
            annualized_return=payload["annualized_return"],
            total_return=payload["total_return"],
            max_drawdown=payload["max_drawdown"],
            sharpe=payload["sharpe"],
            average_holding_days=payload["average_holding_days"],
            equity_curve_points=payload["equity_curve_points"],
            notes=payload.get("notes", []),
            trades=[BacktestTrade(**item) for item in payload.get("trades", [])],
        )
        evaluation = evaluate_backtest_result(
            result,
            min_trade_win_rate=min_trade_win_rate,
            min_annualized_return=min_annualized_return,
            max_drawdown_limit=max_drawdown_limit,
            min_sharpe=min_sharpe,
        )
        target = self.root / "reports" / "evaluations" / f"{result.spec_id}-evaluation.json"
        write_json(target, evaluation.to_dict())
        return target

    def _refresh_changed_features(self, summary_path: Path) -> Path | None:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        execution = payload.get("execution") or {}
        changed_stock_codes = set(execution.get("changed_stock_codes") or [])
        constraints = execution.get("trading_constraints") or {}
        changed_stock_codes.update(constraints.get("changed_stock_codes") or [])

        if changed_stock_codes:
            feature_path = self.run_feature_refresh(stock_codes=sorted(changed_stock_codes))
            feature_payload = json.loads(feature_path.read_text(encoding="utf-8"))
        else:
            feature_path = None
            feature_payload = {
                "status": "no_changes",
                "notes": ["No changed stock codes required derived feature refresh."],
            }

        execution["feature_refresh"] = {
            "summary_path": str(feature_path) if feature_path else None,
            **feature_payload,
        }
        payload["execution"] = execution
        source_snapshot = payload.get("source_snapshot") or {}
        source_path = source_snapshot.get("source_path")
        if source_path:
            snapshot = inspect_stock_history(
                Path(source_path),
                sample_size=int(source_snapshot.get("sample_size") or 50),
            )
            pg = PostgresCli()
            pg.ensure_database()
            pg.ensure_schema()
            payload["inventory"] = build_data_inventory(
                snapshot,
                normalized_available_fields=load_normalized_available_fields(pg),
                feature_available_fields=load_feature_available_fields(pg),
            ).to_dict()
            write_json(self.root / "configs" / "data_inventory.json", payload["inventory"])
        write_json(summary_path, payload)
        return feature_path

    def load_strategy_spec(self, path: Path) -> StrategySpec:
        payload = json.loads(path.read_text(encoding="utf-8"))
        derived_features = [DerivedFeatureSpec(**item) for item in payload.get("derived_features", [])]
        filters = [TradingRule(**item) for item in payload.get("filters", [])]
        entry_rules = [TradingRule(**item) for item in payload.get("entry_rules", [])]
        exit_rules = [TradingRule(**item) for item in payload.get("exit_rules", [])]
        ranking_formula = (
            RankingFormula(**payload["ranking_formula"]) if payload.get("ranking_formula") else None
        )
        position_rules = (
            PositionRules(**payload["position_rules"]) if payload.get("position_rules") else None
        )
        risk_constraints = (
            RiskConstraints(**payload["risk_constraints"])
            if payload.get("risk_constraints")
            else None
        )
        execution_timing = ExecutionTiming(**payload.get("execution_timing", {}))
        review_spec = ReviewSpec(**payload.get("review_spec", {}))
        return StrategySpec(
            spec_id=payload["spec_id"],
            strategy_id=payload["strategy_id"],
            version=payload["version"],
            status=payload["status"],
            derived_from_brief_id=payload["derived_from_brief_id"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            market_inputs=payload.get("market_inputs", []),
            fundamental_inputs=payload.get("fundamental_inputs", []),
            event_inputs=payload.get("event_inputs", []),
            label_inputs=payload.get("label_inputs", []),
            derived_features=derived_features,
            filters=filters,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            ranking_formula=ranking_formula,
            position_rules=position_rules,
            risk_constraints=risk_constraints,
            execution_timing=execution_timing,
            review_spec=review_spec,
        )
