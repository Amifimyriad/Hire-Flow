#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-./.venv/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Expected Python interpreter at $PYTHON_BIN"
  echo "Create the virtual environment first, or override with PYTHON_BIN=/path/to/python"
  exit 1
fi

"$PYTHON_BIN" -m pip install -r requirements.txt

"$PYTHON_BIN" -m PyInstaller --clean --noconfirm HireFlow.spec
