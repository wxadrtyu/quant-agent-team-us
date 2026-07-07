#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.11}"

unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

exec "$PYTHON_BIN" -m streamlit run "$ROOT_DIR/apps/db_dashboard.py" \
  --server.headless true \
  --server.address 127.0.0.1 \
  --server.port 8501
