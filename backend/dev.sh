#!/usr/bin/env bash
# One-step backend setup and run.
# Creates the .venv (if missing), installs requirements, ensures a .env exists,
# then starts the dev server on http://127.0.0.1:5000.
#
# Usage (from anywhere):
#   bash backend/dev.sh
# Or from the backend folder:
#   ./dev.sh

set -euo pipefail

# Always operate relative to this script, not the caller's working directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="$ROOT/.venv/bin/python"
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating virtual environment (.venv) with Python 3.12..."
    py -3.12 -m venv "$ROOT/.venv" 2>/dev/null || python3.12 -m venv "$ROOT/.venv"
    VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
    if [ ! -f "$VENV_PYTHON" ]; then
        VENV_PYTHON="$ROOT/.venv/bin/python"
    fi
else
    echo "Reusing existing virtual environment (.venv)."
fi

echo "Installing dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PYTHON" -m pip install -r "$ROOT/requirements.txt" --quiet

if [ ! -f "$ROOT/.env" ] && [ -f "$ROOT/.env.example" ]; then
    echo "Creating .env from .env.example..."
    cp "$ROOT/.env.example" "$ROOT/.env"
fi

echo "Starting backend on http://127.0.0.1:5000 ..."
exec "$VENV_PYTHON" "$ROOT/run.py"
