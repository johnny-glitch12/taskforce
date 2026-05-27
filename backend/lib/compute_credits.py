"""
Compute Credits Kill Switch — Middleware that enforces execution limits per tier.

Tiers:
  - recruit (free): 100 executions/month
  - cadet ($19):    500 executions/month
  - operator ($99): 2000 executions/month
  - admin/pro:      unlimited

Tracks usage in MongoDB `compute_usage` collection with monthly rollover.
"""
import os
from datetime import datetime, timezone
from fastapi import HTTPException

TIER_LIMITS = {
    "free": 100,
    "recruit": 100,
    "cadet": 500,
    "operator": 2000,
    "pro": 999999,
    "admin": 999999,
}


def _current_period():
    """Return YYYY-MM string for the current billing period."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def check_compute_credits(db, user: dict):
    """
    Check if user has remaining compute credits for this billing period.
    Raises HTTPException 403 if limit reached.
    Returns dict with usage info.
    """
    user_id = user.get("id", user.get("email", "unknown"))
    tier = user.get("tier", "free")
    role = user.get("role", "user")

    # Admin and pro users are unlimited
    if role == "admin" or tier in ("pro", "admin"):
        return {"allowed": True, "used": 0, "limit": 999999, "tier": tier}

    limit = TIER_LIMITS.get(tier, 100)
    period = _current_period()

    # Get or create usage doc for this period
    usage = await db.compute_usage.find_one({
        "user_id": user_id,
        "period": period,
    })

    used = usage["count"] if usage else 0

    if used >= limit:
        tier_label = tier.upper() if tier != "free" else "RECRUIT"
        return {
            "allowed": False,
            "error": "COMPUTE_LIMIT_REACHED",
            "message": f"Execution limit reached ({used}/{limit} this month). Your {tier_label} plan allows {limit} executions/month.",
            "used": used,
            "limit": limit,
            "tier": tier,
            "upgrade_url": "/pricing",
            "upgrade_prompt": "Upgrade your plan to unlock more executions.",
        }

    return {"allowed": True, "used": used, "limit": limit, "tier": tier}


async def increment_compute_usage(db, user: dict):
    """Increment the user's compute usage counter for this period."""
    user_id = user.get("id", user.get("email", "unknown"))
    period = _current_period()

    await db.compute_usage.update_one(
        {"user_id": user_id, "period": period},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {
                "user_id": user_id,
                "period": period,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )


async def get_compute_status(db, user: dict):
    """Return current compute credit status for a user."""
    user_id = user.get("id", user.get("email", "unknown"))
    tier = user.get("tier", "free")
    role = user.get("role", "user")
    # Normalize "free" to "recruit" for consistency
    display_tier = "recruit" if tier == "free" else tier
    limit = TIER_LIMITS.get(tier, 100)
    period = _current_period()

    if role == "admin" or tier in ("pro", "admin"):
        return {"used": 0, "limit": 999999, "remaining": 999999, "tier": display_tier, "period": period, "unlimited": True}

    usage = await db.compute_usage.find_one({"user_id": user_id, "period": period})
    used = usage["count"] if usage else 0

    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "tier": display_tier,
        "period": period,
        "unlimited": False,
    }
