#!/bin/bash
# Dedicated Celery worker entry — for Railway "worker" service.
# Uses `lib.celery_app` (the actual module path in this codebase — NOT
# `backend.celery_app` which doesn't exist).
set -euo pipefail

cd /app/backend
echo "[worker.sh] starting Celery worker (concurrency=${CELERY_CONCURRENCY:-2})"
exec celery -A lib.celery_app worker \
    --loglevel=info \
    --concurrency="${CELERY_CONCURRENCY:-2}" \
    -Q "${CELERY_QUEUES:-default,supernova_eval}"
