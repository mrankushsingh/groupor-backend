#!/bin/sh
set -eu

PORT="${PORT:-8000}"
echo "groupor: starting uvicorn on 0.0.0.0:${PORT}"
echo "groupor: RAILWAY_ENVIRONMENT=${RAILWAY_ENVIRONMENT:-}"
echo "groupor: DATABASE_URL set=$([ -n "${DATABASE_URL:-}" ] && echo yes || echo no)"
echo "groupor: DATABASE_PRIVATE_URL set=$([ -n "${DATABASE_PRIVATE_URL:-}" ] && echo yes || echo no)"

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
