#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Немає .myenv — створюю..."
  python3 -m venv .myenv
  # shellcheck disable=SC1091
  source .myenv/bin/activate
  pip install -r backend/requirements.txt
else
  # shellcheck disable=SC1091
  source .myenv/bin/activate
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-1}"

EXTRA=()
if [[ "$RELOAD" == "1" ]]; then
  EXTRA+=(--reload)
fi

echo "FastAPI → http://${HOST}:${PORT}"
exec uvicorn backend.app:app --host "$HOST" --port "$PORT" "${EXTRA[@]}"
