#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PID_FILE="$ROOT/backend.pid"
LOG_FILE="$ROOT/backend.log"

# Підхоплює myenv (як на сервері), .venv або venv
pick_venv() {
  for d in myenv .venv venv; do
    if [[ -f "$ROOT/$d/bin/activate" ]]; then
      echo "$d"
      return 0
    fi
  done
  return 1
}

VENV_DIR="$(pick_venv || true)"
if [[ -z "${VENV_DIR}" ]]; then
  VENV_DIR="myenv"
  echo "Створюю ${VENV_DIR}..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$ROOT/$VENV_DIR/bin/activate"

REQ=""
if [[ -f "$ROOT/requirements.txt" ]]; then
  REQ="$ROOT/requirements.txt"
elif [[ -f "$ROOT/backend/requirements.txt" ]]; then
  REQ="$ROOT/backend/requirements.txt"
else
  echo "Немає requirements.txt"
  exit 1
fi

echo "pip install -r ${REQ#"$ROOT/"}"
pip install -q -r "$REQ"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
# У фоні reload за замовчуванням вимкнений (надійніше на проді)
RELOAD="${RELOAD:-0}"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Уже запущено (pid ${OLD_PID}). Зупинити: kill ${OLD_PID}"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

EXTRA=()
if [[ "$RELOAD" == "1" ]]; then
  EXTRA+=(--reload)
fi

nohup uvicorn backend.app:app --host "$HOST" --port "$PORT" "${EXTRA[@]}" \
  >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

echo "venv: ${VENV_DIR}"
echo "FastAPI у фоні → http://${HOST}:${PORT}"
echo "pid: $(cat "$PID_FILE")"
echo "лог: ${LOG_FILE}"
echo "стоп: kill \$(cat ${PID_FILE})"
