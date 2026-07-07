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
    parser = ArgumentParser(description="Sync strategy-required data for quant-agent-team")
    parser.add_argument("--spec-path", required=True)
    parser.add_argument("--available", action="append", default=[])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workflow = ProjectWorkflow(ROOT)
    spec = workflow.load_strategy_spec(Path(args.spec_path).resolve())
    path = workflow.plan_strategy_data_sync(spec, available_items=args.available)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
