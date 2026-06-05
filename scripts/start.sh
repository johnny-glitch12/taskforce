#!/bin/bash
# ----------------------------------------------------------------------------
# Task Force AI — production startup (Railway "web" service).
#
# IMPORTANT module paths for this codebase:
#   FastAPI entry  : backend/server.py        →  uvicorn server:app
#   Celery app     : backend/lib/celery_app.py → celery -A lib.celery_app ...
#
# Runs Celery worker in BG + Uvicorn in FG. If Celery dies the container
# stays up (Uvicorn keeps serving the API). For high-volume production,
# split worker into a dedicated Railway service via Dockerfile.worker
# and set ENABLE_INLINE_CELERY=false on the web service.
# ----------------------------------------------------------------------------
set -euo pipefail

echo "[start.sh] booting Task Force AI (PORT=${PORT:-8000})"

# Resolve to /app/backend regardless of invocation CWD so module imports
# (server, lib.celery_app, etc.) always work.
cd /app/backend

# Optional inline Celery — controlled by ENABLE_INLINE_CELERY (default: true).
# Skipped when no broker URL is configured.
BROKER="${CELERY_BROKER_URL:-${REDIS_URL:-}}"
if [ -n "$BROKER" ] && [ "${ENABLE_INLINE_CELERY:-true}" = "true" ]; then
    echo "[start.sh] launching inline Celery worker (broker=${BROKER:0:24}...)"
    celery -A lib.celery_app worker \
        --loglevel=info \
        --concurrency="${CELERY_CONCURRENCY:-2}" \
        -Q "${CELERY_QUEUES:-default,supernova_eval}" &
    CELERY_PID=$!
    echo "[start.sh] celery PID=$CELERY_PID"
    trap "kill -TERM $CELERY_PID 2>/dev/null || true" SIGTERM SIGINT
else
    echo "[start.sh] inline Celery disabled (no broker / ENABLE_INLINE_CELERY=false)"
fi

# Uvicorn in foreground — PORT comes from Railway.
echo "[start.sh] exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --proxy-headers \
    --forwarded-allow-ips='*'
