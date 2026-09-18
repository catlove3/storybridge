#!/usr/bin/env bash
set -Eeuo pipefail

STORYBRIDGE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STORYBRIDGE_MODE="real"
STORYBRIDGE_SHARE_MODE=0
STORYBRIDGE_TUNNEL_PID=""
STORYBRIDGE_QUICK_TUNNEL=0
STORYBRIDGE_INSTALL_MODE="auto"
STORYBRIDGE_BACKEND_PID=""
STORYBRIDGE_FRONTEND_PID=""
STORYBRIDGE_PUBLIC_IP=""
STORYBRIDGE_RUN_DIR=""
STORYBRIDGE_RUNTIME_DIR="$STORYBRIDGE_ROOT/.storybridge/runtime"
STORYBRIDGE_BACKEND_PYTHON="$STORYBRIDGE_ROOT/backend/.venv/bin/python"
STORYBRIDGE_BACKEND_SYNC_MARKER="$STORYBRIDGE_ROOT/backend/.venv/.storybridge-sync"

usage() {
  cat <<'EOF'
Usage: ./speed_run.sh [--share] [--real|--mock] [--refresh|--skip-install]

  --real          Start the configured real-model backend (default).
  --mock          Start the offline mock backend with isolated temporary data.
  --share         Build the website and share it over a temporary HTTPS tunnel.
  --refresh       Force-refresh the Python and frontend dependencies.
  --skip-install  Skip dependency checks and reuse the existing environment.
  -h, --help      Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --real) STORYBRIDGE_MODE="real" ;;
    --share) STORYBRIDGE_SHARE_MODE=1 ;;
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
  for process_id in "$STORYBRIDGE_TUNNEL_PID" "$STORYBRIDGE_FRONTEND_PID" "$STORYBRIDGE_BACKEND_PID"; do
    if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
      kill "$process_id" 2>/dev/null || true
    fi
  done
  for process_id in "$STORYBRIDGE_TUNNEL_PID" "$STORYBRIDGE_FRONTEND_PID" "$STORYBRIDGE_BACKEND_PID"; do
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

resolve_public_ipv4() {
  local hostname=$1 resolver answer
  for resolver in 1.1.1.1 8.8.8.8; do
    answer="$(dig +time=4 +tries=1 "@$resolver" "$hostname" A +short 2>/dev/null || true)"
    answer="$(sed -nE '/^([0-9]{1,3}\.){3}[0-9]{1,3}$/p' <<<"$answer" | head -n 1)"
    if [[ -n "$answer" ]]; then
      printf '%s\n' "$answer"
      return 0
    fi
  done
  return 1
}

start_resolvable_quick_tunnel() {
  local address_attempt hostname
  : >"$STORYBRIDGE_TUNNEL_LOG"
  STORYBRIDGE_PUBLIC_URL=""
  STORYBRIDGE_PUBLIC_IP=""
  echo "Starting Cloudflare temporary HTTPS tunnel..."
  "$STORYBRIDGE_CLOUDFLARED" tunnel --config "$STORYBRIDGE_RUN_DIR/tunnel.yaml" \
    --no-autoupdate --protocol http2 --edge-ip-version 4 --retries 100 \
    --url http://127.0.0.1:8000 \
    >"$STORYBRIDGE_TUNNEL_LOG" 2>&1 &
  STORYBRIDGE_TUNNEL_PID=$!

  for address_attempt in {1..120}; do
    if ! kill -0 "$STORYBRIDGE_TUNNEL_PID" 2>/dev/null; then
      echo "Cloudflare tunnel exited before returning an address:" >&2
      tail -n 80 "$STORYBRIDGE_TUNNEL_LOG" >&2 || true
      return 1
    fi
    STORYBRIDGE_PUBLIC_URL="$(sed -nE 's/.*(https:\/\/[a-z0-9-]+\.trycloudflare\.com).*/\1/p' \
      "$STORYBRIDGE_TUNNEL_LOG" | head -n 1)"
    [[ -n "$STORYBRIDGE_PUBLIC_URL" ]] && break
    sleep 0.5
  done
  if [[ -z "$STORYBRIDGE_PUBLIC_URL" ]]; then
    echo "Cloudflare did not return a temporary address. See $STORYBRIDGE_TUNNEL_LOG" >&2
    return 1
  fi

  hostname="${STORYBRIDGE_PUBLIC_URL#https://}"
  echo "Waiting up to 2 minutes for public IPv4 DNS propagation..."
  for address_attempt in {1..60}; do
    if ! kill -0 "$STORYBRIDGE_TUNNEL_PID" 2>/dev/null; then
      echo "Cloudflare tunnel exited while waiting for DNS:" >&2
      tail -n 80 "$STORYBRIDGE_TUNNEL_LOG" >&2 || true
      return 1
    fi
    if STORYBRIDGE_PUBLIC_IP="$(resolve_public_ipv4 "$hostname")"; then
      echo "Temporary hostname is ready in public DNS."
      return 0
    fi
    sleep 2
  done

  echo "Cloudflare DNS is still propagating; keeping this tunnel and address alive." >&2
  return 0
}

require_command curl
activate_project_node
sync_dependencies

STORYBRIDGE_RUN_DIR="$(mktemp -d -t storybridge-speed-run.XXXXXX)"
STORYBRIDGE_BACKEND_LOG="$STORYBRIDGE_RUN_DIR/backend.log"
STORYBRIDGE_FRONTEND_LOG="$STORYBRIDGE_RUN_DIR/frontend.log"

if ((STORYBRIDGE_SHARE_MODE)); then
  # Refuse to expose an unrelated service that already occupies our port.
  "$STORYBRIDGE_BACKEND_PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",8000)); s.close()'
  if [[ "$STORYBRIDGE_MODE" == "real" ]]; then
    (cd "$STORYBRIDGE_ROOT/backend" && "$STORYBRIDGE_BACKEND_PYTHON" -m app.secrets)
  fi
  echo "Building the shared website..."
  (cd "$STORYBRIDGE_ROOT/frontend" && STORYBRIDGE_PUBLIC_BUILD=1 npm run build)
  if [[ -z "${STORYBRIDGE_PUBLIC_URL:-}" ]]; then
    if command -v cloudflared >/dev/null 2>&1; then
      STORYBRIDGE_CLOUDFLARED="$(command -v cloudflared)"
    else
      echo "Preparing cloudflared..."
      (cd "$STORYBRIDGE_ROOT/backend" && "$STORYBRIDGE_BACKEND_PYTHON" -m scripts.prepare_tunnel)
      STORYBRIDGE_CLOUDFLARED="$STORYBRIDGE_RUNTIME_DIR/cloudflared"
    fi
    STORYBRIDGE_TUNNEL_LOG="$STORYBRIDGE_RUN_DIR/tunnel.log"
    require_command dig
    # An explicit empty config avoids altering any existing named-tunnel config.
    echo '{}' > "$STORYBRIDGE_RUN_DIR/tunnel.yaml"
    STORYBRIDGE_QUICK_TUNNEL=1
    start_resolvable_quick_tunnel
  fi
  export STORYBRIDGE_PUBLIC_URL STORYBRIDGE_SHARE=1 STORYBRIDGE_SERVE_FRONTEND=1
fi

if [[ "$STORYBRIDGE_MODE" == "mock" ]]; then
  (
    export STORYBRIDGE_DATABASE_FILE="$STORYBRIDGE_RUN_DIR/storybridge.sqlite3"
    export STORYBRIDGE_PROJECTS_DIR="$STORYBRIDGE_RUN_DIR/artifacts"
    export STORYBRIDGE_JOBS_FILE="$STORYBRIDGE_RUN_DIR/legacy-jobs.json"
    export STORYBRIDGE_SFT_LOG_DIR="$STORYBRIDGE_RUN_DIR/sft"
    export STORYBRIDGE_RUN_LOG_DIR="$STORYBRIDGE_RUN_DIR/runs"
    cd "$STORYBRIDGE_ROOT/backend"
    exec "$STORYBRIDGE_BACKEND_PYTHON" -m uvicorn app.mock_main:app --host 127.0.0.1 --port 8000 --workers 1
  ) >"$STORYBRIDGE_BACKEND_LOG" 2>&1 &
else
  (
    cd "$STORYBRIDGE_ROOT/backend"
    exec "$STORYBRIDGE_BACKEND_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
  ) >"$STORYBRIDGE_BACKEND_LOG" 2>&1 &
fi
STORYBRIDGE_BACKEND_PID=$!

if ((!STORYBRIDGE_SHARE_MODE)); then
(
  cd "$STORYBRIDGE_ROOT/frontend"
  exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
) >"$STORYBRIDGE_FRONTEND_LOG" 2>&1 &
STORYBRIDGE_FRONTEND_PID=$!
fi

wait_for_service \
  "http://127.0.0.1:8000/readyz" \
  "$STORYBRIDGE_BACKEND_PID" \
  "Backend" \
  "$STORYBRIDGE_BACKEND_LOG"
if ((!STORYBRIDGE_SHARE_MODE)); then
wait_for_service \
  "http://127.0.0.1:5173/" \
  "$STORYBRIDGE_FRONTEND_PID" \
  "Frontend" \
  "$STORYBRIDGE_FRONTEND_LOG"
else
  STORYBRIDGE_PUBLIC_CHECK_LOG="$STORYBRIDGE_RUN_DIR/public-health.log"
  STORYBRIDGE_PUBLIC_HOST="${STORYBRIDGE_PUBLIC_URL#https://}"
  STORYBRIDGE_PUBLIC_HOST="${STORYBRIDGE_PUBLIC_HOST%%/*}"
  STORYBRIDGE_PUBLIC_HOST="${STORYBRIDGE_PUBLIC_HOST%%:*}"
  STORYBRIDGE_CURL_DNS=()
  if [[ -n "$STORYBRIDGE_PUBLIC_IP" ]]; then
    STORYBRIDGE_CURL_DNS=(--resolve "$STORYBRIDGE_PUBLIC_HOST:443:$STORYBRIDGE_PUBLIC_IP")
  fi
  if ! curl --noproxy '*' --fail --silent --show-error --max-time 8 \
      "${STORYBRIDGE_CURL_DNS[@]}" \
      "$STORYBRIDGE_PUBLIC_URL/readyz" >/dev/null 2>"$STORYBRIDGE_PUBLIC_CHECK_LOG"; then
    echo "Waiting for public HTTPS health check (up to 60 seconds)..."
    STORYBRIDGE_PUBLIC_READY=0
    STORYBRIDGE_PUBLIC_DEADLINE=$((SECONDS + 60))
    while ((SECONDS < STORYBRIDGE_PUBLIC_DEADLINE)); do
      if curl --noproxy '*' --fail --silent --show-error --max-time 5 \
          "${STORYBRIDGE_CURL_DNS[@]}" "$STORYBRIDGE_PUBLIC_URL/readyz" \
          >/dev/null 2>"$STORYBRIDGE_PUBLIC_CHECK_LOG"; then
        STORYBRIDGE_PUBLIC_READY=1
        break
      fi
      kill -0 "$STORYBRIDGE_BACKEND_PID" 2>/dev/null || break
      if [[ -n "$STORYBRIDGE_TUNNEL_PID" ]]; then
        kill -0 "$STORYBRIDGE_TUNNEL_PID" 2>/dev/null || break
      fi
      sleep 2
    done
    if ((!STORYBRIDGE_PUBLIC_READY)); then
      if ((STORYBRIDGE_QUICK_TUNNEL)) \
          && [[ -z "$STORYBRIDGE_PUBLIC_IP" ]] \
          && grep -q "Registered tunnel connection" "$STORYBRIDGE_TUNNEL_LOG"; then
        echo "Cloudflare tunnel is connected, but its public DNS is still propagating." >&2
        echo "The address will remain alive; try it again from the phone shortly." >&2
      else
        echo "Public HTTPS health check failed. The unusable address will not be advertised." >&2
        cat "$STORYBRIDGE_PUBLIC_CHECK_LOG" >&2
        exit 1
      fi
    fi
  fi
fi

echo
echo "StoryBridge is ready ($STORYBRIDGE_MODE mode)."
if ((STORYBRIDGE_SHARE_MODE)); then
  echo "App: $STORYBRIDGE_PUBLIC_URL/"
  echo "打开页面右上角「手机扫码体验」可放大、下载二维码。"
  echo "请保持电脑和此终端运行；临时地址可能随重启变化。"
else
  echo "App:      http://127.0.0.1:5173"
  echo "API docs: http://127.0.0.1:8000/docs"
fi
echo "Press Ctrl+C to stop both services."
echo

set +e
STORYBRIDGE_PIDS=("$STORYBRIDGE_BACKEND_PID")
[[ -n "$STORYBRIDGE_FRONTEND_PID" ]] && STORYBRIDGE_PIDS+=("$STORYBRIDGE_FRONTEND_PID")
[[ -n "$STORYBRIDGE_TUNNEL_PID" ]] && STORYBRIDGE_PIDS+=("$STORYBRIDGE_TUNNEL_PID")
wait -n "${STORYBRIDGE_PIDS[@]}"
STORYBRIDGE_EXIT_STATUS=$?
set -e
if ((STORYBRIDGE_EXIT_STATUS != 0)); then
  echo "A service exited unexpectedly." >&2
  tail -n 40 "$STORYBRIDGE_BACKEND_LOG" >&2 || true
  tail -n 40 "$STORYBRIDGE_FRONTEND_LOG" >&2 || true
fi
exit "$STORYBRIDGE_EXIT_STATUS"
