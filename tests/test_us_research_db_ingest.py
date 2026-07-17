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

from us_research_db_ingest import _read_markdown_table, ingest_strategy_research


class UsResearchDbIngestTest(unittest.TestCase):
    def test_read_markdown_table_returns_structured_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text(
                "\n".join(
                    [
                        "# 报告",
                        "| 策略编号 | 策略类型 |",
                        "|---|---|",
                        "| 策略一 | 均衡回调型 |",
                    ]
                ),
                encoding="utf-8",
            )

            frame = _read_markdown_table(path)

            self.assertEqual(frame.to_dict("records"), [{"策略编号": "策略一", "策略类型": "均衡回调型"}])

    def test_ingest_replaces_same_run_without_duplicate_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            factory_dir = root / "factory"
            rolling_dir = root / "rolling"
            null_dir = root / "null"
            export_dir = root / "export"
            for path in [factory_dir, rolling_dir, null_dir, export_dir]:
                path.mkdir()

            pd.DataFrame(
                [{"candidate_id": "s1", "final_score": 1.2, "top_n": 10, "rebalance_days": 20}]
            ).to_csv(factory_dir / "factory_all_candidates.csv", index=False)
            pd.DataFrame(
                [{"candidate_id": "s1", "final_score": 1.2, "top_n": 10, "rebalance_days": 20}]
            ).to_csv(factory_dir / "factory_qualified_candidates.csv", index=False)
            pd.DataFrame([{"reason": "live_failed", "count": 3}]).to_csv(
                factory_dir / "factory_failed_summary.csv", index=False
            )
            pd.DataFrame(
                [{"candidate_id": "s1", "ir": 2.0, "excess_return": 0.5, "mdd": 0.1}]
            ).to_csv(rolling_dir / "rolling_summary.csv", index=False)
            pd.DataFrame(
                [{"candidate_id": "s1", "pvalue_ir": 0.01, "deflated_ir_z": 2.5}]
            ).to_csv(null_dir / "null_overfit_summary.csv", index=False)
            pd.DataFrame(
                [{"策略编号": "策略一", "策略类型": "均衡回调型", "入库状态": "仅表格导出，未写入数据库"}]
            ).to_csv(export_dir / "中文表.csv", index=False)

            db_path = root / "research.duckdb"
            ingest_strategy_research(
                db_path=db_path,
                run_id="run-a",
                universe_status="动态流动性降偏，尚非历史时点成分",
                factory_dir=factory_dir,
                rolling_dir=rolling_dir,
                null_dir=null_dir,
                chinese_report_path=export_dir / "中文表.csv",
                export_dir=export_dir,
            )
            ingest_strategy_research(
                db_path=db_path,
                run_id="run-a",
                universe_status="动态流动性降偏，尚非历史时点成分",
                factory_dir=factory_dir,
                rolling_dir=rolling_dir,
                null_dir=null_dir,
                chinese_report_path=export_dir / "中文表.csv",
                export_dir=export_dir,
            )

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                self.assertEqual(con.execute("select count(*) from us_strategy_factory_candidates").fetchone()[0], 1)
                self.assertEqual(con.execute("select count(*) from us_strategy_rolling_results").fetchone()[0], 1)
                self.assertEqual(con.execute("select count(*) from us_strategy_random_checks").fetchone()[0], 1)
                self.assertEqual(con.execute("select count(*) from us_strategy_chinese_report").fetchone()[0], 1)
                self.assertEqual(con.execute("select count(*) from us_strategy_factory_qualified").fetchone()[0], 1)
                self.assertEqual(con.execute("select count(*) from us_strategy_factory_failed_summary").fetchone()[0], 1)
                status = con.execute("select universe_status from us_strategy_research_runs").fetchone()[0]
                self.assertEqual(status, "动态流动性降偏，尚非历史时点成分")
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
