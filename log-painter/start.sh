#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUNTIME_DIR="$ROOT_DIR/.runtime"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
LOG_PAINTER_HOST="${LOG_PAINTER_HOST:-0.0.0.0}"
LOG_PAINTER_PORT="${LOG_PAINTER_PORT:-5173}"
LOG_PAINTER_ALLOWED_HOSTS="${LOG_PAINTER_ALLOWED_HOSTS:-.velinithra.space,localhost,127.0.0.1}"
LOG_PAINTER_EXPORT_TARGET="${LOG_PAINTER_EXPORT_TARGET:-http://localhost:${BACKEND_PORT}}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$BACKEND_DIR/.venv"

mkdir -p "$RUNTIME_DIR"

backend_pid="$RUNTIME_DIR/backend.pid"
frontend_pid="$RUNTIME_DIR/frontend.pid"
backend_log="$RUNTIME_DIR/backend.log"
frontend_log="$RUNTIME_DIR/frontend.log"

usage() {
  cat <<EOF
Usage: ./start.sh [start|stop|restart|status|logs]

Default command: start

Environment overrides:
  BACKEND_PORT=8000
  LOG_PAINTER_PORT=5173
  LOG_PAINTER_HOST=0.0.0.0
  LOG_PAINTER_ALLOWED_HOSTS=.velinithra.space,localhost,127.0.0.1
  LOG_PAINTER_EXPORT_TARGET=http://localhost:8000
EOF
}

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing command: $command_name" >&2
    exit 1
  fi
}

install_backend_deps() {
  require_command "$PYTHON_BIN"

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  if "$VENV_DIR/bin/python" -c "import fastapi, uvicorn, yaml" >/dev/null 2>&1; then
    return
  fi

  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
}

install_frontend_deps() {
  require_command npm

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    (cd "$FRONTEND_DIR" && npm ci)
  fi
}

build_frontend() {
  (cd "$FRONTEND_DIR" && npm run build)
}

start_backend() {
  if is_running "$backend_pid"; then
    echo "Backend already running, pid $(cat "$backend_pid")"
    return
  fi

  nohup bash -lc "cd '$BACKEND_DIR' && exec '$VENV_DIR/bin/python' -m uvicorn main:app --host '$BACKEND_HOST' --port '$BACKEND_PORT'" \
    >"$backend_log" 2>&1 &
  echo $! >"$backend_pid"
  echo "Backend started: http://localhost:$BACKEND_PORT (pid $(cat "$backend_pid"))"
}

start_frontend() {
  if is_running "$frontend_pid"; then
    echo "Frontend already running, pid $(cat "$frontend_pid")"
    return
  fi

  nohup bash -lc "cd '$FRONTEND_DIR' && LOG_PAINTER_HOST='$LOG_PAINTER_HOST' LOG_PAINTER_PORT='$LOG_PAINTER_PORT' LOG_PAINTER_ALLOWED_HOSTS='$LOG_PAINTER_ALLOWED_HOSTS' LOG_PAINTER_EXPORT_TARGET='$LOG_PAINTER_EXPORT_TARGET' exec npm run preview" \
    >"$frontend_log" 2>&1 &
  echo $! >"$frontend_pid"
  echo "Frontend started: http://localhost:$LOG_PAINTER_PORT (pid $(cat "$frontend_pid"))"
}

start_all() {
  install_backend_deps
  install_frontend_deps
  build_frontend
  start_backend
  start_frontend
  echo
  echo "Open: http://localhost:$LOG_PAINTER_PORT"
  echo "Logs: ./start.sh logs"
  echo "Stop: ./start.sh stop"
}

stop_one() {
  local name="$1"
  local pid_file="$2"

  if ! is_running "$pid_file"; then
    echo "$name is not running"
    rm -f "$pid_file"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  kill "$pid"
  rm -f "$pid_file"
  echo "$name stopped"
}

stop_all() {
  stop_one "Frontend" "$frontend_pid"
  stop_one "Backend" "$backend_pid"
}

status_one() {
  local name="$1"
  local pid_file="$2"

  if is_running "$pid_file"; then
    echo "$name: running, pid $(cat "$pid_file")"
  else
    echo "$name: stopped"
  fi
}

status_all() {
  status_one "Backend" "$backend_pid"
  status_one "Frontend" "$frontend_pid"
}

show_logs() {
  echo "Backend log: $backend_log"
  tail -n 80 "$backend_log" 2>/dev/null || true
  echo
  echo "Frontend log: $frontend_log"
  tail -n 80 "$frontend_log" 2>/dev/null || true
}

command="${1:-start}"

case "$command" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  logs)
    show_logs
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
