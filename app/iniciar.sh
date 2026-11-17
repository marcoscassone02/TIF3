#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PORT="${PORT:-8000}"

cd "$PROJECT_DIR"
exec "$PROJECT_DIR/venv/bin/uvicorn" backend.api:app \
  --app-dir "$SCRIPT_DIR" \
  --host 127.0.0.1 \
  --port "$PORT"
