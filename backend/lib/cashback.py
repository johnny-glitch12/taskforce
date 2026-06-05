"""
cashback — 5% spending cashback, granted silently in 100-credit chunks.

Why silent (no "X/100 progress" bar): variable-ratio reward schedules are far
more engaging than fixed-progress meters (slot-machine effect). The user gets
a surprise +5 credits every now and then which keeps them spending.

Why 100-credit chunks (not real-time 5% on every debit): integer math gets ugly
at small spend (debiting 3 credits would otherwise grant 0.15 cashback). The
accumulator pattern means every 100 credits spent crosses a clean line and the
ratio works out to exactly 5%.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("cashback")

CASHBACK_RATE: float = 0.05         # 5% — small enough that 100-cr threshold gives a satisfying +5
CASHBACK_THRESHOLD: int = 100       # accumulate up to N before granting


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def accrue_and_grant(db, user: dict, credits_spent: int) -> dict:
    """Bump the user's accumulator and grant cashback if a threshold is crossed.

    Returns: {cashback_granted: int, accumulator: int}.
    Never raises — silent failure preferred over user-facing error from a perk.
    Caller can ignore the return value if they don't want to surface a toast.
    """
    if credits_spent <= 0:
        return {"cashback_granted": 0, "accumulator": 0}
    user_id = user.get("id") or user.get("_id")
    if not user_id:
        return {"cashback_granted": 0, "accumulator": 0}

    try:
        updated = await db.users.find_one_and_update(
            {"id": user_id},
            {"$inc": {"cashback_accumulator": int(credits_spent)}},
            return_document=True,
        )
        if not updated:
            return {"cashback_granted": 0, "accumulator": 0}

        accumulator = int(updated.get("cashback_accumulator") or 0)
        if accumulator < CASHBACK_THRESHOLD:
            return {"cashback_granted": 0, "accumulator": accumulator}

        # We may have crossed multiple thresholds in one big spend.
        cashback = int((accumulator // CASHBACK_THRESHOLD) * CASHBACK_THRESHOLD * CASHBACK_RATE)
        remainder = accumulator % CASHBACK_THRESHOLD

        granted = await db.users.find_one_and_update(
            {"id": user_id},
            {"$inc": {"topup_credits": cashback,
                      "cashback_earned_total": cashback},
             "$set": {"cashback_accumulator": remainder,
                      "last_cashback_at": _now_iso()}},
            return_document=True,
        )

        await db.credit_transactions.insert_one({
            "id": f"cashback-{uuid.uuid4().hex[:10]}",
            "user_id": user_id,
            "action": "cashback_reward",
            "amount": cashback,
            "metadata": {
                "rate": CASHBACK_RATE,
                "trigger_spend": accumulator - remainder,
                "remainder_after": remainder,
            },
            "sub_remaining":   (granted or {}).get("subscription_credits", 0),
            "topup_remaining": (granted or {}).get("topup_credits", cashback),
            "created_at": _now_iso(),
        })
        logger.info(f"[cashback] +{cashback} cr granted to user={user_id} (accum→{remainder})")
        return {"cashback_granted": cashback, "accumulator": remainder}
    except Exception as e:
        # Silent failure — a broken perk should NEVER break the debit it follows.
        logger.warning(f"[cashback] accrue failed for user={user_id}: {e}")
        return {"cashback_granted": 0, "accumulator": 0}


async def pending_cashback_for(db, user_id: str) -> dict:
    """For the FE Earnings dashboard: how many credits earned via cashback,
    and unredeemed accumulator (we surface this on the dashboard but NOT in
    a progress bar — keeps the surprise alive)."""
    u = await db.users.find_one({"id": user_id},
                                {"cashback_accumulator": 1,
                                 "cashback_earned_total": 1,
                                 "_id": 0})
    return {
        "lifetime_earned": int((u or {}).get("cashback_earned_total") or 0),
        "accumulator":     int((u or {}).get("cashback_accumulator") or 0),
    }


__all__ = [
    "accrue_and_grant",
    "pending_cashback_for",
    "CASHBACK_RATE",
    "CASHBACK_THRESHOLD",
]
