#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || {
  printf 'Jarvis Gateway requires Python 3.\n' >&2
  exit 1
}

if ! "${PYTHON_BIN}" -c 'import fastapi, pydantic, requests, uvicorn' >/dev/null 2>&1; then
  printf 'Jarvis Gateway dependencies are missing. Install them in a virtual environment with:\n' >&2
  printf '  %s -m pip install -r "%s/requirements.txt"\n' "${PYTHON_BIN}" "${APP_DIR}" >&2
  exit 1
fi

cd "${APP_DIR}/src"
exec "${PYTHON_BIN}" gateway.py "$@"
