#!/usr/bin/env bash
set -Eeuo pipefail

STORYBRIDGE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STORYBRIDGE_MODE="real"
STORYBRIDGE_INSTALL_MODE="auto"
STORYBRIDGE_BACKEND_PID=""
STORYBRIDGE_FRONTEND_PID=""
STORYBRIDGE_RUN_DIR=""
STORYBRIDGE_RUNTIME_DIR="$STORYBRIDGE_ROOT/.storybridge/runtime"
STORYBRIDGE_BACKEND_PYTHON="$STORYBRIDGE_ROOT/backend/.venv/bin/python"
STORYBRIDGE_BACKEND_SYNC_MARKER="$STORYBRIDGE_ROOT/backend/.venv/.storybridge-sync"

usage() {
  cat <<'EOF'
Usage: ./speed_run.sh [--real|--mock] [--refresh|--skip-install]

  --real          Start the configured real-model backend (default).
  --mock          Start the offline mock backend with isolated temporary data.
  --refresh       Force-refresh the Python and frontend dependencies.
  --skip-install  Skip dependency checks and reuse the existing environment.
  -h, --help      Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --real) STORYBRIDGE_MODE="real" ;;
    --mock) STORYBRIDGE_MODE="mock" ;;
    --refresh) STORYBRIDGE_INSTALL_MODE="refresh" ;;
    --skip-install) STORYBRIDGE_INSTALL_MODE="skip" ;;
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
    node_executable="$STORYBRIDGE_RUNTIME_DIR/node_modules/node/bin/node"
    if [[ -x "$node_executable" ]] && [[ "$("$node_executable" --version)" == "v$requested_version" ]]; then
      export PATH="$(dirname -- "$node_executable"):$PATH"
    fi
  fi

  if ! node_is_supported; then
    require_command npm
    echo "Installing project-local Node $requested_version once (system $(node --version 2>/dev/null || echo unavailable))..."
    mkdir -p "$STORYBRIDGE_RUNTIME_DIR"
    if ! npm install \
      --prefix "$STORYBRIDGE_RUNTIME_DIR" \
      --no-save \
      --no-package-lock \
      --no-audit \
      --no-fund \
      "node@$requested_version"; then
      echo "Could not install project-local Node $requested_version through npm." >&2
      exit 1
    fi
    node_executable="$STORYBRIDGE_RUNTIME_DIR/node_modules/node/bin/node"
    if [[ ! -x "$node_executable" ]]; then
      echo "The project-local Node executable is missing: $node_executable" >&2
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

sync_dependencies() {
  local sync_backend=0
  local sync_frontend=0
  local frontend_install_marker="$STORYBRIDGE_ROOT/frontend/node_modules/.package-lock.json"

  if [[ "$STORYBRIDGE_INSTALL_MODE" == "refresh" ]]; then
    sync_backend=1
    sync_frontend=1
  elif [[ "$STORYBRIDGE_INSTALL_MODE" == "auto" ]]; then
    if [[ ! -x "$STORYBRIDGE_BACKEND_PYTHON" \
      || ! -f "$STORYBRIDGE_BACKEND_SYNC_MARKER" \
      || "$STORYBRIDGE_ROOT/backend/uv.lock" -nt "$STORYBRIDGE_BACKEND_SYNC_MARKER" \
      || "$STORYBRIDGE_ROOT/backend/pyproject.toml" -nt "$STORYBRIDGE_BACKEND_SYNC_MARKER" ]]; then
      sync_backend=1
    fi
    if [[ ! -x "$STORYBRIDGE_ROOT/frontend/node_modules/.bin/vite" \
      || ! -f "$frontend_install_marker" \
      || "$STORYBRIDGE_ROOT/frontend/package-lock.json" -nt "$frontend_install_marker" \
      || "$STORYBRIDGE_ROOT/frontend/package.json" -nt "$frontend_install_marker" ]]; then
      sync_frontend=1
    fi
  fi

  if ((sync_backend)); then
    require_command uv
    echo "Syncing backend environment..."
    (cd "$STORYBRIDGE_ROOT/backend" && uv sync --frozen --extra dev)
    touch "$STORYBRIDGE_BACKEND_SYNC_MARKER"
  elif [[ ! -x "$STORYBRIDGE_BACKEND_PYTHON" ]]; then
    echo "Backend environment is missing; run without --skip-install." >&2
    exit 1
  fi

  if ((sync_frontend)); then
    echo "Installing frontend dependencies..."
    (cd "$STORYBRIDGE_ROOT/frontend" && npm ci)
  elif [[ ! -x "$STORYBRIDGE_ROOT/frontend/node_modules/.bin/vite" ]]; then
    echo "Frontend dependencies are missing; run without --skip-install." >&2
    exit 1
  fi

  if ((!sync_backend && !sync_frontend)); then
    echo "Reusing existing project environment."
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

require_command curl
activate_project_node
sync_dependencies

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
    exec "$STORYBRIDGE_BACKEND_PYTHON" -m uvicorn app.mock_main:app --host 127.0.0.1 --port 8000
  ) >"$STORYBRIDGE_BACKEND_LOG" 2>&1 &
else
  (
    cd "$STORYBRIDGE_ROOT/backend"
    exec "$STORYBRIDGE_BACKEND_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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
