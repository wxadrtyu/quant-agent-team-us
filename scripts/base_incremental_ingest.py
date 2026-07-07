#!/usr/bin/env python3
from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.workflow import ProjectWorkflow


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run base incremental ingest and write the summary and inventory")
    parser.add_argument("--source-dir", default="")
    parser.add_argument("--constraints-dir", default="")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--stock-code", action="append", default=[])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workflow = ProjectWorkflow(ROOT)
    path = workflow.run_base_incremental_ingest(
        source_dir=Path(args.source_dir).resolve() if args.source_dir else None,
        sample_size=args.sample_size,
        constraints_dir=Path(args.constraints_dir).resolve() if args.constraints_dir else None,
        stock_codes=args.stock_code,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
