"""
Hosting Subscription Tiers — Prompt 7 Part 3

Creators pay a monthly hosting fee so their published agents in The Exchange
can be executed by buyers on our infrastructure. This is SEPARATE from the
end-user subscription tiers (recruit/cadet/operator/...) which govern credit
allocations.

Tiers are one-month one-shot Stripe checkouts (same pattern as
routes/subscriptions.py) — periodic auto-renewal is intentionally deferred
in favour of a manual top-up UX for the v1 of this feature.

Collection schema (`hosting_subscriptions`):
    id, creator_id, creator_email, tier, status (active|cancelled|superseded|expired),
    stripe_session_id, payment_id, amount,
    current_period_start, current_period_end,
    executions_used, agents_used, agents_published[],
    created_at, updated_at, cancelled_at

Endpoints (all under /api/hosting):
    GET  /tiers          — public catalogue + limits
    GET  /me             — current creator subscription (null if none)
    GET  /usage          — runtime counters + caps + percentage utilisation
    POST /checkout       — Stripe one-time checkout for the chosen tier
    POST /activate       — manual activation after payment success page polls
    POST /cancel         — cancel; tier downgrades to None at period_end
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv()

router = APIRouter()
STRIPE_KEY = os.environ.get("STRIPE_API_KEY")
PERIOD_DAYS = 30  # one month, hard-coded; matches Stripe's 30-day period_end convention


# ── Tier catalogue (server-side ONLY — never trust frontend) ───────────────
HOSTING_TIERS = {
    "starter": {
        "tier": "starter",
        "price": 9.00,
        "label": "Hosting · Starter",
        "tagline": "Launch your first agent.",
        "max_agents": 1,
        "max_executions": 1_000,
        "max_runtime_seconds": 10,
        "features": [
            "1 published agent",
            "1,000 executions / month",
            "10-second max runtime",
            "Basic analytics dashboard",
        ],
        "highlight": False,
    },
    "pro": {
        "tier": "pro",
        "price": 29.00,
        "label": "Hosting · Pro",
        "tagline": "Most popular for indie creators.",
        "max_agents": 3,
        "max_executions": 10_000,
        "max_runtime_seconds": 30,
        "features": [
            "3 published agents",
            "10,000 executions / month",
            "30-second max runtime",
            "Priority execution queue",
            "Custom display URL slug",
        ],
        "highlight": True,
    },
    "growth": {
        "tier": "growth",
        "price": 99.00,
        "label": "Hosting · Growth",
        "tagline": "Scale your agent portfolio.",
        "max_agents": 10,
        "max_executions": 50_000,
        "max_runtime_seconds": 60,
        "features": [
            "10 published agents",
            "50,000 executions / month",
            "60-second max runtime",
            "Priority execution queue",
            "99.5% uptime SLA",
            "Email support",
        ],
        "highlight": False,
    },
    "scale": {
        "tier": "scale",
        "price": 299.00,
        "label": "Hosting · Scale",
        "tagline": "Production-grade hosting.",
        "max_agents": 0,  # 0 = unlimited
        "max_executions": 250_000,
        "max_runtime_seconds": 60,
        "features": [
            "Unlimited published agents",
            "250,000 executions / month",
            "60-second max runtime",
            "Dedicated execution queue",
            "99.9% uptime SLA",
            "Priority support (4h response)",
            "White-glove deployment assistance",
        ],
        "highlight": False,
    },
}


# ── DI shims ───────────────────────────────────────────────────────────────
def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _period_end(start: datetime | None = None) -> str:
    base = start or datetime.now(timezone.utc)
    return (base + timedelta(days=PERIOD_DAYS)).isoformat()


# ── Schemas ────────────────────────────────────────────────────────────────
class CheckoutRequest(BaseModel):
    tier: str = Field(pattern="^(starter|pro|growth|scale)$")
    origin_url: str


class ActivateRequest(BaseModel):
    session_id: str


def _project(sub: dict) -> dict:
    """Strip Mongo internal `_id` + add denormalised tier metadata for the UI."""
    if not sub:
        return None
    tier = HOSTING_TIERS.get(sub.get("tier")) or {}
    out = {k: v for k, v in sub.items() if k != "_id"}
    out["tier_meta"] = {
        "label": tier.get("label"),
        "price": tier.get("price"),
        "max_agents": tier.get("max_agents"),
        "max_executions": tier.get("max_executions"),
        "max_runtime_seconds": tier.get("max_runtime_seconds"),
        "features": tier.get("features"),
    }
    return out


# ── Routes ─────────────────────────────────────────────────────────────────
@router.get("/hosting/tiers")
async def list_tiers():
    """Public — the creator-facing tier catalogue."""
    return {"tiers": list(HOSTING_TIERS.values()), "period_days": PERIOD_DAYS}


@router.get("/hosting/me")
async def get_my_hosting(user=Depends(get_current_user())):
    """Return the user's CURRENT active hosting subscription (or null)."""
    db = get_db()
    creator_id = str(user.get("id", user.get("email")))
    sub = await db.hosting_subscriptions.find_one(
        {"creator_id": creator_id, "status": "active"},
        sort=[("created_at", -1)],
    )
    return {"subscription": _project(sub)}


@router.get("/hosting/usage")
async def get_usage(user=Depends(get_current_user())):
    """Current period counters vs caps. Returns the latest active sub OR a
    null-tier shape so the dashboard can render an upgrade CTA."""
    db = get_db()
    creator_id = str(user.get("id", user.get("email")))
    sub = await db.hosting_subscriptions.find_one(
        {"creator_id": creator_id, "status": "active"},
        sort=[("created_at", -1)],
    )
    if not sub:
        return {
            "has_subscription": False,
            "tier": None,
            "max_agents": 0,
            "max_executions": 0,
            "agents_used": 0,
            "executions_used": 0,
            "pct_agents": 0,
            "pct_executions": 0,
            "period_end": None,
        }
    tier = HOSTING_TIERS.get(sub["tier"]) or {}
    max_agents = tier.get("max_agents") or 0
    max_exec = tier.get("max_executions") or 0
    agents_used = int(sub.get("agents_used") or 0)
    exec_used = int(sub.get("executions_used") or 0)
    return {
        "has_subscription": True,
        "tier": sub["tier"],
        "tier_label": tier.get("label"),
        "max_agents": max_agents,
        "max_executions": max_exec,
        "agents_used": agents_used,
        "executions_used": exec_used,
        "pct_agents": (agents_used / max_agents * 100) if max_agents > 0 else 0,
        "pct_executions": (exec_used / max_exec * 100) if max_exec > 0 else 0,
        "period_start": sub.get("current_period_start"),
        "period_end": sub.get("current_period_end"),
        "status": sub.get("status"),
    }


@router.post("/hosting/checkout")
async def create_checkout(req: CheckoutRequest, request: Request,
                          user=Depends(get_current_user())):
    """Create a Stripe one-time checkout for the chosen hosting tier. The
    webhook (routes/stripe_payments.py) flips status to 'paid' and POST
    /hosting/activate then provisions the hosting_subscriptions row."""
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
    tier_info = HOSTING_TIERS.get(req.tier)
    if not tier_info:
        raise HTTPException(status_code=400, detail="Unknown tier.")
    db = get_db()
    creator_id = str(user.get("id", user.get("email")))

    # Block if an active subscription already exists at this exact tier.
    existing = await db.hosting_subscriptions.find_one(
        {"creator_id": creator_id, "status": "active", "tier": req.tier},
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"You already have an active {tier_info['label']} subscription.",
        )

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_KEY, webhook_url=webhook_url)
    checkout_req = CheckoutSessionRequest(
        amount=float(tier_info["price"]),
        currency="usd",
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&type=hosting",
        cancel_url=f"{req.origin_url}/hosting",
        metadata={
            "type": "hosting",
            "tier": req.tier,
            "user_id": creator_id,
            "user_email": user.get("email") or "",
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    tx_id = str(uuid.uuid4())
    await db.payment_transactions.insert_one({
        "id": tx_id,
        "session_id": session.session_id,
        "user_id": creator_id,
        "user_email": user.get("email"),
        "type": "hosting",
        "tier": req.tier,
        "amount": float(tier_info["price"]),
        "currency": "usd",
        "payment_status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
    })
    return {"url": session.url, "session_id": session.session_id, "tier": req.tier,
            "amount": float(tier_info["price"])}


@router.post("/hosting/activate")
async def activate_subscription(body: ActivateRequest, user=Depends(get_current_user())):
    """Idempotently provision the hosting_subscriptions row once the linked
    payment_transactions row is marked paid (by the webhook). Frontend may call
    this from /payment/success?type=hosting to confirm activation."""
    db = get_db()
    creator_id = str(user.get("id", user.get("email")))
    tx = await db.payment_transactions.find_one(
        {"session_id": body.session_id, "type": "hosting"},
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Hosting checkout not found.")
    if tx.get("user_id") != creator_id:
        raise HTTPException(status_code=403, detail="This checkout belongs to a different account.")
    if tx.get("payment_status") != "paid":
        raise HTTPException(status_code=402,
                            detail=f"Payment not confirmed yet (status={tx.get('payment_status')}).")
    if tx.get("activated"):
        # Already activated — return the matching sub.
        sub = await db.hosting_subscriptions.find_one(
            {"creator_id": creator_id, "stripe_session_id": body.session_id},
        )
        return {"already_active": True, "subscription": _project(sub)}

    tier = tx["tier"]
    tier_info = HOSTING_TIERS.get(tier) or {}
    now_dt = datetime.now(timezone.utc)
    # Supersede any prior active hosting subscription (you can't have two).
    await db.hosting_subscriptions.update_many(
        {"creator_id": creator_id, "status": "active"},
        {"$set": {"status": "superseded", "updated_at": _now()}},
    )
    sub_doc = {
        "id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "creator_email": user.get("email"),
        "tier": tier,
        "status": "active",
        "stripe_session_id": body.session_id,
        "payment_id": tx["id"],
        "amount": tx["amount"],
        "current_period_start": now_dt.isoformat(),
        "current_period_end": _period_end(now_dt),
        "executions_used": 0,
        "agents_used": 0,
        "agents_published": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.hosting_subscriptions.insert_one(sub_doc)
    await db.payment_transactions.update_one(
        {"session_id": body.session_id},
        {"$set": {"activated": True, "updated_at": _now()}},
    )
    return {"already_active": False, "subscription": _project(sub_doc),
            "tier_label": tier_info.get("label")}


@router.post("/hosting/cancel")
async def cancel_subscription(user=Depends(get_current_user())):
    """Cancel the active hosting subscription. Stays active until period_end,
    then is flagged 'expired' by the next usage poll OR a scheduled job."""
    db = get_db()
    creator_id = str(user.get("id", user.get("email")))
    sub = await db.hosting_subscriptions.find_one(
        {"creator_id": creator_id, "status": "active"},
        sort=[("created_at", -1)],
    )
    if not sub:
        raise HTTPException(status_code=404, detail="No active hosting subscription.")
    await db.hosting_subscriptions.update_one(
        {"id": sub["id"]},
        {"$set": {"status": "cancelled", "cancelled_at": _now(), "updated_at": _now()}},
    )
    fresh = await db.hosting_subscriptions.find_one({"id": sub["id"]})
    return {"success": True, "subscription": _project(fresh),
            "message": f"Cancelled. You'll lose publishing privileges on {sub.get('current_period_end','')[:10]}."}


# ── Internal helpers exported for other routes ─────────────────────────────
async def get_active_subscription(db, creator_id: str) -> Optional[dict]:
    """Used by exchange.publish + external_agent_run to enforce caps."""
    return await db.hosting_subscriptions.find_one(
        {"creator_id": str(creator_id), "status": "active"},
        sort=[("created_at", -1)],
    )


async def can_publish(db, creator_id: str) -> dict:
    """Returns {allowed, reason, tier, agents_used, max_agents}. max_agents=0 ⇒ unlimited."""
    sub = await get_active_subscription(db, creator_id)
    if not sub:
        return {"allowed": False, "reason": "no_subscription",
                "message": "Pick a hosting plan to publish agents.", "tier": None}
    tier_info = HOSTING_TIERS.get(sub["tier"]) or {}
    max_agents = tier_info.get("max_agents") or 0
    agents_used = int(sub.get("agents_used") or 0)
    if max_agents == 0:  # unlimited
        return {"allowed": True, "tier": sub["tier"], "agents_used": agents_used,
                "max_agents": 0}
    if agents_used >= max_agents:
        return {"allowed": False, "reason": "agent_cap",
                "message": f"You've published {agents_used}/{max_agents} agents on {tier_info.get('label')}. Upgrade to publish more.",
                "tier": sub["tier"], "agents_used": agents_used, "max_agents": max_agents}
    return {"allowed": True, "tier": sub["tier"], "agents_used": agents_used,
            "max_agents": max_agents}


async def increment_executions(db, creator_id: str, by: int = 1) -> Optional[dict]:
    """Atomic $inc on the creator's active subscription's executions_used.
    Returns the post-update doc, or None if no active sub."""
    return await db.hosting_subscriptions.find_one_and_update(
        {"creator_id": str(creator_id), "status": "active"},
        {"$inc": {"executions_used": int(by)}, "$set": {"updated_at": _now()}},
        sort=[("created_at", -1)],
        return_document=True,
    )


async def increment_agents(db, creator_id: str, listing_id: str, by: int = 1) -> Optional[dict]:
    """Atomic $inc on agents_used + append listing_id to agents_published."""
    return await db.hosting_subscriptions.find_one_and_update(
        {"creator_id": str(creator_id), "status": "active"},
        {"$inc": {"agents_used": int(by)},
         "$addToSet": {"agents_published": listing_id},
         "$set": {"updated_at": _now()}},
        sort=[("created_at", -1)],
        return_document=True,
    )


async def decrement_agents(db, creator_id: str, listing_id: str) -> Optional[dict]:
    """Reverse of increment_agents — clamps to 0 and pulls listing_id from the set.
    Idempotent: removing an already-removed listing leaves the row untouched."""
    sub = await db.hosting_subscriptions.find_one(
        {"creator_id": str(creator_id), "status": "active"},
        sort=[("created_at", -1)],
    )
    if not sub:
        return None
    if listing_id not in (sub.get("agents_published") or []):
        return sub  # nothing to decrement
    new_count = max(0, int(sub.get("agents_used") or 0) - 1)
    return await db.hosting_subscriptions.find_one_and_update(
        {"id": sub["id"]},
        {"$set": {"agents_used": new_count, "updated_at": _now()},
         "$pull": {"agents_published": listing_id}},
        return_document=True,
    )


async def expire_lapsed_subscriptions(db) -> int:
    """Scheduled job — flip status='cancelled' rows whose current_period_end is in
    the past to status='expired'. Also flips 'active' rows past their period_end
    (defensive: should only happen if the row hasn't been renewed yet).

    Returns the total number of rows flipped."""
    now_iso = _now()
    res1 = await db.hosting_subscriptions.update_many(
        {"status": "cancelled", "current_period_end": {"$lt": now_iso}},
        {"$set": {"status": "expired", "expired_at": now_iso, "updated_at": now_iso}},
    )
    res2 = await db.hosting_subscriptions.update_many(
        {"status": "active", "current_period_end": {"$lt": now_iso}},
        {"$set": {"status": "expired", "expired_at": now_iso, "updated_at": now_iso}},
    )
    return (res1.modified_count or 0) + (res2.modified_count or 0)


__all__ = [
    "router", "HOSTING_TIERS", "PERIOD_DAYS",
    "get_active_subscription", "can_publish",
    "increment_executions", "increment_agents", "decrement_agents",
    "expire_lapsed_subscriptions",
]
