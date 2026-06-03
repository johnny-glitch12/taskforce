"""
In-app notifications — Prompt 9 follow-on.

Backend for the bell-icon UI. The `notifications` collection is already being
written to by routes.bounties._emit_notification on submit/win/lose events.
This module exposes the read-side:

    GET    /api/notifications?limit=20&unread_only=false
    GET    /api/notifications/unread-count
    POST   /api/notifications/{id}/read
    POST   /api/notifications/mark-all-read

Notification doc shape (set elsewhere):
    {id, user_id, kind, message, payload?, read, created_at, read_at?}
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id(u: dict) -> str:
    return str(u.get("id", u.get("email")))


@router.get("/notifications")
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = False,
    user=Depends(get_current_user()),
):
    db = get_db()
    q = {"user_id": _user_id(user)}
    if unread_only:
        q["read"] = False
    cursor = db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    unread = await db.notifications.count_documents({"user_id": _user_id(user), "read": False})
    return {"items": items, "unread": unread}


@router.get("/notifications/unread-count")
async def unread_count(user=Depends(get_current_user())):
    """Lightweight endpoint used by the bell badge — frequent polling target."""
    db = get_db()
    n = await db.notifications.count_documents({"user_id": _user_id(user), "read": False})
    return {"unread": n}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user=Depends(get_current_user())):
    db = get_db()
    res = await db.notifications.update_one(
        {"id": notification_id, "user_id": _user_id(user)},
        {"$set": {"read": True, "read_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"success": True}


@router.post("/notifications/mark-all-read")
async def mark_all_read(user=Depends(get_current_user())):
    db = get_db()
    res = await db.notifications.update_many(
        {"user_id": _user_id(user), "read": False},
        {"$set": {"read": True, "read_at": _now()}},
    )
    return {"success": True, "marked": res.modified_count}


__all__ = ["router"]
