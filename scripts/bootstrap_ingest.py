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
    parser = ArgumentParser(description="Bootstrap raw market data into PostgreSQL")
    parser.add_argument("--source-dir", default="")
    parser.add_argument("--limit-files", type=int, default=0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workflow = ProjectWorkflow(ROOT)
    path = workflow.run_bootstrap_ingest(
        source_dir=Path(args.source_dir).resolve() if args.source_dir else None,
        limit_files=args.limit_files or None,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
