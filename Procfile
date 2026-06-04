web: bash scripts/start.sh
worker: cd backend && celery -A lib.celery_app worker --loglevel=info --concurrency=${CELERY_CONCURRENCY:-2} -Q ${CELERY_QUEUES:-default,supernova_eval}
beat: cd backend && celery -A lib.celery_app beat --loglevel=info
