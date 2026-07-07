#!/usr/bin/env python3
"""One-command data catch-up — bring every dataset up to `today` and rebuild derived tables.

Idempotent: run it any time (e.g. after a month away) and it fills the gap. Each underlying
fetcher is resumable; the price/index time-series are force-refreshed so new bars are pulled
(qfq must be re-pulled in full to keep one consistent adjustment basis — see fetch script).

Steps (select with --only / skip with --skip):
  price        re-pull full-market qfq daily bars -> market_daily
  index        re-pull 7 benchmark indices (sina) -> index_daily
  valuation    baidu PE/PB (resumable) + eastmoney current snapshot floor
  roe          THS annual ROE (resumable)
  meta         industry / current-ST / delisted (eastmoney/sse)
  suspension   derive is_suspended from calendar gaps (network-free)
  panel        rebuild factor_panel (+ value/quality if fundamentals present)

Usage:
  python scripts/refresh_all_data.py                 # full catch-up
  python scripts/refresh_all_data.py --only price index panel
  python scripts/refresh_all_data.py --skip valuation roe
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
ALL_STEPS = ["price", "index", "valuation", "roe", "meta", "suspension", "panel"]


def _run(label: str, cmd: list[str]) -> dict:
    t = time.time()
    print(f"\n=== [{label}] {' '.join(cmd[1:])} ===", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return {"step": label, "ok": proc.returncode == 0, "seconds": round(time.time() - t, 1)}


def _db_state(db: str) -> dict:
    import duckdb
    con = duckdb.connect(db, read_only=True)
    have = {r[0] for r in con.execute("show tables").fetchall()}
    state = {}
    for t, datecol in [("market_daily", "trade_date"), ("index_daily", "trade_date"),
                       ("factor_panel", "trade_date"), ("valuation_daily", "trade_date"),
                       ("financials", "report_date"), ("suspension_daily", "trade_date")]:
        if t in have:
            n, mx = con.execute(f"select count(*), max({datecol}) from {t}").fetchone()
            state[t] = {"rows": n, "max_date": str(mx)}
        else:
            state[t] = None
    con.close()
    return state


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to-date", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--db", default=str(ROOT / "quant.duckdb"))
    ap.add_argument("--only", nargs="*", choices=ALL_STEPS)
    ap.add_argument("--skip", nargs="*", choices=ALL_STEPS, default=[])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    steps = args.only or ALL_STEPS
    steps = [s for s in steps if s not in args.skip]

    print(f"[refresh] to_date={args.to_date}  steps={steps}", flush=True)
    print("[refresh] BEFORE:", _db_state(args.db), flush=True)
    results = []

    if "price" in steps:
        # qfq must be re-pulled in full to keep a consistent adjustment basis
        shutil.rmtree(ROOT / "data" / "akshare_qfq", ignore_errors=True)
        results.append(_run("price.fetch", [PY, "scripts/fetch_akshare_history.py",
                                            "--start", "20220101", "--end", args.to_date,
                                            "--adjust", "qfq", "--workers", str(args.workers)]))
        results.append(_run("price.ingest", [PY, "scripts/ingest_akshare_to_duckdb.py"]))

    if "index" in steps:
        results.append(_run("index", [PY, "-c",
            "import sys; sys.path.insert(0,'src');"
            "from quant_agent_team.benchmark import load_index_daily, INDEX_SINA;"
            "[load_index_daily(n, refresh=True) for n in INDEX_SINA];"
            "print('index_daily refreshed')"]))

    if "valuation" in steps:
        results.append(_run("valuation.baidu", [PY, "scripts/fetch_akshare_fundamentals.py",
                                                "--skip-roe", "--workers", "3"]))
        results.append(_run("valuation.snapshot", [PY, "scripts/fetch_valuation_snapshot.py"]))

    if "roe" in steps:
        results.append(_run("roe.ths", [PY, "scripts/fetch_roe_ths.py", "--workers", str(args.workers)]))

    if "meta" in steps:
        results.append(_run("meta.fetch", [PY, "scripts/fetch_industry_st_delist.py"]))
        results.append(_run("meta.ingest", [PY, "scripts/ingest_meta.py"]))

    if "suspension" in steps:
        results.append(_run("suspension", [PY, "scripts/build_tradability.py"]))

    if "valuation" in steps or "roe" in steps:
        results.append(_run("fundamentals.ingest", [PY, "scripts/ingest_fundamentals.py"]))

    if "panel" in steps:
        results.append(_run("panel", [PY, "scripts/build_factor_panel.py"]))

    print("\n[refresh] AFTER:", _db_state(args.db), flush=True)
    print("\n[refresh] STEP RESULTS:")
    for r in results:
        print(f"  {'OK ' if r['ok'] else 'ERR'} {r['step']:24s} {r['seconds']}s")
    failed = [r["step"] for r in results if not r["ok"]]
    print(f"\n[refresh] done. {len(results)-len(failed)}/{len(results)} steps ok."
          + (f" FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
