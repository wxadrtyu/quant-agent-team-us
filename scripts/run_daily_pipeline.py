#!/usr/bin/env python3.11
from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.lagging_status import load_free_source_unavailable_codes
from quant_agent_team.market_fetch import update_stock_history_file
from quant_agent_team.workflow import ProjectWorkflow


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Fetch free-market daily bars into stock_history and then run incremental ingest"
    )
    parser.add_argument("--source-dir", default=str(Path.home() / "Downloads" / "stock_history"))
    parser.add_argument("--constraints-dir", default="")
    parser.add_argument("--stock-code", action="append", default=[])
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--include-free-source-unavailable", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()
    explicit_stock_codes = bool(args.stock_code)
    stock_codes = args.stock_code or sorted(path.stem for path in source_dir.glob("*.csv") if path.is_file())
    skipped_codes: list[str] = []
    if not explicit_stock_codes and not args.include_free_source_unavailable:
        blocked = load_free_source_unavailable_codes(ROOT)
        skipped_codes = [code for code in stock_codes if code in blocked]
        stock_codes = [code for code in stock_codes if code not in blocked]
    failed_fetches: list[dict[str, str]] = []

    for stock_code in stock_codes:
        try:
            result = update_stock_history_file(
                source_dir=source_dir,
                stock_code=stock_code,
                start_date=args.start_date or None,
                end_date=args.end_date or None,
            )
            print(result)
        except Exception as exc:
            error = {"stock_code": stock_code, "error": str(exc)}
            failed_fetches.append(error)
            print(error)

    if skipped_codes:
        print(
            {
                "phase": "skip_free_source_unavailable",
                "skip_count": len(skipped_codes),
                "sample_codes": skipped_codes[:20],
            }
        )

    workflow = ProjectWorkflow(ROOT)
    summary_path = workflow.run_daily_update(
        source_dir=source_dir,
        sample_size=args.sample_size,
        constraints_dir=Path(args.constraints_dir).resolve() if args.constraints_dir else None,
        stock_codes=stock_codes if explicit_stock_codes else None,
    )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    execution = payload.get("execution") or {}
    execution["fetch"] = {
        "requested_stock_codes": len(stock_codes) + len(skipped_codes),
        "attempted_stock_codes": len(stock_codes),
        "failed_fetch_count": len(failed_fetches),
        "failed_fetches": failed_fetches[:50],
        "skipped_free_source_unavailable_count": len(skipped_codes),
        "skipped_free_source_unavailable_sample": skipped_codes[:50],
        "include_free_source_unavailable": bool(args.include_free_source_unavailable),
        "explicit_stock_codes": explicit_stock_codes,
    }
    payload["execution"] = execution
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(summary_path)
    if failed_fetches:
        print({"fetch_failures": failed_fetches, "failure_count": len(failed_fetches)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
