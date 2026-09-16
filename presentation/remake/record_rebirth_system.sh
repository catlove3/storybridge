#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/zypca/zhili
CASE="$ROOT/presentation/remake/rebirth_system_16k"
NODE_BIN=/home/zypca/.npm/_npx/f2a849c05e3b14b4/node_modules/node/bin
cleanup() {
  if [[ -n "${VITE_PID:-}" ]]; then kill "$VITE_PID" 2>/dev/null || true; fi
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

cd "$ROOT/backend"
env STORYBRIDGE_DATABASE_FILE="$CASE/runtime/storybridge.sqlite3" \
    STORYBRIDGE_PROJECTS_DIR="$CASE/runtime/projects" \
    STORYBRIDGE_RUN_LOG_DIR="$CASE/runtime/run_logs" \
    STORYBRIDGE_JOBS_FILE="$CASE/runtime/jobs.json" \
    .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 \
    >"$CASE/api_recording.log" 2>&1 &
API_PID=$!

cd "$ROOT/frontend"
env PATH="$NODE_BIN:/usr/local/bin:/usr/bin:/bin" \
    VITE_API_TARGET=http://127.0.0.1:8001 \
    npm run dev -- --host 127.0.0.1 --port 5175 \
    >"$CASE/vite_recording.log" 2>&1 &
VITE_PID=$!

for _ in $(seq 1 40); do
  if curl --noproxy '*' -fsS http://127.0.0.1:5175/ >/dev/null 2>&1 && \
     curl --noproxy '*' -fsS http://127.0.0.1:8001/api/runtime-policy >/dev/null 2>&1; then
    break
  fi
  sleep .25
done
curl --noproxy '*' -fsS http://127.0.0.1:5175/ >/dev/null
curl --noproxy '*' -fsS http://127.0.0.1:8001/api/runtime-policy >/dev/null

cd "$ROOT"
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost python3.12 presentation/remake/capture_rebirth_system.py
