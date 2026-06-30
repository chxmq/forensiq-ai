#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Forensiq AI — one-command launcher (backend + frontend + demo seed)
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "▶ Forensiq AI — Intelligent Document Integrity System"
echo "──────────────────────────────────────────────────────"

# 1. Backend environment
cd backend
if [ ! -d ".venv" ]; then
  echo "• Creating Python 3.13 virtual environment & installing dependencies..."
  python3.13 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip --quiet
  ./.venv/bin/python -m pip install -r requirements.txt
fi

# 2. Bootstrap demo data (only seeds when database is empty)
echo "• Bootstrapping database (seed only if empty)..."
./.venv/bin/python -m scripts.bootstrap >/dev/null

# 3. Launch backend
echo "• Starting backend on http://127.0.0.1:8000"
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >/tmp/forensiq-backend.log 2>&1 &
BACKEND_PID=$!
cd "$ROOT"

# 4. Frontend
cd frontend
if [ ! -d "node_modules" ]; then
  echo "• Installing frontend dependencies..."
  npm install --silent
fi
echo "• Starting frontend on http://localhost:5173"
npm run dev &
FRONTEND_PID=$!
cd "$ROOT"

echo "──────────────────────────────────────────────────────"
echo "✓ Forensiq AI is running:"
echo "    Frontend  →  http://localhost:5173"
echo "    API docs  →  http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to stop."

trap "echo; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0" INT TERM
wait
