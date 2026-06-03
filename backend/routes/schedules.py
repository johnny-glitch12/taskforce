"""
Scheduled executions — preset-interval scheduling for user_bot_deployments.

P2 launch: 4 preset intervals only (hourly / 6h / daily / weekly). No raw cron.
Adding a custom-cron mode is a future ENH — the schedule doc shape supports it
(interval_minutes is the source of truth).

Storage shape on user_bot_deployments:
    schedule: {
        enabled: bool,
        preset: "hourly" | "6h" | "daily" | "weekly",
        interval_minutes: int,
        next_run_at: ISO str,
        last_run_at: ISO str | null,
        last_run_id: str | null,
        last_run_success: bool | null,
        created_at, updated_at,
    }

Tick:
    `tick_scheduled_runs(db)` is invoked every 5 minutes by APScheduler. It
    finds every deployment whose `schedule.enabled = true` AND `schedule.next_run_at <= now`,
    runs them (best-effort, via `run_deployment_real`), and bumps next_run_at
    to now + interval_minutes. Per-month usage caps are honoured.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("schedules")
router = APIRouter()


PRESETS = {
    # label, interval_in_minutes
    "hourly":  ("Every hour",   60),
    "6h":      ("Every 6 hours", 60 * 6),
    "daily":   ("Once a day",    60 * 24),
    "weekly":  ("Once a week",   60 * 24 * 7),
}


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _user_id(u: dict) -> str:
    return str(u.get("id", u.get("email")))


class ScheduleRequest(BaseModel):
    enabled: bool
    preset: Optional[str] = Field(default=None, pattern="^(hourly|6h|daily|weekly)$")


@router.get("/deployments/{deployment_id}/schedule")
async def get_schedule(deployment_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = _user_id(user)
    doc = await db.user_bot_deployments.find_one(
        {"id": deployment_id, "user_id": user_id},
        {"_id": 0, "schedule": 1, "id": 1, "config": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    sched = doc.get("schedule") or {"enabled": False, "preset": None}
    return {
        "schedule": sched,
        "presets": [
            {"id": k, "label": v[0], "interval_minutes": v[1]} for k, v in PRESETS.items()
        ],
    }


@router.put("/deployments/{deployment_id}/schedule")
async def upsert_schedule(deployment_id: str, body: ScheduleRequest,
                          user=Depends(get_current_user())):
    db = get_db()
    user_id = _user_id(user)
    doc = await db.user_bot_deployments.find_one(
        {"id": deployment_id, "user_id": user_id},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    if not body.enabled:
        await db.user_bot_deployments.update_one(
            {"id": deployment_id, "user_id": user_id},
            {"$set": {
                "schedule.enabled": False,
                "schedule.updated_at": _now(),
                "updated_at": _now(),
            }},
        )
        fresh = await db.user_bot_deployments.find_one(
            {"id": deployment_id}, {"_id": 0, "schedule": 1},
        )
        return {"success": True, "schedule": fresh.get("schedule")}

    if not body.preset or body.preset not in PRESETS:
        raise HTTPException(status_code=422, detail="preset is required when enabled=true")

    interval = PRESETS[body.preset][1]
    existing = doc.get("schedule") or {}
    next_run = (_now_dt() + timedelta(minutes=interval)).isoformat()
    schedule = {
        "enabled": True,
        "preset": body.preset,
        "interval_minutes": interval,
        "next_run_at": next_run,
        "last_run_at": existing.get("last_run_at"),
        "last_run_id": existing.get("last_run_id"),
        "last_run_success": existing.get("last_run_success"),
        "created_at": existing.get("created_at") or _now(),
        "updated_at": _now(),
    }
    await db.user_bot_deployments.update_one(
        {"id": deployment_id, "user_id": user_id},
        {"$set": {"schedule": schedule, "updated_at": _now()}},
    )
    return {"success": True, "schedule": schedule}


async def tick_scheduled_runs(db) -> int:
    """Called by APScheduler. Returns the number of scheduled runs dispatched."""
    from routes.credits_and_more import run_deployment_real

    now_iso = _now_dt().isoformat()
    candidates = await db.user_bot_deployments.find(
        {"schedule.enabled": True, "schedule.next_run_at": {"$lte": now_iso}},
        {"_id": 0},
    ).to_list(length=200)

    dispatched = 0
    for d in candidates:
        sched = d.get("schedule") or {}
        usage = d.get("usage") or {}
        # Respect per-month run caps. If hit, disable schedule to stop churning.
        if usage.get("run_count", 0) >= usage.get("limit_per_month", 1000):
            await db.user_bot_deployments.update_one(
                {"id": d["id"]},
                {"$set": {
                    "schedule.enabled": False,
                    "schedule.last_disabled_reason": "limit_reached",
                    "schedule.updated_at": _now(),
                }},
            )
            logger.info(f"[sched] deployment {d['id']} hit run limit — schedule auto-disabled")
            continue
        try:
            run = await run_deployment_real(db, d, trigger="schedule", input_payload={})
            dispatched += 1
            interval = int(sched.get("interval_minutes") or 60)
            next_run = (_now_dt() + timedelta(minutes=interval)).isoformat()
            await db.user_bot_deployments.update_one(
                {"id": d["id"]},
                {"$set": {
                    "schedule.next_run_at": next_run,
                    "schedule.last_run_at": _now(),
                    "schedule.last_run_id": run["id"],
                    "schedule.last_run_success": bool(run.get("success")),
                    "schedule.updated_at": _now(),
                }},
            )
        except Exception as e:
            logger.warning(f"[sched] run failed for deployment {d['id']}: {e}")
            # Don't disable — try again next tick. Bump next_run forward so
            # we don't hammer a broken deployment in tight loop.
            interval = int(sched.get("interval_minutes") or 60)
            next_run = (_now_dt() + timedelta(minutes=interval)).isoformat()
            await db.user_bot_deployments.update_one(
                {"id": d["id"]},
                {"$set": {
                    "schedule.next_run_at": next_run,
                    "schedule.last_error": str(e)[:500],
                    "schedule.updated_at": _now(),
                }},
            )
    return dispatched


__all__ = ["router", "tick_scheduled_runs", "PRESETS"]
