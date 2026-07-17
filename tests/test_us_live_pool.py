from pathlib import Path
import sys
import tempfile
import unittest

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_live_pool import (
    _validate_outputs,
    build_latest_holdings_from_candidates,
    enrich_strategies_with_live_metrics,
    filter_live_outperformers,
    select_live_pool,
    write_live_pool,
)


class UsLivePoolTest(unittest.TestCase):
    def test_select_live_pool_sorts_and_filters_to_worthy_checked_strategies(self) -> None:
        rolling = pd.DataFrame(
            [
                {"candidate_id": "low", "ir": 1.0, "excess_return": 2.0, "mdd": 0.1, "top_n": 10, "rebalance_days": 20},
                {"candidate_id": "high", "ir": 2.0, "excess_return": 1.0, "mdd": 0.2, "top_n": 10, "rebalance_days": 20},
            ]
        )
        random_checks = pd.DataFrame([{"candidate_id": "high", "pvalue_ir": 0.01, "pvalue_excess": 0.01, "deflated_ir_z": 2.5}])

        selected = select_live_pool(rolling, random_checks, top_n=2)

        self.assertEqual(selected["candidate_id"].tolist(), ["high"])
        self.assertEqual(selected["随机检验状态"].tolist(), ["已完成随机检验"])

    def test_select_live_pool_rejects_holdings_above_twenty_except_allowed_sizes(self) -> None:
        rolling = pd.DataFrame(
            [
                {"candidate_id": "n10", "ir": 2.0, "excess_return": 1.0, "mdd": 0.2, "top_n": 10, "rebalance_days": 20},
                {"candidate_id": "n20", "ir": 1.9, "excess_return": 1.0, "mdd": 0.2, "top_n": 20, "rebalance_days": 20},
                {"candidate_id": "n30", "ir": 3.0, "excess_return": 2.0, "mdd": 0.1, "top_n": 30, "rebalance_days": 20},
            ]
        )
        random_checks = pd.DataFrame(
            [
                {"candidate_id": "n10", "top_n": 10, "rebalance_days": 20, "pvalue_ir": 0.01, "pvalue_excess": 0.01, "deflated_ir_z": 2.5},
                {"candidate_id": "n20", "top_n": 20, "rebalance_days": 20, "pvalue_ir": 0.01, "pvalue_excess": 0.01, "deflated_ir_z": 2.5},
                {"candidate_id": "n30", "top_n": 30, "rebalance_days": 20, "pvalue_ir": 0.01, "pvalue_excess": 0.01, "deflated_ir_z": 2.5},
            ]
        )

        selected = select_live_pool(rolling, random_checks, top_n=None)

        self.assertEqual(selected["candidate_id"].tolist(), ["n10", "n20"])
        self.assertEqual(selected["持仓数量"].tolist(), [10, 20])

    def test_enrich_strategies_handles_empty_live_metrics(self) -> None:
        strategies = pd.DataFrame(columns=["策略编号", "candidate_id"])
        live_metrics = pd.DataFrame()

        enriched = enrich_strategies_with_live_metrics(strategies, live_metrics)

        self.assertTrue(enriched.empty)
        self.assertIn("入库状态", enriched.columns)

    def test_filter_live_outperformers_removes_nonpositive_excess_and_holdings(self) -> None:
        strategies = pd.DataFrame(
            [
                {"策略编号": "策略一", "candidate_id": "keep", "实盘超基准收益": 0.01},
                {"策略编号": "策略二", "candidate_id": "drop_negative", "实盘超基准收益": -0.01},
                {"策略编号": "策略三", "candidate_id": "drop_flat", "实盘超基准收益": 0.0},
            ]
        )
        holdings = pd.DataFrame(
            [
                {"策略编号": "策略一", "股票代码": "AAA"},
                {"策略编号": "策略二", "股票代码": "BBB"},
                {"策略编号": "策略三", "股票代码": "CCC"},
            ]
        )

        kept_strategies, kept_holdings = filter_live_outperformers(strategies, holdings)

        self.assertEqual(kept_strategies["candidate_id"].tolist(), ["keep"])
        self.assertEqual(kept_holdings["股票代码"].tolist(), ["AAA"])

    def test_validate_outputs_allows_zero_after_live_outperformance_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "research.duckdb"
            report_path = Path(tmp) / "report.md"
            strategies = pd.DataFrame(columns=["run_id", "策略编号"])
            holdings = pd.DataFrame(columns=["run_id", "策略编号", "股票代码"])
            report_path.write_text("# 空批次\n\n本批没有策略跑赢基准。", encoding="utf-8")

            write_live_pool(db_path, run_id="r_zero", strategies=strategies, holdings=holdings)

            _validate_outputs(db_path, "r_zero", report_path, strategies, holdings)

    def test_write_live_pool_replaces_same_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "research.duckdb"
            strategies = pd.DataFrame(
                [{"run_id": "r1", "策略编号": "策略一", "candidate_id": "s1", "监控状态": "待人工审核，未进入正式监控"}]
            )
            holdings = pd.DataFrame(
                [{"run_id": "r1", "策略编号": "策略一", "股票代码": "AAPL", "目标权重": 1.0}]
            )

            write_live_pool(db_path, run_id="r1", strategies=strategies, holdings=holdings)
            write_live_pool(db_path, run_id="r1", strategies=strategies, holdings=holdings)

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                self.assertEqual(con.execute("select count(*) from us_live_pool_strategies").fetchone()[0], 1)
                self.assertEqual(con.execute("select count(*) from us_live_pool_holdings").fetchone()[0], 1)
            finally:
                con.close()

    def test_empty_live_pool_batch_does_not_shrink_existing_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "research.duckdb"
            strategies = pd.DataFrame(
                [{"run_id": "r1", "绛栫暐缂栧彿": "绛栫暐涓€", "candidate_id": "s1", "top_n_numeric": 5}]
            )
            holdings = pd.DataFrame(
                [{"run_id": "r1", "绛栫暐缂栧彿": "绛栫暐涓€", "鑲＄エ浠ｇ爜": "AAPL", "鐩爣鏉冮噸": 1.0}]
            )
            empty_strategies = pd.DataFrame(columns=["run_id", "入库状态"])
            empty_holdings = pd.DataFrame(columns=["run_id"])

            write_live_pool(db_path, run_id="r1", strategies=strategies, holdings=holdings)
            write_live_pool(db_path, run_id="r2", strategies=empty_strategies, holdings=empty_holdings)

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                columns = [row[1] for row in con.execute("pragma table_info('us_live_pool_strategies')").fetchall()]
                self.assertIn("candidate_id", columns)
                self.assertIn("top_n_numeric", columns)
                self.assertEqual(con.execute("select count(*) from us_live_pool_strategies").fetchone()[0], 1)
            finally:
                con.close()

    def test_build_latest_holdings_from_candidates_generates_each_strategy_basket(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "策略编号": "策略一",
                    "candidate_id": "s1",
                    "策略类型": "均衡回调型",
                    "持仓数量": 2,
                }
            ]
        )
        candidates = pd.DataFrame([{"candidate_id": "s1", "weights": '{"x": 1.0}'}])
        latest_panel = pd.DataFrame(
            [
                {"symbol": "AAA", "trade_date": "2026-07-10", "score_x": 2.0},
                {"symbol": "BBB", "trade_date": "2026-07-10", "score_x": 1.0},
                {"symbol": "CCC", "trade_date": "2026-07-10", "score_x": 0.0},
            ]
        )

        holdings = build_latest_holdings_from_candidates(strategies, candidates, latest_panel)

        self.assertEqual(holdings["股票代码"].tolist(), ["AAA", "BBB"])
        self.assertAlmostEqual(float(holdings["目标权重"].sum()), 1.0)
        self.assertEqual(holdings["策略编号"].tolist(), ["策略一", "策略一"])


if __name__ == "__main__":
    unittest.main()
