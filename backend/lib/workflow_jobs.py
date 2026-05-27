"""
Async Workflow Job Manager — Task Force AI

Extracted from routes/workflow_executor.py.
- _run_async_job: background worker that executes a workflow DAG
- mark_stale_jobs_failed: startup hook that sweeps jobs stuck in 'running' after worker restart
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict


async def _run_async_job(job_id: str, workflow_id: str, user: Dict):
    """Background worker — executes workflow and updates db.workflow_jobs."""
    # Lazy imports to avoid circulars
    from routes.workflow_executor import execute_workflow_dag, _log_run, _build_ctx
    from lib.compute_credits import increment_compute_usage
    from server import db

    user_id = str(user.get("id", user.get("email")))
    try:
        wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id}, {"_id": 0})
        if not wf:
            await db.workflow_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "failed", "error": "Workflow not found", "finished_at": datetime.now(timezone.utc).isoformat()}},
            )
            return

        await db.workflow_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}},
        )
        ctx = _build_ctx(db, user)
        result = await execute_workflow_dag(wf, ctx)
        await increment_compute_usage(db, user)
        run_id = await _log_run(db, user_id, workflow_id, "async", result)

        await db.workflow_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "succeeded" if result["success"] else "failed",
                "result": result,
                "run_id": run_id,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as e:
        await db.workflow_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "failed", "error": str(e)[:300], "finished_at": datetime.now(timezone.utc).isoformat()}},
        )


def schedule_async_job(job_id: str, workflow_id: str, user: Dict) -> None:
    """Fire-and-forget asyncio task (in-process worker)."""
    asyncio.create_task(_run_async_job(job_id, workflow_id, user))


async def mark_stale_jobs_failed(db, max_age_seconds: int = 600) -> int:
    """
    Startup sweeper — any job stuck in 'queued' or 'running' older than max_age
    is marked failed with reason 'worker_restart'. Returns count swept.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    res = await db.workflow_jobs.update_many(
        {
            "status": {"$in": ["queued", "running"]},
            "created_at": {"$lt": cutoff},
        },
        {"$set": {
            "status": "failed",
            "error": "worker_restart — job was orphaned and reaped on startup",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return res.modified_count
