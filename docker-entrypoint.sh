#!/usr/bin/env bash
set -euo pipefail
cd /app/backend

echo "▶ Forensiq AI — bootstrapping..."
python -m scripts.bootstrap

PORT="${PORT:-8000}"
echo "▶ Starting server on 0.0.0.0:${PORT}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --log-level info
