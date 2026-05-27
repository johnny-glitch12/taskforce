"""
Stripe Payments Routes — Task Force AI

Extracted from server.py. One-shot agent rent/buy checkouts (NOT subscriptions —
those live in routes/subscriptions.py). Uses emergentintegrations Stripe wrapper.
Webhook handles both one-shot and subscription confirmation events.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user():
    from server import get_current_user as _u
    return _u


def _srv():
    import server as srv
    return srv


def _stripe(host_url: str):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    return StripeCheckout(
        api_key=os.environ.get("STRIPE_API_KEY"),
        webhook_url=f"{host_url}/api/webhook/stripe",
    )


@router.post("/payments/checkout")
async def create_checkout(request: Request, data: dict, user=Depends(get_current_user())):
    from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest
    srv = _srv()
    db = srv.db

    agent_id = data.get("agent_id")
    plan = data.get("plan", "rent")
    origin_url = data.get("origin_url", "")
    if not origin_url:
        raise HTTPException(status_code=400, detail="origin_url is required")

    agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    amount = float(agent["price"]) if plan == "rent" else float(agent["buyPrice"])
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid price")

    host_url = str(request.base_url).rstrip("/")
    stripe_checkout = _stripe(host_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=f"{origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin_url}/agent/{agent_id}",
        metadata={
            "agent_id": str(agent_id),
            "agent_name": agent["shortTitle"],
            "plan": plan,
            "user_id": user["id"],
            "user_email": user["email"],
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    tx_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "id": tx_id,
        "session_id": session.session_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "agent_id": agent_id,
        "agent_name": agent["shortTitle"],
        "plan": plan,
        "amount": amount,
        "currency": "usd",
        "payment_status": "pending",
        "created_at": now,
        "updated_at": now,
    })
    return {"url": session.url, "session_id": session.session_id}


@router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, request: Request):
    srv = _srv()
    db = srv.db

    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    host_url = str(request.base_url).rstrip("/")
    stripe_checkout = _stripe(host_url)
    status = await stripe_checkout.get_checkout_status(session_id)

    if status.payment_status != tx.get("payment_status"):
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": status.payment_status,
                "status": status.status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    return {
        "session_id": session_id,
        "status": status.status,
        "payment_status": status.payment_status,
        "amount": status.amount_total,
        "currency": status.currency,
        "agent_id": tx.get("agent_id"),
        "agent_name": tx.get("agent_name"),
        "plan": tx.get("plan"),
    }


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    srv = _srv()
    db = srv.db

    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    host_url = str(request.base_url).rstrip("/")
    stripe_checkout = _stripe(host_url)

    try:
        event = await stripe_checkout.handle_webhook(body, sig)
        if event.payment_status == "paid" and event.session_id:
            tx = await db.payment_transactions.find_one({"session_id": event.session_id})
            if tx and tx.get("payment_status") != "paid":
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "status": "complete",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                logger.info(f"Payment confirmed for session {event.session_id}")

                # Auto-activate subscription if this is a subscription payment
                if tx.get("type") == "subscription" and not tx.get("activated"):
                    from routes.subscriptions import TIERS
                    tier = tx.get("tier")
                    tier_info = TIERS.get(tier, {})
                    now = datetime.now(timezone.utc).isoformat()
                    await db.subscriptions.update_many(
                        {"user_id": tx["user_id"], "status": "active"},
                        {"$set": {"status": "superseded", "updated_at": now}},
                    )
                    await db.subscriptions.insert_one({
                        "id": str(uuid.uuid4()),
                        "user_id": tx["user_id"],
                        "tier": tier,
                        "status": "active",
                        "payment_id": tx["id"],
                        "session_id": event.session_id,
                        "amount": tx["amount"],
                        "created_at": now,
                        "updated_at": now,
                    })
                    await db.users.update_one(
                        {"id": tx["user_id"]},
                        {"$set": {"tier": tier, "agent_limit": tier_info.get("agent_limit", 3)}},
                    )
                    await db.payment_transactions.update_one(
                        {"session_id": event.session_id},
                        {"$set": {"activated": True}},
                    )
                    logger.info(f"Subscription activated: {tier} for user {tx['user_id']}")

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}
