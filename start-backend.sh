#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

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
RELOAD="${RELOAD:-1}"

EXTRA=()
if [[ "$RELOAD" == "1" ]]; then
  EXTRA+=(--reload)
fi

echo "venv: ${VENV_DIR}"
echo "FastAPI → http://${HOST}:${PORT}"
exec uvicorn backend.app:app --host "$HOST" --port "$PORT" "${EXTRA[@]}"
