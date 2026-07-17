from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd


TABLES = [
    "us_strategy_chinese_report",
    "us_paper_live_model_portfolio",
    "us_paper_live_latest_signals",
    "us_paper_live_strategies",
    "us_strategy_factory_failed_summary",
    "us_strategy_factory_qualified",
    "us_strategy_random_checks",
    "us_strategy_rolling_results",
    "us_strategy_factory_candidates",
    "us_strategy_research_runs",
]


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".md":
        return _read_markdown_table(path)
    return pd.read_csv(path)


def _read_markdown_table(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    table_lines = [line.strip() for line in lines if line.strip().startswith("|") and line.strip().endswith("|")]
    rows = []
    headers: list[str] | None = None
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return pd.DataFrame(rows)


def _register_frame(con: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    exists = con.execute(
        "select count(*) from information_schema.tables where table_name = ?",
        [table],
    ).fetchone()[0]
    if exists:
        existing_columns = [
            row[1]
            for row in con.execute(f"pragma table_info('{table}')").fetchall()
        ]
        if existing_columns != list(frame.columns):
            con.execute(f"drop table {table}")
    con.register("_frame", frame)
    try:
        con.execute(f"create table if not exists {table} as select * from _frame where 1=0")
        con.execute(f"insert into {table} select * from _frame")
    finally:
        con.unregister("_frame")


def _with_run_columns(frame: pd.DataFrame, run_id: str, universe_status: str, source_path: Path) -> pd.DataFrame:
    out = frame.copy()
    out.insert(0, "run_id", run_id)
    out.insert(1, "universe_status", universe_status)
    out.insert(2, "source_path", str(source_path))
    return out


def _delete_existing_run(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    for table in TABLES:
        exists = con.execute(
            "select count(*) from information_schema.tables where table_name = ?",
            [table],
        ).fetchone()[0]
        if exists:
            con.execute(f"delete from {table} where run_id = ?", [run_id])


def ingest_strategy_research(
    db_path: Path,
    run_id: str,
    universe_status: str,
    factory_dir: Path,
    rolling_dir: Path,
    null_dir: Path,
    chinese_report_path: Path,
    export_dir: Path | None = None,
) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        _delete_existing_run(con, run_id)

        run_frame = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "universe_status": universe_status,
                    "factory_dir": str(factory_dir),
                    "rolling_dir": str(rolling_dir),
                    "null_dir": str(null_dir),
                    "chinese_report_path": str(chinese_report_path),
                    "ingested_at": pd.Timestamp.now(tz="UTC").isoformat(),
                }
            ]
        )
        _register_frame(con, "us_strategy_research_runs", run_frame)

        loaded: dict[str, int] = {"us_strategy_research_runs": 1}
        sources = [
            ("us_strategy_factory_candidates", factory_dir / "factory_all_candidates.csv"),
            ("us_strategy_factory_qualified", factory_dir / "factory_qualified_candidates.csv"),
            ("us_strategy_factory_failed_summary", factory_dir / "factory_failed_summary.csv"),
            ("us_strategy_rolling_results", rolling_dir / "rolling_summary.csv"),
            ("us_strategy_random_checks", null_dir / "null_overfit_summary.csv"),
            ("us_strategy_chinese_report", chinese_report_path),
        ]
        if export_dir is not None:
            sources.extend(
                [
                    ("us_paper_live_strategies", export_dir / "paper_live_pool_strategies_20260712.csv"),
                    ("us_paper_live_latest_signals", export_dir / "paper_live_pool_latest_signals_20260712.csv"),
                    ("us_paper_live_model_portfolio", export_dir / "paper_live_model_portfolio_20260712.csv"),
                ]
            )
        for table, path in sources:
            frame = _read_csv_if_exists(path)
            if frame.empty:
                loaded[table] = 0
                continue
            frame = _with_run_columns(frame, run_id=run_id, universe_status=universe_status, source_path=path)
            _register_frame(con, table, frame)
            loaded[table] = int(len(frame))
        return {
            "db_path": str(db_path),
            "run_id": run_id,
            "universe_status": universe_status,
            "loaded_rows": loaded,
        }
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
    parser.add_argument("--run-id", default="2026-07-12-dynamic-liquidity")
    parser.add_argument("--universe-status", default="动态流动性降偏，尚非历史时点成分")
    parser.add_argument("--factory-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-factory-dynamic-liquidity")
    parser.add_argument("--rolling-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-rolling-dynamic-liquidity")
    parser.add_argument("--null-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-null-dynamic-liquidity")
    parser.add_argument("--chinese-report", default=r"G:\quant-agent-team-us\reports\us\export\2026-07-13-动态流动性策略复核中文表.md")
    parser.add_argument("--export-dir", default=r"G:\quant-agent-team-us\reports\us\export")
    args = parser.parse_args()

    result = ingest_strategy_research(
        db_path=Path(args.db),
        run_id=args.run_id,
        universe_status=args.universe_status,
        factory_dir=Path(args.factory_dir),
        rolling_dir=Path(args.rolling_dir),
        null_dir=Path(args.null_dir),
        chinese_report_path=Path(args.chinese_report),
        export_dir=Path(args.export_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
