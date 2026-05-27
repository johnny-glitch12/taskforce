"""
Stripe Subscription Management — Handles Cadet ($19/mo) and Operator ($99/mo) tiers.
Uses emergent Stripe test key via one-time checkout sessions that upgrade user tiers.
Also handles referral credit system.
"""
import os
import uuid
import string
import random
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from dotenv import load_dotenv
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

load_dotenv()

router = APIRouter()

STRIPE_KEY = os.environ.get("STRIPE_API_KEY")

# ── Subscription Tiers (server-side pricing — NEVER from frontend) ──
TIERS = {
    "cadet": {"price": 19.00, "label": "Cadet", "agent_limit": 10, "executions": 500},
    "operator": {"price": 99.00, "label": "Operator", "agent_limit": 50, "executions": 2000},
}


def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


def get_db():
    from server import db
    return db


# ── Schemas ──
class SubscribeRequest(BaseModel):
    tier: str
    origin_url: str


class ApplyReferralRequest(BaseModel):
    code: str


# ──────────────────────────────────────────────
# SUBSCRIPTIONS
# ──────────────────────────────────────────────

@router.post("/subscriptions/checkout")
async def create_subscription_checkout(req: SubscribeRequest, request: Request, user=Depends(get_current_user())):
    """Create a Stripe checkout session for a subscription tier."""
    if req.tier not in TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Choose from: {list(TIERS.keys())}")

    tier = TIERS[req.tier]
    db = get_db()

    # Check if user already has an active subscription at this tier or higher
    existing = await db.subscriptions.find_one({
        "user_id": user["id"],
        "status": "active",
    })
    if existing and existing.get("tier") == req.tier:
        raise HTTPException(status_code=400, detail=f"You already have an active {tier['label']} subscription.")

    # Check for referral credit
    credit = await db.referral_credits.find_one({
        "user_id": user["id"],
        "used": False,
    })
    discount = float(credit["amount"]) if credit else 0.0
    final_price = max(1.00, tier["price"] - discount)

    success_url = f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&type=subscription"
    cancel_url = f"{req.origin_url}/pricing"

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_KEY, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=final_price,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "subscription",
            "tier": req.tier,
            "user_id": user["id"],
            "user_email": user["email"],
            "discount_applied": str(discount),
            "credit_id": str(credit["id"]) if credit else "",
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Record pending transaction
    now = datetime.now(timezone.utc).isoformat()
    tx_id = str(uuid.uuid4())
    await db.payment_transactions.insert_one({
        "id": tx_id,
        "session_id": session.session_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "type": "subscription",
        "tier": req.tier,
        "amount": final_price,
        "discount": discount,
        "currency": "usd",
        "payment_status": "pending",
        "created_at": now,
        "updated_at": now,
    })

    return {"url": session.url, "session_id": session.session_id}


@router.get("/subscriptions/status")
async def get_subscription_status(user=Depends(get_current_user())):
    """Get user's current subscription tier and status."""
    db = get_db()
    sub = await db.subscriptions.find_one(
        {"user_id": user["id"], "status": "active"},
        {"_id": 0},
    )

    from lib.compute_credits import get_compute_status
    compute = await get_compute_status(db, user)

    if not sub:
        return {
            "tier": "recruit",
            "status": "free",
            "label": "Recruit",
            "agent_limit": 3,
            "executions_limit": 100,
            "compute": compute,
        }

    tier_info = TIERS.get(sub["tier"], {})
    return {
        "tier": sub["tier"],
        "status": sub["status"],
        "label": tier_info.get("label", sub["tier"].title()),
        "agent_limit": tier_info.get("agent_limit", 3),
        "executions_limit": tier_info.get("executions", 100),
        "subscribed_at": sub.get("created_at"),
        "payment_id": sub.get("payment_id"),
        "compute": compute,
    }


@router.post("/subscriptions/cancel")
async def cancel_subscription(user=Depends(get_current_user())):
    """Cancel active subscription (downgrades to Recruit at period end)."""
    db = get_db()
    sub = await db.subscriptions.find_one({"user_id": user["id"], "status": "active"})
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found.")

    now = datetime.now(timezone.utc).isoformat()
    await db.subscriptions.update_one(
        {"_id": sub["_id"]},
        {"$set": {"status": "cancelled", "cancelled_at": now, "updated_at": now}},
    )

    # Downgrade user tier
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"tier": "free", "agent_limit": 3}},
    )

    return {"success": True, "message": "Subscription cancelled immediately. Downgraded to Recruit."}


@router.post("/subscriptions/activate")
async def activate_subscription_from_payment(session_id: str, user=Depends(get_current_user())):
    """Called after successful payment to activate subscription."""
    db = get_db()

    # Find the payment transaction
    tx = await db.payment_transactions.find_one({"session_id": session_id, "type": "subscription"})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if tx.get("payment_status") != "paid":
        raise HTTPException(status_code=400, detail="Payment not confirmed yet.")
    if tx.get("activated"):
        return {"success": True, "message": "Already activated.", "tier": tx["tier"]}

    tier = tx["tier"]
    tier_info = TIERS.get(tier, {})
    now = datetime.now(timezone.utc).isoformat()

    # Deactivate any existing subscription
    await db.subscriptions.update_many(
        {"user_id": tx["user_id"], "status": "active"},
        {"$set": {"status": "superseded", "updated_at": now}},
    )

    # Create new subscription record
    await db.subscriptions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": tx["user_id"],
        "tier": tier,
        "status": "active",
        "payment_id": tx["id"],
        "session_id": session_id,
        "amount": tx["amount"],
        "created_at": now,
        "updated_at": now,
    })

    # Upgrade user tier
    await db.users.update_one(
        {"id": tx["user_id"]},
        {"$set": {
            "tier": tier,
            "agent_limit": tier_info.get("agent_limit", 3),
        }},
    )

    # Mark transaction as activated (prevent double activation)
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"activated": True, "updated_at": now}},
    )

    # Mark referral credit as used if applicable
    credit_id = tx.get("metadata", {}).get("credit_id") or ""
    if not credit_id and isinstance(tx.get("discount"), (int, float)) and tx["discount"] > 0:
        credit = await db.referral_credits.find_one({"user_id": tx["user_id"], "used": False})
        if credit:
            await db.referral_credits.update_one({"_id": credit["_id"]}, {"$set": {"used": True, "used_at": now}})

    return {"success": True, "tier": tier, "label": tier_info.get("label", tier.title())}


# ──────────────────────────────────────────────
# REFERRAL SYSTEM
# ──────────────────────────────────────────────

def generate_referral_code():
    """Generate a unique 8-char referral code."""
    chars = string.ascii_uppercase + string.digits
    return "TF-" + "".join(random.choices(chars, k=6))


@router.get("/referrals/my-code")
async def get_my_referral_code(user=Depends(get_current_user())):
    """Get or generate the user's referral code."""
    db = get_db()
    existing = await db.referral_codes.find_one({"user_id": user["id"]}, {"_id": 0})
    if existing:
        # Count successful referrals
        referral_count = await db.referrals.count_documents({"referrer_id": user["id"], "status": "completed"})
        total_earned = referral_count * 10.0
        return {**existing, "referral_count": referral_count, "total_earned": total_earned}

    code = generate_referral_code()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "code": code,
        "created_at": now,
    }
    await db.referral_codes.insert_one(doc)
    del doc["_id"]
    return {**doc, "referral_count": 0, "total_earned": 0.0}


@router.post("/referrals/apply")
async def apply_referral_code(req: ApplyReferralRequest, user=Depends(get_current_user())):
    """Apply a referral code during or after signup. Credits both parties."""
    db = get_db()
    code = req.code.strip().upper()

    # Find the referral code
    ref_code = await db.referral_codes.find_one({"code": code})
    if not ref_code:
        raise HTTPException(status_code=404, detail="Invalid referral code.")

    # Can't refer yourself
    if ref_code["user_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="You can't use your own referral code.")

    # Check if already referred
    existing = await db.referrals.find_one({"referred_id": user["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="You've already used a referral code.")

    now = datetime.now(timezone.utc).isoformat()

    # Create referral record
    await db.referrals.insert_one({
        "id": str(uuid.uuid4()),
        "referrer_id": ref_code["user_id"],
        "referred_id": user["id"],
        "code": code,
        "status": "completed",
        "created_at": now,
    })

    # Credit the referred user: $10 off next subscription
    await db.referral_credits.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "amount": 10.0,
        "reason": f"Referred by {code}",
        "used": False,
        "created_at": now,
    })

    # Credit the referrer: $10 off next subscription
    await db.referral_credits.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": ref_code["user_id"],
        "amount": 10.0,
        "reason": f"Referred user {user['email']}",
        "used": False,
        "created_at": now,
    })

    return {
        "success": True,
        "message": "Referral applied! You both get $10 off your next subscription.",
        "your_credit": 10.0,
        "referrer_credit": 10.0,
    }


@router.get("/referrals/credits")
async def get_my_credits(user=Depends(get_current_user())):
    """Get user's available referral credits."""
    db = get_db()
    credits = await db.referral_credits.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).to_list(100)
    available = sum(c["amount"] for c in credits if not c.get("used"))
    total = sum(c["amount"] for c in credits)
    return {
        "available_credit": available,
        "total_earned": total,
        "credits": credits,
    }
