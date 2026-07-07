from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.dependency_registry import DEFAULT_DEPENDENCY_REGISTRY
from quant_agent_team.db import DatabaseConfig, PostgresCli
from quant_agent_team.feature_refresh import run_feature_refresh
from quant_agent_team.ingestion import (
    build_bootstrap_bundle,
    inspect_stock_history,
    run_base_incremental_ingest,
)
from quant_agent_team.lagging_status import load_free_source_unavailable_codes
from quant_agent_team.market_fetch import (
    DailyBar,
    _provider_attempt_limit,
    fetch_daily_bars_with_fallback,
    merge_market_rows,
    resolve_stock_fetch_start_date,
)
from quant_agent_team.strategy_data_sync import StrategyDataSync
from quant_agent_team.workflow import ProjectWorkflow


def _require_postgres(test_case: unittest.TestCase) -> None:
    """Skip the test unless a usable psql binary is resolvable on this machine."""
    psql = DatabaseConfig.from_env().psql_bin
    if Path(psql).exists() or shutil.which(str(psql)):
        return
    test_case.skipTest("PostgreSQL CLI is not available in the local environment.")


class WorkflowTest(unittest.TestCase):
    def test_provider_attempt_limit_uses_single_try_for_noisy_fallbacks(self) -> None:
        class Provider:
            def __init__(self, name: str) -> None:
                self.name = name

        self.assertEqual(_provider_attempt_limit(Provider("pytdx")), 1)
        self.assertEqual(_provider_attempt_limit(Provider("mootdx")), 1)
        self.assertEqual(_provider_attempt_limit(Provider("yfinance")), 1)
        self.assertEqual(_provider_attempt_limit(Provider("akshare")), 3)

    def test_fetch_daily_bars_with_fallback_limits_noisy_provider_retries(self) -> None:
        class NoisyProvider:
            name = "pytdx"

            def __init__(self) -> None:
                self.calls = 0

            def fetch_daily_bars(self, stock_code: str, start_date: str | None = None, end_date: str | None = None):
                self.calls += 1
                raise RuntimeError("socket timeout")

        class SuccessProvider:
            name = "akshare"

            def fetch_daily_bars(self, stock_code: str, start_date: str | None = None, end_date: str | None = None):
                return [
                    DailyBar(
                        stock_code=stock_code,
                        trade_date="2026-03-20",
                        close_price=10.0,
                        open_price=10.0,
                        high_price=10.0,
                        low_price=10.0,
                        volume=1000.0,
                        turnover=10000.0,
                    )
                ]

        noisy = NoisyProvider()
        rows, provider_name = fetch_daily_bars_with_fallback(
            "000001",
            providers=[noisy, SuccessProvider()],
        )
        self.assertEqual(noisy.calls, 1)
        self.assertEqual(provider_name, "akshare")
        self.assertEqual(rows[0].trade_date, "2026-03-20")

    def test_create_kpi_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            path = workflow.create_kpi_version(0.9, 0.2, 0.15, notes="test")
            self.assertTrue(path.exists())
            self.assertIn("kpi-", path.name)

    def test_create_strategy_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            path = workflow.create_strategy_brief("s1", "Demo", "Demo thesis")
            self.assertTrue(path.exists())
            self.assertIn("Demo thesis", path.read_text(encoding="utf-8"))

    def test_create_strategy_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            path = workflow.create_strategy_spec(
                strategy_id="s1",
                spec_id="spec-s1",
                market_inputs=["close_price_adj"],
                fundamental_inputs=["roe"],
                label_inputs=["industry_name"],
                derived_features=["ma_20"],
            )
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn('"spec_id": "spec-s1"', content)
            self.assertIn('"feature_name": "ma_20"', content)

    def test_plan_strategy_data_sync_with_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            spec_path = workflow.create_strategy_spec(
                strategy_id="s1",
                spec_id="spec-s1",
                market_inputs=["close_price_adj"],
                fundamental_inputs=["roe"],
                derived_features=["ma_20"],
            )
            spec = workflow.load_strategy_spec(spec_path)
            path = workflow.plan_strategy_data_sync(spec, available_items=["close_price_adj"])
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn('"ready_for_backtest": false', content)
            self.assertIn('"strategy_data_sync.fundamental_ingest"', content)
            self.assertIn('"feature_builder"', content)

    def test_write_base_ingest_plan(self) -> None:
        _require_postgres(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            source_dir = Path(tmpdir) / "seed"
            constraints_dir = Path(tmpdir) / "constraints"
            source_dir.mkdir(parents=True, exist_ok=True)
            constraints_dir.mkdir(parents=True, exist_ok=True)
            sample = source_dir / "000001.csv"
            sample.write_text(
                "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                "000001,2025-01-03,10,9,10,8,100,1000\n"
                "000001,2025-01-02,9,8,9,7,90,900\n",
                encoding="utf-8",
            )
            (constraints_dir / "000001.csv").write_text(
                "trade_date,adj_factor,is_suspended,is_st,limit_up_price,limit_down_price\n"
                "2025-01-03,1.1,false,true,11,9\n"
                "2025-01-02,1.0,false,false,10,8\n",
                encoding="utf-8",
            )
            path = workflow.run_base_incremental_ingest(
                source_dir=source_dir,
                sample_size=10,
                constraints_dir=constraints_dir,
            )
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn('"execution": {', content)
            self.assertIn('"feature_refresh": {', content)
            self.assertIn('"earliest_trade_date": "2025-01-02"', content)
            self.assertIn('"latest_trade_date": "2025-01-03"', content)
            inventory = (Path(tmpdir) / "configs" / "data_inventory.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"name": "close_price"', inventory)
            self.assertIn('"name": "close_price_adj"', inventory)
            self.assertIn('"source": "normalized_market_daily"', inventory)

    def test_plan_strategy_data_sync_uses_inventory_when_available_not_passed(self) -> None:
        _require_postgres(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow = ProjectWorkflow(root)
            source_dir = root / "seed"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "000001.csv").write_text(
                "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                "000001,2025-01-03,10,9,10,8,100,1000\n",
                encoding="utf-8",
            )
            workflow.run_base_incremental_ingest(source_dir=source_dir, sample_size=10)
            spec_path = workflow.create_strategy_spec(
                strategy_id="s3",
                spec_id="spec-s3",
                market_inputs=["close_price"],
                derived_features=["ma_20"],
            )
            spec = workflow.load_strategy_spec(spec_path)
            path = workflow.plan_strategy_data_sync(spec)
            content = path.read_text(encoding="utf-8")
            self.assertIn('"close_price"', content)
            self.assertIn('"ma_20"', content)
            self.assertIn('"ready_for_backtest": true', content)

    def test_feature_refresh_updates_inventory_for_strategy_data_sync(self) -> None:
        _require_postgres(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow = ProjectWorkflow(root)
            source_dir = root / "seed"
            source_dir.mkdir(parents=True, exist_ok=True)
            rows = [
                "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额",
            ]
            base = date(2025, 1, 1)
            for i in range(70, 0, -1):
                d = base + timedelta(days=i)
                rows.append(
                    f"000001,{d.isoformat()},{10 + i/100:.2f},{9 + i/100:.2f},{10.5 + i/100:.2f},{9.5 + i/100:.2f},{100000 + i},{1000000 + i}"
                )
            (source_dir / "000001.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

            workflow.run_base_incremental_ingest(source_dir=source_dir, sample_size=10)

            spec_path = workflow.create_strategy_spec(
                strategy_id="s4",
                spec_id="spec-s4",
                market_inputs=["close_price_adj"],
                derived_features=["ma_20"],
            )
            spec = workflow.load_strategy_spec(spec_path)
            path = workflow.plan_strategy_data_sync(spec)
            content = path.read_text(encoding="utf-8")
            self.assertIn('"ready_for_backtest": true', content)

    def test_run_daily_update_writes_latest_and_archived_summary(self) -> None:
        _require_postgres(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow = ProjectWorkflow(root)
            source_dir = root / "seed"
            source_dir.mkdir(parents=True, exist_ok=True)
            stock_code = f"test_{uuid4().hex[:8]}"
            (source_dir / f"{stock_code}.csv").write_text(
                "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                f"{stock_code},2025-01-03,10,9,10,8,100,1000\n",
                encoding="utf-8",
            )

            path = workflow.run_daily_update(source_dir=source_dir, sample_size=10)

            self.assertEqual(path, root / "reports" / "ingestion" / "daily_update_latest.json")
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn('"status": "success"', content)
            self.assertIn('"feature_refresh": {', content)

            history_dir = root / "reports" / "ingestion" / "daily_updates"
            archived = list(history_dir.glob("daily_update_*.json"))
            self.assertEqual(len(archived), 1)
            self.assertIn('"execution": {', archived[0].read_text(encoding="utf-8"))

    def test_load_free_source_unavailable_codes_includes_recent_2025_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            snapshot = root / "reports" / "data_quality" / "lagging_backfill_status.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(
                json.dumps(
                    {
                        "recent_2026_remaining": {
                            "symbols": [{"stock_code": "300379", "latest_trade_date": "2026-01-23"}]
                        },
                        "recent_2025_tail_remaining": {
                            "symbols": [{"stock_code": "600898", "latest_trade_date": "2025-01-10"}]
                        },
                        "stale_2024_remaining": {
                            "symbols": [{"stock_code": "000005", "latest_trade_date": "2024-03-05"}]
                        },
                        "stale_2020_2023_remaining": {
                            "symbols": [{"stock_code": "000018", "latest_trade_date": "2020-01-06"}]
                        },
                        "historical_end_before_2020_remaining": {
                            "symbols": [{"stock_code": "000043", "latest_trade_date": "2019-12-13"}]
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_free_source_unavailable_codes(root),
                {"300379", "600898", "000005", "000018", "000043"},
            )


class RegistryTest(unittest.TestCase):
    def test_default_registry_contains_base_and_strategy_driven_dependencies(self) -> None:
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("close_price_adj"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("roe"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("turnover"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ma_5"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ma_10"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ma_20"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ma_60"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("avg_volume_20d"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("avg_turnover_20d"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("volume_ratio_20d"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ret_1d"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ret_5d"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("ret_20d"))
        self.assertTrue(DEFAULT_DEPENDENCY_REGISTRY.contains("volatility_20d"))

    def test_strategy_data_sync_resolves_transitive_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            spec_path = workflow.create_strategy_spec(
                strategy_id="s2",
                spec_id="spec-s2",
                derived_features=["ma_20"],
            )
            spec = workflow.load_strategy_spec(spec_path)
            sync = StrategyDataSync(available_items=["close_price_adj", "ma_20"])
            result = sync.plan(spec)
            self.assertTrue(result.ready_for_backtest)
            self.assertIn("ma_20", result.satisfied_requirements)
            self.assertIn("close_price_adj", result.satisfied_requirements)

    def test_load_strategy_spec_preserves_rules_and_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spec_path = root / "strategies" / "specs" / "spec-s4.json"
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text(
                json.dumps(
                    {
                        "spec_id": "spec-s4",
                        "strategy_id": "s4",
                        "version": "v1",
                        "status": "data_ready",
                        "derived_from_brief_id": "s4",
                        "created_at": "2026-03-26T10:00:00",
                        "updated_at": "2026-03-26T10:00:00",
                        "market_inputs": ["close_price_adj", "volume"],
                        "fundamental_inputs": [],
                        "event_inputs": [],
                        "label_inputs": [],
                        "derived_features": [
                            {
                                "feature_name": "ma_20",
                                "formula": "rolling_mean(close_price_adj, 20)",
                                "dependencies": ["close_price_adj"],
                                "window": 20,
                                "output_type": "numeric",
                                "notes": "",
                            }
                        ],
                        "filters": [
                            {
                                "rule_id": "f1",
                                "logic": "AND",
                                "conditions": [
                                    {"field": "close_price_adj", "operator": ">", "value_from": "ma_20"}
                                ],
                                "notes": "demo filter",
                            }
                        ],
                        "entry_rules": [
                            {
                                "rule_id": "e1",
                                "logic": "AND",
                                "conditions": [
                                    {"field": "volume_ratio_20d", "operator": ">=", "value": 1.2}
                                ],
                                "notes": "demo entry",
                            }
                        ],
                        "exit_rules": [
                            {
                                "rule_id": "x1",
                                "logic": "OR",
                                "conditions": [
                                    {"field": "close_price_adj", "operator": "<", "value_from": "ma_10"}
                                ],
                                "notes": "demo exit",
                            }
                        ],
                        "ranking_formula": {
                            "score_name": "strategy_score",
                            "formula": "ret_20d + volume_ratio_20d",
                            "components": ["ret_20d", "volume_ratio_20d"],
                            "sort_direction": "desc",
                            "notes": "demo ranking",
                        },
                        "position_rules": {
                            "position_sizing_method": "fixed_slots",
                            "max_positions": 5,
                            "min_positions": 1,
                            "holding_period_hint": "1-2 weeks",
                            "rebalance_frequency": "weekly",
                            "ranking_key": "strategy_score",
                        },
                        "risk_constraints": {
                            "max_drawdown_limit": 0.15,
                            "max_single_position_weight": 0.2,
                            "exclude_st": True,
                            "exclude_suspended": True,
                            "exclude_limit_up": True,
                            "exclude_limit_down": False,
                        },
                        "execution_timing": {
                            "signal_generation_time": "after_close",
                            "trade_reference_time": "next_open_reference",
                            "data_cutoff_rule": "use only data available by market close",
                        },
                        "review_spec": {
                            "required_metrics": ["trade_win_rate"],
                            "review_focus": ["win_rate_stability"],
                            "known_risks": [],
                            "failure_modes": [],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            workflow = ProjectWorkflow(root)
            spec = workflow.load_strategy_spec(spec_path)
            self.assertEqual(len(spec.filters), 1)
            self.assertEqual(spec.filters[0].rule_id, "f1")
            self.assertEqual(len(spec.entry_rules), 1)
            self.assertEqual(spec.exit_rules[0].logic, "OR")
            self.assertIsNotNone(spec.ranking_formula)
            self.assertEqual(spec.ranking_formula.score_name, "strategy_score")


class IngestionTest(unittest.TestCase):
    def test_inspect_stock_history_and_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            seed = root / "seed"
            seed.mkdir(parents=True, exist_ok=True)
            (seed / "000001.csv").write_text(
                "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                "000001,2025-01-03,10,9,10,8,100,1000\n"
                "000001,2025-01-02,9,8,9,7,90,900\n",
                encoding="utf-8",
            )
            snapshot = inspect_stock_history(seed, sample_size=10)
            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(snapshot.file_count, 1)
            self.assertEqual(snapshot.earliest_trade_date, "2025-01-02")
            self.assertEqual(snapshot.latest_trade_date, "2025-01-03")

            bundle = root / "bundle.csv"
            meta = build_bootstrap_bundle(seed, bundle, limit_files=10)
            self.assertEqual(meta["files_processed"], 1)
            self.assertEqual(meta["rows_prepared"], 2)
            content = bundle.read_text(encoding="utf-8")
            self.assertIn("raw_line_hash", content)
            self.assertIn("raw_payload", content)

    def test_merge_market_rows_overwrites_same_date_and_keeps_desc_order(self) -> None:
        merged = merge_market_rows(
            [
                DailyBar("000001", "2025-01-03", 10, 9, 10, 8, 100, 1000),
                DailyBar("000001", "2025-01-02", 9, 8, 9, 7, 90, 900),
            ],
            [
                DailyBar("000001", "2025-01-06", 11, 10, 11, 9, 110, 1100),
                DailyBar("000001", "2025-01-03", 12, 11, 12, 10, 120, 1200),
            ],
        )
        self.assertEqual([row.trade_date for row in merged], ["2025-01-06", "2025-01-03", "2025-01-02"])
        self.assertEqual(merged[1].close_price, 12)

    def test_resolve_stock_fetch_start_date_uses_stock_latest_trade_date(self) -> None:
        rows = [
            DailyBar("000001", "2025-01-06", 11, 10, 11, 9, 110, 1100),
            DailyBar("000001", "2025-01-03", 10, 9, 10, 8, 100, 1000),
            DailyBar("000001", "2025-01-02", 9, 8, 9, 7, 90, 900),
        ]
        self.assertEqual(resolve_stock_fetch_start_date(rows), "2025-01-07")
        self.assertEqual(
            resolve_stock_fetch_start_date(rows, explicit_start_date="2025-01-01"),
            "2025-01-01",
        )
        self.assertIsNone(resolve_stock_fetch_start_date([]))

    def test_fetch_daily_bars_with_fallback_uses_later_provider_when_earlier_returns_empty(self) -> None:
        class EmptyProvider:
            name = "empty"

            def fetch_daily_bars(
                self,
                stock_code: str,
                start_date: str | None = None,
                end_date: str | None = None,
            ) -> list[DailyBar]:
                return []

        class WorkingProvider:
            name = "working"

            def fetch_daily_bars(
                self,
                stock_code: str,
                start_date: str | None = None,
                end_date: str | None = None,
            ) -> list[DailyBar]:
                return [
                    DailyBar(stock_code, "2025-01-03", 10, 9, 10, 8, 100, 1000),
                    DailyBar(stock_code, "2025-01-02", 9, 8, 9, 7, 90, 900),
                ]

        rows, provider = fetch_daily_bars_with_fallback(
            "000001",
            providers=[EmptyProvider(), WorkingProvider()],
            max_attempts=1,
        )
        self.assertEqual(provider, "working")
        self.assertEqual([row.trade_date for row in rows], ["2025-01-03", "2025-01-02"])

    def test_fetch_daily_bars_with_fallback_normalizes_lot_volume_to_share_volume(self) -> None:
        class LotVolumeProvider:
            name = "lot-volume"

            def fetch_daily_bars(
                self,
                stock_code: str,
                start_date: str | None = None,
                end_date: str | None = None,
            ) -> list[DailyBar]:
                return [
                    DailyBar(
                        stock_code,
                        "2026-03-09",
                        10.76,
                        10.79,
                        10.82,
                        10.74,
                        835892.0,
                        900716851.39,
                    )
                ]

        rows, provider = fetch_daily_bars_with_fallback(
            "000001",
            providers=[LotVolumeProvider()],
            max_attempts=1,
        )

        self.assertEqual(provider, "lot-volume")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].volume, 83589200.0)
        self.assertEqual(rows[0].turnover, 900716851.39)

    def test_run_base_incremental_ingest_real_incremental_chain(self) -> None:
        psql_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/psql")
        createdb_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/createdb")
        if not psql_bin.exists() or not createdb_bin.exists():
            self.skipTest("PostgreSQL CLI is not available in the local environment.")

        db_name = f"quant_agent_team_test_{uuid4().hex[:8]}"
        config = DatabaseConfig(
            db_url=f"postgresql:///{db_name}?host=/tmp",
            admin_db_url="postgresql:///postgres?host=/tmp",
            psql_bin=psql_bin,
            createdb_bin=createdb_bin,
        )
        db = PostgresCli(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                root = Path(tmpdir)
                seed = root / "seed"
                constraints = root / "constraints"
                seed.mkdir(parents=True, exist_ok=True)
                constraints.mkdir(parents=True, exist_ok=True)
                source = seed / "000001.csv"
                source.write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2025-01-03,10,9,10,8,100,1000\n"
                    "000001,2025-01-02,9,8,9,7,90,900\n",
                    encoding="utf-8",
                )
                (constraints / "000001.csv").write_text(
                    "trade_date,adj_factor,is_suspended,is_st,limit_up_price,limit_down_price\n"
                    "2025-01-03,1.1,false,true,11,9\n"
                    "2025-01-02,1.0,false,false,10,8\n",
                    encoding="utf-8",
                )

                first = run_base_incremental_ingest(
                    seed,
                    sample_size=10,
                    constraints_dir=constraints,
                    db=db,
                )
                self.assertEqual(first.status, "success")
                self.assertEqual(first.execution["files_changed"], 1)
                self.assertEqual(first.execution["changed_stock_codes"], ["000001"])
                self.assertEqual(first.execution["inserted_rows"], 2)
                self.assertEqual(first.execution["conflict_rows"], 0)
                self.assertEqual(first.execution["normalized_rows_synced"], 2)
                self.assertEqual(first.execution["trading_constraints"]["files_changed"], 1)
                self.assertEqual(db.run_sql("SELECT COUNT(*) FROM raw_market_daily;").strip(), "2")
                self.assertEqual(db.run_sql("SELECT COUNT(*) FROM raw_trading_constraints_daily;").strip(), "2")
                self.assertEqual(db.run_sql("SELECT COUNT(*) FROM normalized_market_daily;").strip(), "2")
                self.assertEqual(
                    db.run_sql(
                        """
SELECT close_price_adj
FROM normalized_market_daily
WHERE stock_code = '000001' AND trade_date = '2025-01-03';
"""
                    ).strip(),
                    "11.00",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT is_st, limit_up_price
FROM normalized_market_daily
WHERE stock_code = '000001' AND trade_date = '2025-01-03';
"""
                    ).strip(),
                    "t|11.0",
                )

                second = run_base_incremental_ingest(
                    seed,
                    sample_size=10,
                    constraints_dir=constraints,
                    db=db,
                )
                self.assertEqual(second.status, "no_changes")
                self.assertEqual(second.execution["files_changed"], 0)
                self.assertEqual(second.execution["changed_stock_codes"], [])
                self.assertEqual(second.execution["inserted_rows"], 0)
                self.assertEqual(second.execution["normalized_rows_synced"], 0)

                source.write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2025-01-06,11,10,11,9,110,1100\n"
                    "000001,2025-01-03,10,9,10,8,100,1000\n"
                    "000001,2025-01-02,9,8,9,7,90,900\n",
                    encoding="utf-8",
                )
                third = run_base_incremental_ingest(
                    seed,
                    sample_size=10,
                    constraints_dir=constraints,
                    db=db,
                )
                self.assertEqual(third.status, "success")
                self.assertEqual(third.execution["files_changed"], 1)
                self.assertEqual(third.execution["changed_stock_codes"], ["000001"])
                self.assertEqual(third.execution["rows_prepared"], 1)
                self.assertEqual(third.execution["inserted_rows"], 1)
                self.assertEqual(third.execution["unchanged_rows"], 0)
                self.assertEqual(third.execution["normalized_rows_synced"], 3)
                self.assertEqual(db.run_sql("SELECT COUNT(*) FROM raw_market_daily;").strip(), "3")
                self.assertEqual(db.run_sql("SELECT COUNT(*) FROM normalized_market_daily;").strip(), "3")
                self.assertEqual(
                    db.run_sql(
                        """
SELECT latest_trade_date, row_count
FROM ingest_source_file_state
WHERE stock_code = '000001'
  AND source_path LIKE '%/seed/000001.csv';
"""
                    ).strip(),
                    "2025-01-06|3",
                )

                source.write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2025-01-06,11,10,11,9,110,1100\n"
                    "000001,2025-01-03,12,9,12,8,120,1200\n"
                    "000001,2025-01-02,9,8,9,7,90,900\n",
                    encoding="utf-8",
                )
                (constraints / "000001.csv").write_text(
                    "trade_date,adj_factor,is_suspended,is_st,limit_up_price,limit_down_price\n"
                    "2025-01-06,1.2,false,false,12,10\n"
                    "2025-01-03,1.1,false,true,11,9\n"
                    "2025-01-02,1.0,false,false,10,8\n",
                    encoding="utf-8",
                )
                fourth = run_base_incremental_ingest(
                    seed,
                    sample_size=10,
                    constraints_dir=constraints,
                    db=db,
                )
                self.assertEqual(fourth.status, "completed_with_conflicts")
                self.assertEqual(fourth.execution["conflict_rows"], 1)
                self.assertEqual(fourth.execution["normalized_rows_synced"], 3)
                self.assertEqual(fourth.execution["trading_constraints"]["files_changed"], 1)
                self.assertEqual(
                    db.run_sql("SELECT COUNT(*) FROM ingest_conflict_log;").strip(),
                    "1",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT close_price_adj, adj_factor
FROM normalized_market_daily
WHERE stock_code = '000001' AND trade_date = '2025-01-06';
"""
                    ).strip(),
                    "13.20|1.2",
                )

                db.run_sql("DELETE FROM raw_trading_constraints_daily;", capture=False)
                db.run_sql(
                    """
UPDATE normalized_market_daily
SET close_price_adj = close_price,
    adj_factor = 1.0,
    is_suspended = NULL,
    is_st = NULL,
    limit_up_price = NULL,
    limit_down_price = NULL;
""",
                    capture=False,
                )

                feature_source = root / "feature_seed"
                feature_source.mkdir(parents=True, exist_ok=True)
                prices = []
                base_date = date(2025, 1, 1)
                for index in range(1, 66):
                    trade_date = (base_date + timedelta(days=index - 1)).isoformat()
                    prices.append(
                        f"000002,{trade_date},{index},{index},{index},{index},{index * 10},{index * 100}\n"
                    )
                (feature_source / "000002.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    + "".join(reversed(prices)),
                    encoding="utf-8",
                )
                run_base_incremental_ingest(feature_source, sample_size=30, db=db)
                first_refresh = run_feature_refresh(db=db)
                self.assertEqual(first_refresh.status, "success")
                self.assertEqual(first_refresh.expected_unavailable_stock_dates, 62)
                self.assertEqual(first_refresh.missing_refresh_stock_dates, 0)
                self.assertEqual(first_refresh.stock_codes_with_missing_refresh, 0)
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ma_5
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-05';
"""
                    ).strip(),
                    "3.0",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ma_10
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-10';
"""
                    ).strip(),
                    "5.5",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ma_20
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-20';
"""
                    ).strip(),
                    "10.5",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT avg_volume_20d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-20';
"""
                    ).strip(),
                    "105.0",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT avg_turnover_20d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-20';
"""
                    ).strip(),
                    "1050.0",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT volume_ratio_20d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-20';
"""
                    ).strip(),
                    "1.9047619047619047",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ret_1d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-03';
"""
                    ).strip(),
                    "0.5",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ret_5d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-06';
"""
                    ).strip(),
                    "5.0",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ret_20d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-21';
"""
                    ).strip(),
                    "20.0",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT volatility_20d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-21';
"""
                    ).strip(),
                    "0.21782753635431476",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT momentum_20d
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-01-20';
"""
                    ).strip(),
                    "19.0",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ma_60
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-03-01';
"""
                    ).strip(),
                    "30.5",
                )

                prices.extend(
                    [
                        "000002,2025-03-07,66,66,66,66,660,6600\n",
                        "000002,2025-03-08,67,67,67,67,670,6700\n",
                    ]
                )
                (feature_source / "000002.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    + "".join(reversed(prices)),
                    encoding="utf-8",
                )
                run_base_incremental_ingest(feature_source, sample_size=40, db=db)
                second_refresh = run_feature_refresh(db=db)
                self.assertEqual(second_refresh.status, "success")
                self.assertEqual(
                    db.run_sql(
                        """
SELECT COUNT(ma_20)
FROM research_feature_daily
WHERE stock_code = '000002';
"""
                    ).strip(),
                    "48",
                )
                self.assertEqual(
                    db.run_sql(
                        """
SELECT ma_20
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-03-08';
"""
                    ).strip(),
                    "57.5",
                )
                db.run_sql(
                    """
DELETE FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-03-05';
""",
                    capture=False,
                )
                third_refresh = run_feature_refresh(db=db, stock_codes=["000002"])
                self.assertEqual(third_refresh.status, "success")
                self.assertEqual(third_refresh.expected_unavailable_stock_dates, 59)
                self.assertEqual(third_refresh.missing_refresh_stock_dates, 0)
                self.assertEqual(
                    db.run_sql(
                        """
SELECT COUNT(ma_20)
FROM research_feature_daily
WHERE stock_code = '000002'
  AND trade_date = '2025-03-05';
"""
                    ).strip(),
                    "1",
                )
            finally:
                db.run_admin_sql(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);", capture=False)

    def test_run_feature_refresh_uses_trading_day_lookback_for_ma60(self) -> None:
        psql_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/psql")
        createdb_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/createdb")
        if not psql_bin.exists() or not createdb_bin.exists():
            self.skipTest("PostgreSQL CLI is not available in the local environment.")

        db_name = f"quant_agent_team_test_{uuid4().hex[:8]}"
        config = DatabaseConfig(
            db_url=f"postgresql:///{db_name}?host=/tmp",
            admin_db_url="postgresql:///postgres?host=/tmp",
            psql_bin=psql_bin,
            createdb_bin=createdb_bin,
        )
        db = PostgresCli(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                root = Path(tmpdir)
                source_dir = root / "feature_seed"
                source_dir.mkdir(parents=True, exist_ok=True)

                business_dates = []
                current = date(2025, 10, 1)
                while len(business_dates) < 90:
                    if current.weekday() < 5:
                        business_dates.append(current)
                    current += timedelta(days=1)

                prices = []
                for index, trade_date in enumerate(business_dates, start=1):
                    prices.append(
                        f"688693,{trade_date.isoformat()},{index},{index},{index},{index},{index * 100},{index * 1000}\n"
                    )

                (source_dir / "688693.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    + "".join(reversed(prices)),
                    encoding="utf-8",
                )

                run_base_incremental_ingest(source_dir, sample_size=100, db=db)
                first_refresh = run_feature_refresh(db=db)
                self.assertEqual(first_refresh.status, "success")

                target_date = business_dates[70].isoformat()
                db.run_sql(
                    f"""
UPDATE research_feature_daily
SET ma_60 = NULL
WHERE stock_code = '688693'
  AND trade_date = '{target_date}'::date;
""",
                    capture=False,
                )

                second_refresh = run_feature_refresh(db=db, stock_codes=["688693"])
                self.assertEqual(second_refresh.status, "success")
                self.assertEqual(second_refresh.missing_refresh_stock_dates, 0)
                self.assertEqual(
                    db.run_sql(
                        f"""
SELECT ma_60 IS NOT NULL
FROM research_feature_daily
WHERE stock_code = '688693'
  AND trade_date = '{target_date}'::date;
"""
                    ).strip(),
                    "t",
                )
            finally:
                db.run_admin_sql(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);", capture=False)

    def test_run_base_incremental_ingest_ignores_near_equal_volume_rounding(self) -> None:
        psql_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/psql")
        createdb_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/createdb")
        if not psql_bin.exists() or not createdb_bin.exists():
            self.skipTest("PostgreSQL CLI is not available in the local environment.")

        db_name = f"quant_agent_team_test_{uuid4().hex[:8]}"
        config = DatabaseConfig(
            db_url=f"postgresql:///{db_name}?host=/tmp",
            admin_db_url="postgresql:///postgres?host=/tmp",
            psql_bin=psql_bin,
            createdb_bin=createdb_bin,
        )
        db = PostgresCli(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                root = Path(tmpdir)
                seed = root / "seed"
                seed.mkdir(parents=True, exist_ok=True)
                source = seed / "000001.csv"
                source.write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2026-03-10,10.81,10.77,10.81,10.73,79011168,850573535.93\n",
                    encoding="utf-8",
                )

                first = run_base_incremental_ingest(seed, sample_size=10, db=db)
                self.assertEqual(first.status, "success")
                self.assertEqual(first.execution["conflict_rows"], 0)

                source.write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2026-03-10,10.81,10.77,10.81,10.73,79011200,850573535.93\n",
                    encoding="utf-8",
                )

                second = run_base_incremental_ingest(seed, sample_size=10, db=db)
                self.assertEqual(second.status, "success")
                self.assertEqual(second.execution["conflict_rows"], 0)
                self.assertEqual(db.run_sql("SELECT COUNT(*) FROM ingest_conflict_log;").strip(), "0")
            finally:
                db.run_admin_sql(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);", capture=False)

    def test_run_base_incremental_ingest_can_target_selected_stock_codes(self) -> None:
        psql_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/psql")
        createdb_bin = Path("/opt/homebrew/Cellar/postgresql@17/17.9/bin/createdb")
        if not psql_bin.exists() or not createdb_bin.exists():
            self.skipTest("PostgreSQL CLI is not available in the local environment.")

        db_name = f"quant_agent_team_test_{uuid4().hex[:8]}"
        config = DatabaseConfig(
            db_url=f"postgresql:///{db_name}?host=/tmp",
            admin_db_url="postgresql:///postgres?host=/tmp",
            psql_bin=psql_bin,
            createdb_bin=createdb_bin,
        )
        db = PostgresCli(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                root = Path(tmpdir)
                seed = root / "seed"
                seed.mkdir(parents=True, exist_ok=True)
                (seed / "000001.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2026-03-10,10.81,10.77,10.81,10.73,79011168,850573535.93\n",
                    encoding="utf-8",
                )
                (seed / "000002.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000002,2026-03-10,4.67,4.66,4.69,4.65,63955629,298634048.83\n",
                    encoding="utf-8",
                )

                first = run_base_incremental_ingest(seed, sample_size=10, db=db)
                self.assertEqual(first.execution["files_changed"], 2)

                (seed / "000001.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000001,2026-03-10,10.81,10.77,10.81,10.73,79011200,850573535.93\n",
                    encoding="utf-8",
                )
                (seed / "000002.csv").write_text(
                    "股票代码,交易日期,收盘价,开盘价,最高价,最低价,成交量,成交额\n"
                    "000002,2026-03-10,4.67,4.66,4.69,4.65,63955700,298634048.83\n",
                    encoding="utf-8",
                )

                second = run_base_incremental_ingest(
                    seed,
                    sample_size=10,
                    stock_codes=["000001"],
                    db=db,
                )
                self.assertEqual(second.execution["files_scanned"], 1)
                self.assertEqual(second.execution["files_changed"], 1)
                self.assertEqual(second.execution["changed_stock_codes"], ["000001"])
            finally:
                db.run_admin_sql(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);", capture=False)

    def test_run_daily_update_can_target_selected_stock_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow = ProjectWorkflow(root)
            seed = root / "seed"
            seed.mkdir(parents=True, exist_ok=True)
            summary_path = root / "reports" / "ingestion" / "base_incremental_summary.json"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps({"execution": {"files_scanned": 1, "files_changed": 1, "changed_stock_codes": ["000001"]}}),
                encoding="utf-8",
            )

            with mock.patch.object(ProjectWorkflow, "run_base_incremental_ingest", return_value=summary_path) as patched:
                latest_path = workflow.run_daily_update(
                    source_dir=seed,
                    sample_size=10,
                    stock_codes=["000001"],
                )

            patched.assert_called_once_with(
                source_dir=seed,
                sample_size=10,
                constraints_dir=None,
                stock_codes=["000001"],
            )
            payload = json.loads(latest_path.read_text(encoding="utf-8"))
            execution = payload.get("execution") or {}
            self.assertEqual(execution.get("files_scanned"), 1)
            self.assertEqual(execution.get("files_changed"), 1)
            self.assertEqual(execution.get("changed_stock_codes"), ["000001"])


if __name__ == "__main__":
    unittest.main()
