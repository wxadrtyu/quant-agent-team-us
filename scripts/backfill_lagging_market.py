#!/usr/bin/env python3.11
from __future__ import annotations

from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing as mp
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import PostgresCli
from quant_agent_team.market_fetch import update_stock_history_file
from quant_agent_team.workflow import ProjectWorkflow


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Backfill lagging stock_history files and ingest them into PostgreSQL")
    parser.add_argument("--source-dir", default=str(Path.home() / "Downloads" / "stock_history"))
    parser.add_argument("--end-date", default="2026-03-20")
    parser.add_argument("--max-lag-date", default="2026-03-20")
    parser.add_argument("--exact-lag-date", default="2025-12-31")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=12)
    return parser


def load_lagging_codes(
    db: PostgresCli,
    max_lag_date: str,
    exact_lag_date: str = "",
    limit: int = 0,
) -> list[str]:
    sql = f"""
SELECT stock_code
FROM (
  SELECT stock_code, MAX(trade_date) AS max_trade_date
  FROM raw_market_daily
  WHERE stock_code ~ '^[0-9]{{6}}$'
  GROUP BY stock_code
) t
WHERE max_trade_date < '{max_lag_date}'::date
"""
    if exact_lag_date:
        sql += f"\n  AND max_trade_date = '{exact_lag_date}'::date"
    sql += "\nORDER BY stock_code"
    if limit > 0:
        sql += f"\nLIMIT {limit}"
    sql += ";"
    return [row.strip() for row in db.run_sql(sql).splitlines() if row.strip()]


def fetch_one_task(payload: dict[str, str]) -> dict[str, object]:
    stock_code = payload["stock_code"]
    source_dir = Path(payload["source_dir"])
    start_date = payload.get("start_date") or None
    end_date = payload.get("end_date") or None
    try:
        result = update_stock_history_file(
            source_dir=source_dir,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
        )
        return {"status": "ok", **result}
    except Exception as exc:
        return {"status": "error", "stock_code": stock_code, "error": str(exc)}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    db = PostgresCli()
    workflow = ProjectWorkflow(ROOT)
    source_dir = Path(args.source_dir).resolve()
    logs_dir = ROOT / "reports" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    suffix = (args.exact_lag_date or args.max_lag_date).replace(":", "-")
    log_path = logs_dir / f"parallel_backfill_{suffix}.jsonl"
    fail_path = logs_dir / f"parallel_backfill_{suffix}_failures.json"

    codes = load_lagging_codes(
        db,
        max_lag_date=args.max_lag_date,
        exact_lag_date=args.exact_lag_date,
        limit=args.limit,
    )
    failed: list[dict[str, object]] = []
    success_count = 0
    symbols_with_new_dates = 0

    def log(item: dict[str, object]) -> None:
        line = json.dumps(item, ensure_ascii=False)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(item, flush=True)

    log(
        {
            "phase": "start",
            "lagging_count": len(codes),
            "workers": args.workers,
            "exact_lag_date": args.exact_lag_date,
            "log_path": str(log_path),
        }
    )

    start_date = "2026-01-01" if args.exact_lag_date == "2025-12-31" else ""
    mp_context = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=max(1, args.workers), mp_context=mp_context) as executor:
        future_map = {
            executor.submit(
                fetch_one_task,
                {
                    "stock_code": code,
                    "source_dir": str(source_dir),
                    "start_date": start_date,
                    "end_date": args.end_date or "",
                },
            ): code
            for code in codes
        }
        for index, future in enumerate(as_completed(future_map), start=1):
            result = future.result()
            if result["status"] == "ok":
                success_count += 1
                if result.get("new_dates"):
                    symbols_with_new_dates += 1
                if result.get("new_dates") or index == 1 or index % 100 == 0:
                    log({"phase": "fetch", "index": index, "total": len(codes), **result})
            else:
                item = {"phase": "fetch_error", "index": index, "total": len(codes), **result}
                failed.append(item)
                log(item)

    fail_path.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary_path = workflow.run_daily_update(source_dir=source_dir, sample_size=50)
    log(
        {
            "phase": "ingest_done",
            "summary_path": str(summary_path),
            "fetch_success_count": success_count,
            "symbols_with_new_dates": symbols_with_new_dates,
        }
    )
    log({"phase": "feature_done", "feature_path": "embedded_in_daily_update"})
    log(
        {
            "phase": "done",
            "failure_count": len(failed),
            "failure_path": str(fail_path),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
