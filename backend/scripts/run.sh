#!/usr/bin/env bash
# Start the Forensiq AI backend (FastAPI + Uvicorn).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Creating Python 3.13 virtual environment..."
  python3.13 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip
  ./.venv/bin/python -m pip install -r requirements.txt
fi

echo "Starting Forensiq AI backend on http://127.0.0.1:8000"
exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
