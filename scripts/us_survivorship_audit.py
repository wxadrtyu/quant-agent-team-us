from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def audit_membership(membership: pd.DataFrame) -> dict:
    if membership.empty:
        return {
            "status": "blocked_missing_membership",
            "pit_ready": False,
            "rows": 0,
            "symbols": 0,
            "current_snapshot_rows": 0,
            "historical_rows": 0,
        }
    frame = membership.copy()
    frame["membership_type"] = frame.get("membership_type", "").fillna("").astype(str)
    end_date = frame.get("end_date", pd.Series([""] * len(frame))).fillna("").astype(str)
    current_snapshot_rows = int(frame["membership_type"].str.lower().eq("current_snapshot").sum())
    historical_rows = int((~frame["membership_type"].str.lower().eq("current_snapshot") | end_date.ne("")).sum())
    pit_ready = historical_rows > 0 and current_snapshot_rows < len(frame)
    status = "pit_ready" if pit_ready else "blocked_current_snapshot_only"
    return {
        "status": status,
        "pit_ready": bool(pit_ready),
        "rows": int(len(frame)),
        "symbols": int(frame["symbol"].nunique()) if "symbol" in frame else 0,
        "universes": int(frame["universe_name"].nunique()) if "universe_name" in frame else 0,
        "current_snapshot_rows": current_snapshot_rows,
        "historical_rows": historical_rows,
        "membership_types": frame["membership_type"].value_counts().to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--membership", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12\us_index_membership.parquet")
    parser.add_argument("--export-dir", default=r"G:\quant-agent-team-us\reports\us\export")
    parser.add_argument("--out-dir", default=r"E:\quant-agent-team-us\research\2026-07-12-survivorship-audit")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    membership = pd.read_parquet(args.membership)
    result = audit_membership(membership)
    result["membership"] = args.membership
    (out_dir / "survivorship_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    pd.DataFrame([result]).to_csv(out_dir / "survivorship_audit.csv", index=False)

    export_dir = Path(args.export_dir)
    for filename in ["strategy_table_20260712.csv", "paper_live_pool_strategies_20260712.csv"]:
        path = export_dir / filename
        if path.exists():
            frame = pd.read_csv(path)
            frame["survivorship_status"] = "pit_ready" if result["pit_ready"] else "blocked_current_snapshot_only"
            frame["active_monitoring_status"] = "eligible_after_human_review" if result["pit_ready"] else "blocked_pending_pit_universe"
            frame.to_csv(path, index=False)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
