"""
Credit Wallet — Emergent-style DUAL-POOL credits for Task Force AI.

Each user has TWO credit pools on their user document:
  - `subscription_credits`     : monthly allocation, RESETS each billing cycle
  - `subscription_credits_max` : current tier's allocation (for UI ring + reset)
  - `topup_credits`            : purchased credits, NEVER expire
  - `credit_reset_date`        : ISO timestamp of next reset (Stripe `invoice.paid`)

Deduction priority: subscription first, then topup. This way users never burn
purchased credits while their free monthly allocation is still available.

Top up via:
  - Tier monthly reset (Stripe `invoice.paid` webhook → `reset_subscription`)
  - Stripe one-time top-up packs (`/credits/topup/poll/{sid}` → credits to topup_credits)
  - Promo code redemption (`credits` kind → adds to topup_credits)
  - Admin grant

Action costs:
  - vibe_chat          : 0  (free — chatting is free like Emergent)
  - build_bot          : 5  (LLM code generation)
  - workflow_run       : 1  (per Armory execution)
  - bot_deploy         : 0  (free; pay listing price separately)
  - agent_run          : 1  (per execution of a deployed agent)
  - external_agent_run : 2  (externally-uploaded agents, more compute)
  - publish_listing    : 0  (free to list)

Transactions are persisted in the immutable `credit_transactions` collection with
both `sub_deducted` / `topup_deducted` (debits) and the post-update `sub_remaining`
/ `topup_remaining` snapshot for full auditability.

Legacy migration: if a user has `credit_balance` but no `subscription_credits` /
`topup_credits` fields yet, the first `get_balance` call splits the old number —
min(balance, tier_allocation) → subscription, remainder → topup — and unsets
the legacy field.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any


ACTION_COSTS = {
    "vibe_chat":          1,
    "build_bot":          5,
    "workflow_run":       1,
    "bot_deploy":         0,
    "agent_run":          1,
    "external_agent_run": 2,
    "publish_listing":    0,
}


TIER_MONTHLY_GRANT = {
    "free":     50,
    "recruit":  50,
    "cadet":    500,
    "operator": 2000,
    "pro":      10_000,
    "command":  10_000,
}


ADMIN_UNLIMITED = 10**9  # virtual "infinity" for admin views


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_reset_iso(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _user_filter(user: dict) -> dict:
    """Lookup filter that works for both id-keyed and email-keyed users."""
    user_id = str(user.get("id", user.get("email")))
    return {"$or": [{"id": user_id}, {"email": user.get("email")}]}


async def _migrate_if_needed(db, user: dict, doc: dict) -> dict:
    """One-shot legacy migration: split `credit_balance` into sub/topup."""
    if doc is None:
        return doc
    if "subscription_credits" in doc and "topup_credits" in doc:
        return doc  # already migrated

    tier = doc.get("tier") or user.get("tier") or "recruit"
    allocation = TIER_MONTHLY_GRANT.get(tier, 50)
    old_balance = int(doc.get("credit_balance") or 0)

    sub = min(old_balance, allocation) if old_balance > 0 else allocation
    topup = max(0, old_balance - allocation)

    await db.users.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "subscription_credits": sub,
                "subscription_credits_max": allocation,
                "topup_credits": topup,
                "credit_reset_date": _next_reset_iso(),
                "updated_at": _now_iso(),
            },
            "$unset": {"credit_balance": ""},
        },
    )
    # Reflect in returned doc so subsequent reads see new values.
    doc["subscription_credits"] = sub
    doc["subscription_credits_max"] = allocation
    doc["topup_credits"] = topup
    doc["credit_reset_date"] = _next_reset_iso()
    doc.pop("credit_balance", None)
    return doc


async def get_balance(db, user: dict) -> Dict[str, Any]:
    """Read the user's current dual-pool balance + tier info.
    Returns:
      {
        balance, subscription_credits, subscription_credits_max,
        topup_credits, credit_reset_date, tier, unlimited, monthly_grant,
      }
    """
    if user.get("role") == "admin":
        return {
            "balance": ADMIN_UNLIMITED,
            "subscription_credits": ADMIN_UNLIMITED,
            "subscription_credits_max": ADMIN_UNLIMITED,
            "topup_credits": ADMIN_UNLIMITED,
            "credit_reset_date": None,
            "tier": "admin",
            "unlimited": True,
            "monthly_grant": ADMIN_UNLIMITED,
        }

    doc = await db.users.find_one(_user_filter(user))
    if doc:
        doc = await _migrate_if_needed(db, user, doc)

    tier = (doc or {}).get("tier") or user.get("tier") or "recruit"
    allocation = TIER_MONTHLY_GRANT.get(tier, 50)
    sub = int((doc or {}).get("subscription_credits") or 0)
    topup = int((doc or {}).get("topup_credits") or 0)
    sub_max = int((doc or {}).get("subscription_credits_max") or allocation)
    reset_at = (doc or {}).get("credit_reset_date")

    return {
        "balance": sub + topup,
        "subscription_credits": sub,
        "subscription_credits_max": sub_max,
        "topup_credits": topup,
        "credit_reset_date": reset_at,
        "tier": tier,
        "unlimited": False,
        "monthly_grant": allocation,
    }


async def can_afford(db, user: dict, action: str) -> Dict[str, Any]:
    """Non-mutating check — does the user have enough credits for `action`?"""
    cost = ACTION_COSTS.get(action, 1)
    if user.get("role") == "admin":
        return {"allowed": True, "cost": cost, "balance": ADMIN_UNLIMITED, "unlimited": True}
    info = await get_balance(db, user)
    if info["balance"] >= cost:
        return {
            "allowed": True, "cost": cost,
            "balance": info["balance"],
            "subscription_credits": info["subscription_credits"],
            "topup_credits": info["topup_credits"],
            "unlimited": False,
        }
    return {
        "allowed": False,
        "error": "INSUFFICIENT_CREDITS",
        "message": f"Need {cost} credits, you have {info['balance']}. Top up or upgrade your plan.",
        "cost": cost,
        "balance": info["balance"],
        "subscription_credits": info["subscription_credits"],
        "topup_credits": info["topup_credits"],
        "tier": info["tier"],
        "upgrade_url": "/pricing",
        "topup_url": "/credits",
    }


async def debit(db, user: dict, action: str, ref: Optional[str] = None) -> Dict[str, Any]:
    """Dual-pool atomic debit. Consumes `subscription_credits` first, then `topup_credits`.
    Returns {balance, sub_remaining, topup_remaining, cost, unlimited}.
    Raises ValueError on insufficient funds (call `can_afford` first for a clean error)."""
    cost = ACTION_COSTS.get(action, 1)

    if user.get("role") == "admin":
        await _ledger(db, user, action, ref, sub_deducted=0, topup_deducted=0,
                      sub_remaining=ADMIN_UNLIMITED, topup_remaining=ADMIN_UNLIMITED,
                      note="admin (uncharged)", virtual=True)
        return {
            "balance": ADMIN_UNLIMITED, "cost": cost,
            "sub_remaining": ADMIN_UNLIMITED, "topup_remaining": ADMIN_UNLIMITED,
            "unlimited": True,
        }

    if cost == 0:
        # Free action — log for analytics but no balance change.
        info = await get_balance(db, user)
        await _ledger(db, user, action, ref,
                      sub_deducted=0, topup_deducted=0,
                      sub_remaining=info["subscription_credits"],
                      topup_remaining=info["topup_credits"], note=f"{action} (free)")
        return {
            "balance": info["balance"], "cost": 0,
            "sub_remaining": info["subscription_credits"],
            "topup_remaining": info["topup_credits"],
            "unlimited": False,
        }

    # Snapshot current pools to decide split.
    doc = await db.users.find_one(_user_filter(user))
    if doc:
        doc = await _migrate_if_needed(db, user, doc)
    sub = int((doc or {}).get("subscription_credits") or 0)
    topup = int((doc or {}).get("topup_credits") or 0)

    if sub + topup < cost:
        raise ValueError(f"insufficient_credits: need {cost}, have {sub + topup}")

    sub_deduct = min(sub, cost)
    topup_deduct = cost - sub_deduct

    # Atomic conditional update guards against concurrent debits.
    res = await db.users.find_one_and_update(
        {**_user_filter(user),
         "subscription_credits": {"$gte": sub_deduct},
         "topup_credits": {"$gte": topup_deduct}},
        {"$inc": {"subscription_credits": -sub_deduct, "topup_credits": -topup_deduct},
         "$set": {"updated_at": _now_iso()}},
        return_document=True,
    )
    if not res:
        # Race condition — retry once with fresh snapshot.
        return await debit(db, user, action, ref=ref)

    sub_remaining = int(res.get("subscription_credits") or 0)
    topup_remaining = int(res.get("topup_credits") or 0)
    await _ledger(db, user, action, ref,
                  sub_deducted=sub_deduct, topup_deducted=topup_deduct,
                  sub_remaining=sub_remaining, topup_remaining=topup_remaining,
                  note=f"{action}: -{sub_deduct}sub -{topup_deduct}top")
    return {
        "balance": sub_remaining + topup_remaining,
        "cost": cost,
        "sub_remaining": sub_remaining,
        "topup_remaining": topup_remaining,
        "unlimited": False,
    }


async def credit(db, user: dict, amount: int, source: str,
                 ref: Optional[str] = None, note: Optional[str] = None,
                 pool: str = "topup") -> Dict[str, Any]:
    """Add credits. `pool` is one of:
      - "topup"        : default. Goes to `topup_credits` (never expires) — promos, packs, admin grants
      - "subscription" : Goes to `subscription_credits` (resets monthly) — only used by `reset_subscription`
    """
    if amount <= 0:
        raise ValueError("amount must be > 0")
    if pool not in ("topup", "subscription"):
        raise ValueError(f"invalid pool: {pool}")

    field = "topup_credits" if pool == "topup" else "subscription_credits"
    res = await db.users.find_one_and_update(
        _user_filter(user),
        {"$inc": {field: amount}, "$set": {"updated_at": _now_iso()}},
        return_document=True, upsert=False,
    )
    if res:
        res = await _migrate_if_needed(db, user, res)
    sub_remaining = int((res or {}).get("subscription_credits") or 0)
    topup_remaining = int((res or {}).get("topup_credits") or 0)
    await _ledger(db, user, source, ref,
                  sub_deducted=0, topup_deducted=0,
                  sub_remaining=sub_remaining, topup_remaining=topup_remaining,
                  delta=amount, pool=pool, note=note or f"+{amount} via {source}")
    return {
        "balance": sub_remaining + topup_remaining,
        "added": amount,
        "pool": pool,
        "sub_remaining": sub_remaining,
        "topup_remaining": topup_remaining,
    }


async def reset_subscription(db, user: dict, tier: Optional[str] = None,
                             days_until_next: int = 30,
                             ref: Optional[str] = None) -> Dict[str, Any]:
    """Reset the user's `subscription_credits` to their tier's monthly allocation.
    Top-up credits are UNTOUCHED. Called from the Stripe `invoice.paid` webhook
    and from tier-change handlers."""
    doc = await db.users.find_one(_user_filter(user))
    effective_tier = tier or (doc or {}).get("tier") or user.get("tier") or "recruit"
    allocation = TIER_MONTHLY_GRANT.get(effective_tier, 50)
    reset_at = _next_reset_iso(days_until_next)

    res = await db.users.find_one_and_update(
        _user_filter(user),
        {"$set": {
            "subscription_credits": allocation,
            "subscription_credits_max": allocation,
            "credit_reset_date": reset_at,
            "tier": effective_tier,
            "updated_at": _now_iso(),
        }},
        return_document=True,
    )
    topup_remaining = int((res or {}).get("topup_credits") or 0)
    await _ledger(db, user, "subscription_reset", ref,
                  sub_deducted=0, topup_deducted=0,
                  sub_remaining=allocation, topup_remaining=topup_remaining,
                  delta=allocation, pool="subscription",
                  note=f"Monthly reset: {effective_tier} → {allocation}cr")
    return {
        "tier": effective_tier,
        "subscription_credits": allocation,
        "subscription_credits_max": allocation,
        "topup_credits": topup_remaining,
        "credit_reset_date": reset_at,
    }


async def list_transactions(db, user: dict, limit: int = 50):
    user_id = str(user.get("id", user.get("email")))
    cursor = db.credit_transactions.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)


async def _ledger(db, user: dict, kind: str, ref: Optional[str], *,
                  sub_deducted: int = 0, topup_deducted: int = 0,
                  sub_remaining: int = 0, topup_remaining: int = 0,
                  delta: Optional[int] = None, pool: Optional[str] = None,
                  note: str = "", virtual: bool = False):
    user_id = str(user.get("id", user.get("email")))
    # Compute delta from deductions if not explicitly given (debit case).
    if delta is None:
        delta = -(sub_deducted + topup_deducted)
    await db.credit_transactions.insert_one({
        "user_id": user_id,
        "email": user.get("email"),
        "delta": int(delta),
        "kind": kind,                              # action name, "topup", "promo", "subscription_reset"
        "ref": ref,                                # listing id / stripe session id / promo code, etc.
        "pool": pool,                              # "subscription" | "topup" | None (for debit)
        "sub_deducted": int(sub_deducted),
        "topup_deducted": int(topup_deducted),
        "sub_remaining": int(sub_remaining),
        "topup_remaining": int(topup_remaining),
        "balance_after": int(sub_remaining + topup_remaining),
        "note": note,
        "virtual": virtual,
        "created_at": _now_iso(),
    })
