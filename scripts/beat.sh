#!/bin/bash
# Dedicated Celery beat entry — for Railway "beat" service (scheduled tasks).
# Uses `lib.celery_app` (the actual module path in this codebase — NOT
# `backend.celery_app` which doesn't exist).
set -euo pipefail

cd /app/backend
echo "[beat.sh] starting Celery beat scheduler"
exec celery -A lib.celery_app beat \
    --loglevel=info \
    --schedule="/tmp/celerybeat-schedule"
