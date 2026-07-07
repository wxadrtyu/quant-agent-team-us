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
    parser = ArgumentParser(description="Refresh derived research features from normalized market data")
    parser.add_argument("--stock-code", action="append", default=[])
    parser.add_argument("--skip-gap-diagnostics", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workflow = ProjectWorkflow(ROOT)
    path = workflow.run_feature_refresh(
        stock_codes=args.stock_code,
        include_gap_diagnostics=not args.skip_gap_diagnostics,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
