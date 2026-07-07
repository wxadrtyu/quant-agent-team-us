#!/usr/bin/env python3
"""Build/refresh the factor_panel table from market_daily (+ fundamentals if present)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_agent_team.factor_panel import build_factor_panel  # noqa: E402

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "quant.duckdb")
    print(json.dumps(build_factor_panel(db), ensure_ascii=False, indent=2))
