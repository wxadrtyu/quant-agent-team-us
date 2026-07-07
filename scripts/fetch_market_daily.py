#!/usr/bin/env python3.11
from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.market_fetch import update_stock_history_file
from quant_agent_team.lagging_status import load_free_source_unavailable_codes


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Fetch A-share daily bars from free providers and update stock_history")
    parser.add_argument("--source-dir", default=str(Path.home() / "Downloads" / "stock_history"))
    parser.add_argument("--stock-code", action="append", default=[])
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
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
    for stock_code in stock_codes:
        result = update_stock_history_file(
            source_dir=source_dir,
            stock_code=stock_code,
            start_date=args.start_date or None,
            end_date=args.end_date or None,
        )
        print(result)
    if skipped_codes:
        print(
            {
                "phase": "skip_free_source_unavailable",
                "skip_count": len(skipped_codes),
                "sample_codes": skipped_codes[:20],
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
