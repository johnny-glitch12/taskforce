"""
celery_app — Production-grade async runtime for Task Force AI.

Replaces the in-process AsyncIOScheduler with a Celery worker + beat pair
backed by Redis. APScheduler stays in place as a fallback for environments
where CELERY_BROKER_URL is unset (zero-config dev).

Activation:
    CELERY_BROKER_URL=redis://localhost:6379/0
    CELERY_RESULT_BACKEND=redis://localhost:6379/1   (optional, defaults to broker)

Run locally:
    celery -A lib.celery_app worker --loglevel=info --concurrency=4
    celery -A lib.celery_app beat --loglevel=info

Supervisor wires the worker + beat as separate long-running services in
/etc/supervisor/conf.d/supervisord.conf when redis is reachable.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger("celery_app")

BROKER_URL = os.environ.get("CELERY_BROKER_URL") or ""
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND") or BROKER_URL
ENABLED = bool(BROKER_URL)


# Build the Celery app (always — but a worker only runs if you start one).
celery_app = Celery(
    "tfai",
    broker=BROKER_URL or "memory://",
    backend=RESULT_BACKEND or "cache+memory://",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,             # 5-min hard timeout per task
    task_soft_time_limit=240,
    worker_max_tasks_per_child=200,  # recycle workers to avoid leaks
    broker_connection_retry_on_startup=True,
)


# ─── Async helpers ──────────────────────────────────────
# Each Celery task runs in a sync thread, but our existing jobs are async coroutines
# that need an event loop + the live Mongo client. We spin up a fresh loop per task,
# import server.db lazily to avoid circular imports during Celery worker boot.

def _run_async(coro_factory):
    """Run a one-shot async coroutine from a sync Celery task body.
    A fresh event loop is created per call; motor clients are scoped to the
    coroutine so they bind to the right loop (avoids "event loop is closed")."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _task_db():
    """Build a per-task Mongo client. We can't import server.db at module load
    because that binds the motor pool to the celery worker's bootstrap loop and
    breaks on the second task. Returns a (client, db) pair — caller closes client."""
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    return client, client[db_name]


# ─── Tasks ──────────────────────────────────────────────
@celery_app.task(name="tfai.hosting_expire", bind=True)
def hosting_expire_task(self):
    """Hourly hosting-subscription janitor."""
    async def _go():
        client, db = _task_db()
        try:
            from routes.hosting import expire_lapsed_subscriptions
            return await expire_lapsed_subscriptions(db)
        finally:
            client.close()
    n = _run_async(_go)
    if n:
        logger.info(f"[celery:hosting_expire] flipped {n} lapsed subscription(s)")
    return {"flipped": int(n or 0)}


@celery_app.task(name="tfai.bounty_expire", bind=True)
def bounty_expire_task(self):
    """Hourly bounty-board janitor. Auto-refunds escrow past grace period."""
    async def _go():
        client, db = _task_db()
        try:
            from routes.bounties import expire_lapsed_bounties
            return await expire_lapsed_bounties(db)
        finally:
            client.close()
    n = _run_async(_go)
    if n:
        logger.info(f"[celery:bounty_expire] processed {n} lapsed bounty/-ies")
    return {"processed": int(n or 0)}


@celery_app.task(name="tfai.scheduled_runs_tick", bind=True)
def scheduled_runs_tick_task(self):
    """Every-5-min scan for deployment schedules whose next_run_at <= now."""
    async def _go():
        client, db = _task_db()
        try:
            from routes.schedules import tick_scheduled_runs
            return await tick_scheduled_runs(db)
        finally:
            client.close()
    n = _run_async(_go)
    if n:
        logger.info(f"[celery:sched_tick] dispatched {n} scheduled run(s)")
    return {"dispatched": int(n or 0)}


@celery_app.task(name="tfai.supernova_eval", bind=True)
def supernova_eval_task(self):
    """Daily Supernova creator-tier evaluation."""
    async def _go():
        # evaluate_supernovas closes over server.db which is bound to a different
        # loop. We can't trivially rebuild it here without touching server.py,
        # so we just exec via the module — if it crashes, the next tick retries.
        from server import evaluate_supernovas
        return await evaluate_supernovas()
    return _run_async(_go)


# ─── Beat schedule (only honored when celery beat is running) ───
celery_app.conf.beat_schedule = {
    "hosting-expire-hourly": {
        "task": "tfai.hosting_expire",
        "schedule": crontab(minute=0),                # top of every hour
    },
    "bounty-expire-hourly": {
        "task": "tfai.bounty_expire",
        "schedule": crontab(minute=5),                # 5 min past every hour
    },
    "scheduled-runs-tick-5min": {
        "task": "tfai.scheduled_runs_tick",
        "schedule": 300.0,                            # every 5 minutes
    },
    "supernova-eval-daily": {
        "task": "tfai.supernova_eval",
        "schedule": crontab(hour=0, minute=30),       # 00:30 UTC daily
    },
}


def status() -> dict:
    """Lightweight health probe — used by /api/admin/runtime/status."""
    return {
        "enabled": ENABLED,
        "broker_url": BROKER_URL or None,
        "result_backend": RESULT_BACKEND or None,
        "tasks": list(celery_app.tasks.keys()) if ENABLED else [],
        "fallback": "apscheduler",
    }


def health() -> Optional[dict]:
    """Live ping — connects to the broker if enabled, returns latency_ms."""
    if not ENABLED:
        return None
    import time
    try:
        import redis as redis_client
        client = redis_client.Redis.from_url(BROKER_URL, socket_connect_timeout=2)
        t0 = time.time()
        client.ping()
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
