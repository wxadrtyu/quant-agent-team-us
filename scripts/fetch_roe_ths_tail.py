#!/usr/bin/env python3
"""Co-operative helper for fetch_roe_ths.py (run by another session from the front).

Fills the REMAINING THS ROE working the TAIL of universe.json (reverse order) so the
two pullers converge toward the middle. Reuses fetch_roe_ths.fetch_one verbatim, so:
  - same source ('ths'), same output dir, same look-ahead-safe report_date  -> no mixing
  - skip-if-exists in fetch_one  -> NEVER re-writes a file the other session already made
  - low workers (default 2)  -> shares akshare's per-IP rate budget politely

'skip' results just mean the other session got there first (dedup working as intended).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_roe_ths import OUT, ROOT, fetch_one  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    uni = json.loads((ROOT / "data" / "universe.json").read_text(encoding="utf-8"))
    codes = [r["code"] if isinstance(r, dict) else str(r) for r in uni]
    missing = [c for c in codes if not (OUT / f"{c}.parquet").exists()]
    missing = list(reversed(missing))  # tail-first, opposite the front-running session
    total = len(missing)
    print(f"[tail] {total} missing, workers={args.workers}", flush=True)

    ok = skip = done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(fetch_one, c) for c in missing]):
            _code, status = fut.result()
            done += 1
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            if done % 100 == 0 or done == total:
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (total - done) / rate / 60 if rate else 0
                print(f"[{done}/{total}] ok={ok} skip={skip} {rate:.2f}/s eta={eta:.1f}min", flush=True)
    print(f"[tail done] ok={ok} skip={skip} in {(time.time()-t0)/60:.1f}min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
