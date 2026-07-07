from __future__ import annotations

import json
from pathlib import Path


def load_free_source_unavailable_codes(project_root: Path) -> set[str]:
    path = project_root / "reports" / "data_quality" / "lagging_backfill_status.json"
    if not path.exists():
        return set()

    payload = json.loads(path.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for bucket_name in (
        "recent_2026_remaining",
        "recent_2025_tail_remaining",
        "stale_2024_remaining",
        "stale_2020_2023_remaining",
        "historical_end_before_2020_remaining",
    ):
        bucket = payload.get(bucket_name) or {}
        for row in bucket.get("symbols") or []:
            stock_code = row.get("stock_code")
            if stock_code:
                codes.add(stock_code)
    return codes
