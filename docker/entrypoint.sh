#!/usr/bin/env bash
set -euo pipefail

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
UI_HOST="${UI_HOST:-0.0.0.0}"
UI_PORT="${UI_PORT:-8501}"

cleanup() {
  # Best-effort shutdown of background processes
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

uvicorn bot:app --host "$API_HOST" --port "$API_PORT" &
API_PID="$!"

exec streamlit run app.py --server.address "$UI_HOST" --server.port "$UI_PORT"
