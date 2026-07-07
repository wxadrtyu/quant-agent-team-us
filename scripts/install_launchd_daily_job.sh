#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LABEL="com.laisicong.quant-agent-team.daily-job"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
LOG_DIR="$ROOT_DIR/reports/logs"
OUT_LOG="$LOG_DIR/launchd.daily-job.out.log"
ERR_LOG="$LOG_DIR/launchd.daily-job.err.log"
SOURCE_DIR="${SOURCE_DIR:-$HOME/Downloads/stock_history}"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.11}"
CONSTRAINTS_DIR="${CONSTRAINTS_DIR:-}"

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT_DIR/scripts/run_daily_job.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHON_BIN</key>
    <string>$PYTHON_BIN</string>
    <key>SOURCE_DIR</key>
    <string>$SOURCE_DIR</string>
PLIST

if [[ -n "$CONSTRAINTS_DIR" ]]; then
cat >> "$PLIST_PATH" <<PLIST
    <key>CONSTRAINTS_DIR</key>
    <string>$CONSTRAINTS_DIR</string>
PLIST
fi

cat >> "$PLIST_PATH" <<PLIST
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>15</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$OUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/$LABEL"

echo "$PLIST_PATH"
