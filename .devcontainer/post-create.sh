#!/bin/bash
# Provision both stacks once, at container-create time.
# This runs BEFORE postStartCommand (the firewall), so installs have open network.
set -euo pipefail

echo "==> Setting up Python backend (.venv + requirements)"
cd /workspace/backend
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> Setting up React frontend (npm install)"
cd /workspace/frontend
npm install

echo "==> Done. Backend venv: backend/.venv  |  Frontend deps installed."
