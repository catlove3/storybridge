#!/usr/bin/env bash
set -Eeuo pipefail

STORYBRIDGE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STORYBRIDGE_MODE="real"
STORYBRIDGE_INSTALL=1
STORYBRIDGE_BACKEND_PID=""
STORYBRIDGE_FRONTEND_PID=""
STORYBRIDGE_RUN_DIR=""

usage() {
  cat <<'EOF'
Usage: ./speed_run.sh [--real|--mock] [--skip-install]

  --real          Start the configured real-model backend (default).
  --mock          Start the offline mock backend with isolated temporary data.
  --skip-install  Reuse installed Python and npm dependencies.
  -h, --help      Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --real) STORYBRIDGE_MODE="real" ;;
    --mock) STORYBRIDGE_MODE="mock" ;;
    --skip-install) STORYBRIDGE_INSTALL=0 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cleanup() {
  local exit_status=$?
  trap - EXIT INT TERM
  for process_id in "$STORYBRIDGE_FRONTEND_PID" "$STORYBRIDGE_BACKEND_PID"; do
    if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
      kill "$process_id" 2>/dev/null || true
    fi
  done
  for process_id in "$STORYBRIDGE_FRONTEND_PID" "$STORYBRIDGE_BACKEND_PID"; do
    if [[ -n "$process_id" ]]; then
      wait "$process_id" 2>/dev/null || true
    fi
  done
  if [[ -n "$STORYBRIDGE_RUN_DIR" ]]; then
    echo "Logs: $STORYBRIDGE_RUN_DIR"
  fi
  exit "$exit_status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

node_is_supported() {
  local node_version
  command -v node >/dev/null 2>&1 || return 1
  node_version="$(node --version)"
  [[ "$node_version" =~ ^v([0-9]+)\.([0-9]+)\. ]] || return 1
  ((BASH_REMATCH[1] == 20 && BASH_REMATCH[2] >= 19 || BASH_REMATCH[1] == 22 && BASH_REMATCH[2] >= 12 || BASH_REMATCH[1] > 22))
}

activate_project_node() {
  local requested_version nvm_script node_executable
  requested_version="$(<"$STORYBRIDGE_ROOT/frontend/.nvmrc")"

  for nvm_script in "${NVM_DIR:-}/nvm.sh" "${HOME:-}/.nvm/nvm.sh"; do
    if [[ -s "$nvm_script" ]]; then
      set +u
      # shellcheck source=/dev/null
      source "$nvm_script"
      set -u
      nvm use --silent "$requested_version" >/dev/null 2>&1 || true
      break
    fi
  done

  if ! node_is_supported; then
    require_command npm
    require_command npx
    echo "Preparing project Node $requested_version (system $(node --version 2>/dev/null || echo unavailable))..."
    if ! node_executable="$(npx --yes --package="node@$requested_version" -- node -p process.execPath)"; then
      echo "Could not prepare Node $requested_version through npm." >&2
      exit 1
    fi
    if [[ ! -x "$node_executable" ]]; then
      echo "npm returned an invalid Node executable: $node_executable" >&2
      exit 1
    fi
    export PATH="$(dirname -- "$node_executable"):$PATH"
  fi

  require_command node
  require_command npm
  if ! node_is_supported; then
    echo "Node $(node --version) is unsupported; use Node 22.12+ (frontend/.nvmrc)." >&2
    exit 1
  fi
}

wait_for_service() {
  local url=$1
  local process_id=$2
  local label=$3
  local log_file=$4
  local attempt
  for attempt in {1..120}; do
    if ! kill -0 "$process_id" 2>/dev/null; then
      echo "$label exited before becoming ready:" >&2
      tail -n 80 "$log_file" >&2 || true
      return 1
    fi
    if curl --noproxy '*' --fail --silent --show-error --max-time 1 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "$label did not become ready at $url:" >&2
  tail -n 80 "$log_file" >&2 || true
  return 1
}

require_command uv
require_command curl
activate_project_node

if ((STORYBRIDGE_INSTALL)); then
  echo "Syncing backend dependencies..."
  (cd "$STORYBRIDGE_ROOT/backend" && uv sync --frozen --extra dev)
  echo "Installing frontend dependencies..."
  (cd "$STORYBRIDGE_ROOT/frontend" && npm ci)
fi

STORYBRIDGE_RUN_DIR="$(mktemp -d -t storybridge-speed-run.XXXXXX)"
STORYBRIDGE_BACKEND_LOG="$STORYBRIDGE_RUN_DIR/backend.log"
STORYBRIDGE_FRONTEND_LOG="$STORYBRIDGE_RUN_DIR/frontend.log"

if [[ "$STORYBRIDGE_MODE" == "mock" ]]; then
  (
    export STORYBRIDGE_DATABASE_FILE="$STORYBRIDGE_RUN_DIR/storybridge.sqlite3"
    export STORYBRIDGE_PROJECTS_DIR="$STORYBRIDGE_RUN_DIR/artifacts"
    export STORYBRIDGE_JOBS_FILE="$STORYBRIDGE_RUN_DIR/legacy-jobs.json"
    export STORYBRIDGE_SFT_LOG_DIR="$STORYBRIDGE_RUN_DIR/sft"
    export STORYBRIDGE_RUN_LOG_DIR="$STORYBRIDGE_RUN_DIR/runs"
    cd "$STORYBRIDGE_ROOT/backend"
    exec uv run uvicorn app.mock_main:app --host 127.0.0.1 --port 8000
  ) >"$STORYBRIDGE_BACKEND_LOG" 2>&1 &
else
  (
    cd "$STORYBRIDGE_ROOT/backend"
    exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
  ) >"$STORYBRIDGE_BACKEND_LOG" 2>&1 &
fi
STORYBRIDGE_BACKEND_PID=$!

(
  cd "$STORYBRIDGE_ROOT/frontend"
  exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
) >"$STORYBRIDGE_FRONTEND_LOG" 2>&1 &
STORYBRIDGE_FRONTEND_PID=$!

wait_for_service \
  "http://127.0.0.1:8000/healthz" \
  "$STORYBRIDGE_BACKEND_PID" \
  "Backend" \
  "$STORYBRIDGE_BACKEND_LOG"
wait_for_service \
  "http://127.0.0.1:5173/" \
  "$STORYBRIDGE_FRONTEND_PID" \
  "Frontend" \
  "$STORYBRIDGE_FRONTEND_LOG"

echo
echo "StoryBridge is ready ($STORYBRIDGE_MODE mode)."
echo "App:      http://127.0.0.1:5173"
echo "API docs: http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop both services."
echo

set +e
wait -n "$STORYBRIDGE_BACKEND_PID" "$STORYBRIDGE_FRONTEND_PID"
STORYBRIDGE_EXIT_STATUS=$?
set -e
if ((STORYBRIDGE_EXIT_STATUS != 0)); then
  echo "A service exited unexpectedly." >&2
  tail -n 40 "$STORYBRIDGE_BACKEND_LOG" >&2 || true
  tail -n 40 "$STORYBRIDGE_FRONTEND_LOG" >&2 || true
fi
exit "$STORYBRIDGE_EXIT_STATUS"
