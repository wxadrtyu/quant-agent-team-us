#!/usr/bin/env python3.11
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.workflow import ProjectWorkflow


def main() -> int:
    workflow = ProjectWorkflow(ROOT)
    path = workflow.run_data_quality_report()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
