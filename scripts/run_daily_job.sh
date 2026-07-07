#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="${SOURCE_DIR:-$HOME/Downloads/stock_history}"
CONSTRAINTS_DIR="${CONSTRAINTS_DIR:-}"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.11}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/reports/logs}"
LOCK_DIR="$ROOT_DIR/.daily_job.lock"
TIMESTAMP="$(date +"%Y-%m-%dT%H-%M-%S")"
LOG_PATH="$LOG_DIR/daily_job_${TIMESTAMP}.log"

export PYTHONUNBUFFERED=1

mkdir -p "$LOG_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "daily job already running: $LOCK_DIR" | tee -a "$LOG_PATH"
  exit 1
fi

cleanup() {
  rmdir "$LOCK_DIR"
}
trap cleanup EXIT

print_blocked_snapshot() {
  local snapshot_path="$ROOT_DIR/reports/data_quality/lagging_backfill_status.json"
  if [[ ! -f "$snapshot_path" ]]; then
    echo "free_source_unavailable_snapshot=<missing>"
    return
  fi

  "$PYTHON_BIN" - <<PY
import json
from pathlib import Path

path = Path(r"$snapshot_path")
payload = json.loads(path.read_text(encoding="utf-8"))
print(
    "free_source_unavailable_snapshot="
    f"recent_2026={payload.get('recent_2026_remaining', {}).get('count', 0)},"
    f"recent_2025_tail={payload.get('recent_2025_tail_remaining', {}).get('count', 0)},"
    f"stale_2024={payload.get('stale_2024_remaining', {}).get('count', 0)},"
    f"stale_2020_2023={payload.get('stale_2020_2023_remaining', {}).get('count', 0)},"
    f"historical_pre_2020={payload.get('historical_end_before_2020_remaining', {}).get('count', 0)}"
)
PY
}

print_quality_snapshot() {
  local quality_path="$ROOT_DIR/reports/data_quality/latest.json"
  if [[ ! -f "$quality_path" ]]; then
    echo "quality_report=<missing>"
    return
  fi

  "$PYTHON_BIN" - <<PY
import json
from pathlib import Path

path = Path(r"$quality_path")
payload = json.loads(path.read_text(encoding="utf-8"))
lagging = payload.get("lagging_symbols", {})
blocked = lagging.get("backfill_status_snapshot", {})
print(
    "quality_report="
    f"lagging={lagging.get('lagging_symbol_count', 0)},"
    f"recent_2026_blocked={blocked.get('recent_2026_remaining', {}).get('count', 0)},"
    f"recent_2025_tail_blocked={blocked.get('recent_2025_tail_remaining', {}).get('count', 0)},"
    f"stale_2024_blocked={blocked.get('stale_2024_remaining', {}).get('count', 0)},"
    f"stale_2020_2023_blocked={blocked.get('stale_2020_2023_remaining', {}).get('count', 0)},"
    f"historical_pre_2020_blocked={blocked.get('historical_end_before_2020_remaining', {}).get('count', 0)}"
)
PY
}

CMD=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/run_daily_pipeline.py"
  "--source-dir" "$SOURCE_DIR"
)

if [[ -n "$CONSTRAINTS_DIR" ]]; then
  CMD+=("--constraints-dir" "$CONSTRAINTS_DIR")
fi

{
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] starting daily job"
  echo "root=$ROOT_DIR"
  echo "source_dir=$SOURCE_DIR"
  if [[ -n "$CONSTRAINTS_DIR" ]]; then
    echo "constraints_dir=$CONSTRAINTS_DIR"
  else
    echo "constraints_dir=<disabled>"
  fi
  print_blocked_snapshot
  "${CMD[@]}"
  print_quality_snapshot
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] daily job finished"
} | tee -a "$LOG_PATH"
