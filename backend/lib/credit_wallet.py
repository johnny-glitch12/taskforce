"""
Credit Wallet — Emergent-style credits for The Armory.

Each user has a `credit_balance` (int) on their user doc. Actions debit credits:
  - build_bot     : 5 credits (LLM-intensive)
  - workflow_run  : 1 credit  (per execution)
  - bot_deploy    : 0 credits (free; gated by purchase instead)

Top up via:
  - Tier auto-recharge (monthly) — handled by subscriptions.py grant_monthly_credits
  - Stripe one-time top-up packs (handled by routes/credits.py /topup)
  - Promo code redemption
  - Admin grant

Transactions are persisted in `credit_transactions` (immutable ledger).
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any

ACTION_COSTS = {
    "build_bot": 5,
    "workflow_run": 1,
    "bot_deploy": 0,
}

TIER_MONTHLY_GRANT = {
    "free":     50,
    "recruit":  50,
    "cadet":    500,
    "operator": 2000,
    "pro":      10_000,
}

ADMIN_UNLIMITED = 10**9  # virtual "infinity" for admin views


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_balance(db, user: dict) -> Dict[str, Any]:
    """Read the user's current credit balance + tier info."""
    user_id = str(user.get("id", user.get("email")))
    if user.get("role") == "admin":
        return {
            "balance": ADMIN_UNLIMITED,
            "tier": "admin",
            "unlimited": True,
            "monthly_grant": ADMIN_UNLIMITED,
        }
    doc = await db.users.find_one({"id": user_id}) or await db.users.find_one({"email": user.get("email")})
    tier = (doc or {}).get("tier") or user.get("tier") or "free"
    balance = int((doc or {}).get("credit_balance") or 0)
    return {
        "balance": balance,
        "tier": tier,
        "unlimited": False,
        "monthly_grant": TIER_MONTHLY_GRANT.get(tier, 50),
    }


async def can_afford(db, user: dict, action: str) -> Dict[str, Any]:
    """Non-mutating check — does the user have enough credits for `action`?"""
    cost = ACTION_COSTS.get(action, 1)
    if user.get("role") == "admin":
        return {"allowed": True, "cost": cost, "balance": ADMIN_UNLIMITED, "unlimited": True}
    info = await get_balance(db, user)
    if info["balance"] >= cost:
        return {"allowed": True, "cost": cost, "balance": info["balance"], "unlimited": False}
    return {
        "allowed": False,
        "error": "INSUFFICIENT_CREDITS",
        "message": f"Need {cost} credits, you have {info['balance']}. Top up or upgrade your plan.",
        "cost": cost,
        "balance": info["balance"],
        "tier": info["tier"],
        "upgrade_url": "/pricing",
        "topup_url": "/credits",
    }


async def debit(db, user: dict, action: str, ref: Optional[str] = None) -> Dict[str, Any]:
    """
    Atomically deduct credits for `action` from the user's balance and append a
    `credit_transactions` ledger entry. Returns the updated balance + cost.
    Caller MUST have called `can_afford` first if a clean error is desired —
    this raises ValueError on insufficient funds.
    """
    cost = ACTION_COSTS.get(action, 1)
    if user.get("role") == "admin":
        # Admin runs are still logged but never debited.
        await _ledger(db, user, -cost, action, ref, note="admin (uncharged)", new_balance=ADMIN_UNLIMITED, virtual=True)
        return {"balance": ADMIN_UNLIMITED, "cost": cost, "unlimited": True}

    user_id = str(user.get("id", user.get("email")))
    # Atomic conditional update: only debit if balance >= cost.
    res = await db.users.find_one_and_update(
        {"$or": [{"id": user_id}, {"email": user.get("email")}], "credit_balance": {"$gte": cost}},
        {"$inc": {"credit_balance": -cost}, "$set": {"updated_at": _now_iso()}},
        return_document=True,
    )
    if not res:
        raise ValueError(f"insufficient_credits: need {cost}")
    new_balance = int(res.get("credit_balance") or 0)
    await _ledger(db, user, -cost, action, ref, note=f"{action} run", new_balance=new_balance)
    return {"balance": new_balance, "cost": cost, "unlimited": False}


async def credit(db, user: dict, amount: int, source: str, ref: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
    """Add credits to a user's wallet (top-up, promo, tier-grant, admin)."""
    if amount <= 0:
        raise ValueError("amount must be > 0")
    user_id = str(user.get("id", user.get("email")))
    res = await db.users.find_one_and_update(
        {"$or": [{"id": user_id}, {"email": user.get("email")}]},
        {"$inc": {"credit_balance": amount}, "$set": {"updated_at": _now_iso()}},
        return_document=True,
        upsert=False,
    )
    new_balance = int((res or {}).get("credit_balance") or amount)
    await _ledger(db, user, amount, source, ref, note=note or f"+{amount} via {source}", new_balance=new_balance)
    return {"balance": new_balance, "added": amount}


async def list_transactions(db, user: dict, limit: int = 50):
    user_id = str(user.get("id", user.get("email")))
    cursor = db.credit_transactions.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)


async def _ledger(db, user: dict, delta: int, kind: str, ref: Optional[str], note: str, new_balance: int, virtual: bool = False):
    user_id = str(user.get("id", user.get("email")))
    await db.credit_transactions.insert_one({
        "user_id": user_id,
        "email": user.get("email"),
        "delta": int(delta),
        "kind": kind,                  # "build_bot" | "workflow_run" | "topup" | "promo" | "tier_grant" | "admin_grant"
        "ref": ref,                    # listing id / stripe session id / promo code, etc.
        "note": note,
        "balance_after": int(new_balance),
        "virtual": virtual,
        "created_at": _now_iso(),
    })
