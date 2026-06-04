#!/bin/bash
# ----------------------------------------------------------------------------
# Single-container production startup — Railway "web" service.
# Runs Celery worker in background + FastAPI/Uvicorn in foreground.
# ----------------------------------------------------------------------------
set -e

cd /app/backend

# Optional: launch Celery in the background only when a broker is configured
# AND the operator opts in. For high-volume production split into a dedicated
# Railway worker service using Dockerfile.worker.
if [ -n "${CELERY_BROKER_URL}${REDIS_URL}" ] && [ "${ENABLE_INLINE_CELERY:-true}" = "true" ]; then
    echo "[start.sh] launching inline Celery worker..."
    celery -A lib.celery_app worker \
        --loglevel=info \
        --concurrency="${CELERY_CONCURRENCY:-2}" \
        -Q "${CELERY_QUEUES:-default,supernova_eval}" &
    CELERY_PID=$!
    echo "[start.sh] celery PID=$CELERY_PID"

    # Ensure Celery dies when the container is terminated.
    trap "kill -TERM $CELERY_PID 2>/dev/null || true" SIGTERM SIGINT
else
    echo "[start.sh] inline Celery disabled (no broker / ENABLE_INLINE_CELERY=false)"
fi

# Uvicorn in foreground — PORT comes from Railway.
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --proxy-headers \
    --forwarded-allow-ips='*'
