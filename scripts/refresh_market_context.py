from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import PostgresCli
from quant_agent_team.market_context import refresh_market_context


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh northbound and attention market context")
    parser.add_argument("--stock-code", action="append", default=[])
    parser.add_argument("--top-n-attention", type=int, default=100)
    parser.add_argument("--attention-start-date", default="")
    parser.add_argument("--notice-start-date", default="")
    parser.add_argument("--context-start-date", default="2025-01-01")
    parser.add_argument("--theme-snapshot-date", default="")
    parser.add_argument("--skip-industries", action="store_true")
    parser.add_argument("--include-concepts", action="store_true")
    parser.add_argument("--max-concepts", type=int, default=60)
    parser.add_argument("--max-industries", type=int, default=0)
    args = parser.parse_args()

    result = refresh_market_context(
        db=PostgresCli(),
        stock_codes=args.stock_code,
        top_n_attention=args.top_n_attention,
        attention_start_date=args.attention_start_date or None,
        notice_start_date=args.notice_start_date or None,
        context_start_date=args.context_start_date or None,
        theme_snapshot_date=args.theme_snapshot_date or None,
        include_industries=not args.skip_industries,
        include_concepts=bool(args.include_concepts),
        max_concepts=args.max_concepts,
        max_industries=args.max_industries or None,
    )
    print(result.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
