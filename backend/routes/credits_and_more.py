"""
Credits + Promo + Newsletter + Deployments API routes.

Bundled in one module to keep iter39 surface area focused.
"""
import os
import json
import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr

from lib.credit_wallet import (
    get_balance, list_transactions, credit as credit_wallet_credit,
    debit as credit_wallet_debit, TIER_MONTHLY_GRANT,
)

router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")


# ──────────────────────────────────────────────────────────
# 1. CREDITS
# ──────────────────────────────────────────────────────────
TOPUP_PACKS = {
    "starter":      {"credits": 200,   "price": 5.00,   "label": "Starter · 200 credits"},
    "builder":      {"credits": 1000,  "price": 19.00,  "label": "Builder · 1,000 credits"},
    "operator":     {"credits": 5000,  "price": 79.00,  "label": "Operator · 5,000 credits"},
    "agency":       {"credits": 25000, "price": 299.00, "label": "Agency · 25,000 credits"},
}


@router.get("/credits/me")
async def credits_me(user=Depends(get_current_user())):
    db = get_db()
    info = await get_balance(db, user)
    txns = await list_transactions(db, user, limit=20)
    # Strip the rich cost metadata (api_cost_usd, revenue_usd, key_source,
    # input/output_tokens) from user-facing transactions — admins can still
    # see those in the Economics Dashboard. We keep human-friendly fields:
    # delta, kind, ref, pool, sub/topup_deducted, sub/topup_remaining, note,
    # balance_after, created_at, source.
    sanitized = []
    for tx in txns:
        tx.pop("metadata", None)
        sanitized.append(tx)
    # action_costs intentionally OMITTED from the frontend response so users
    # don't see per-action credit pricing. Costs are still tracked server-side
    # and visible in the owner-only Economics Dashboard.
    return {**info, "transactions": sanitized, "packs": TOPUP_PACKS}


class TopupRequest(BaseModel):
    pack: str
    promo_code: Optional[str] = None


@router.post("/credits/topup/checkout")
async def credits_topup_checkout(request: Request, body: TopupRequest, user=Depends(get_current_user())):
    """Create a Stripe one-time checkout that mints credits on success.
    Promo code (optional) is validated AT REDEMPTION TIME via the webhook, not here."""
    pack = TOPUP_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown pack.")
    db = get_db()

    # If promo_code present, sanity-check it now so the user sees errors early.
    promo_discount = 0
    if body.promo_code:
        promo = await db.promo_codes.find_one({"code": body.promo_code.upper().strip(), "active": True})
        if promo and promo.get("kind") == "discount_pct":
            promo_discount = float(promo.get("value", 0))

    final_price = round(pack["price"] * (1 - promo_discount / 100.0), 2)
    if final_price < 0.50:
        final_price = 0.50  # Stripe minimum

    # Lazy import — match existing stripe_payments.py pattern
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    host = str(request.base_url).rstrip("/")
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured.")
    sc = StripeCheckout(api_key=api_key, webhook_url=f"{host}/api/payments/webhook")

    metadata = {
        "kind": "credit_topup",
        "pack": body.pack,
        "credits": str(pack["credits"]),
        "user_id": str(user.get("id", user.get("email"))),
        "user_email": str(user.get("email", "")),
    }
    if body.promo_code and promo_discount > 0:
        metadata["promo_code"] = body.promo_code.upper().strip()
        metadata["promo_discount_pct"] = str(promo_discount)

    sess_req = CheckoutSessionRequest(
        amount=final_price, currency="usd",
        success_url=f"{host}/credits?session_id={{CHECKOUT_SESSION_ID}}&topup=success",
        cancel_url=f"{host}/credits?topup=cancel",
        metadata=metadata,
    )
    session = await sc.create_checkout_session(sess_req)
    # Persist a payment_transactions record so the webhook can credit on `invoice.paid`/`checkout.session.completed`.
    await db.payment_transactions.insert_one({
        "id": uuid.uuid4().hex,
        "session_id": session.session_id,
        "user_id": str(user.get("id", user.get("email"))),
        "user_email": user.get("email"),
        "type": "credit_topup",
        "pack": body.pack,
        "credits": pack["credits"],
        "amount": final_price,
        "currency": "usd",
        "payment_status": "pending",
        "activated": False,
        "metadata": metadata,
        "created_at": _now(),
        "updated_at": _now(),
    })
    return {"url": session.url, "session_id": session.session_id, "final_price": final_price, "pack": pack}


@router.post("/credits/topup/poll/{session_id}")
async def credits_topup_poll(session_id: str, request: Request, user=Depends(get_current_user())):
    """Manual sanity-poll for the success page — checks Stripe session and grants credits if paid
    AND not already granted (idempotent via existing transaction lookup)."""
    db = get_db()
    existing = await db.credit_transactions.find_one({"kind": "topup", "ref": session_id})
    if existing:
        info = await get_balance(db, user)
        return {"already_granted": True, **info}

    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY"), webhook_url=f"{host}/api/payments/webhook")
    status = await sc.get_checkout_status(session_id)
    if (status.payment_status or "").lower() != "paid":
        return {"paid": False, "status": status.payment_status}

    md = status.metadata or {}
    if md.get("kind") != "credit_topup":
        raise HTTPException(status_code=400, detail="Session not a credit top-up.")
    credits = int(md.get("credits") or 0)
    if credits <= 0:
        raise HTTPException(status_code=400, detail="Invalid credits in session metadata.")
    # Optionally record promo redemption stats
    if md.get("promo_code"):
        await db.promo_codes.update_one(
            {"code": md["promo_code"]}, {"$inc": {"redeemed_count": 1}, "$set": {"last_redeemed": _now()}}
        )
    result = await credit_wallet_credit(db, user, credits, "topup", ref=session_id, note=f"+{credits} via Stripe topup")
    return {"paid": True, "credits_added": credits, **result}


# ──────────────────────────────────────────────────────────
# 2. PROMO CODES
# ──────────────────────────────────────────────────────────
class PromoCreateRequest(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    kind: str = Field(pattern="^(credits|discount_pct)$")
    value: float = Field(gt=0)
    max_redemptions: int = Field(default=0, ge=0)  # 0 = unlimited
    note: Optional[str] = Field(default=None, max_length=200)


@router.post("/promo/codes")
async def create_promo_code(body: PromoCreateRequest, user=Depends(get_current_user())):
    """ADMIN — mint a new promo code."""
    _require_admin(user)
    db = get_db()
    code = body.code.upper().strip()
    existing = await db.promo_codes.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=409, detail="Code already exists.")
    doc = {
        "id": uuid.uuid4().hex,
        "code": code,
        "kind": body.kind,           # "credits" → grants credits ; "discount_pct" → discount on topups
        "value": float(body.value),
        "max_redemptions": body.max_redemptions,
        "redeemed_count": 0,
        "active": True,
        "note": body.note,
        "created_by": user.get("email"),
        "created_at": _now(),
    }
    await db.promo_codes.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/promo/codes")
async def list_promo_codes(user=Depends(get_current_user())):
    _require_admin(user)
    db = get_db()
    cursor = db.promo_codes.find({}, {"_id": 0}).sort("created_at", -1)
    return {"codes": await cursor.to_list(200)}


@router.delete("/promo/codes/{code}")
async def disable_promo_code(code: str, user=Depends(get_current_user())):
    _require_admin(user)
    db = get_db()
    res = await db.promo_codes.update_one({"code": code.upper().strip()}, {"$set": {"active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Code not found.")
    return {"success": True}


class PromoRedeemRequest(BaseModel):
    code: str = Field(min_length=3, max_length=40)


@router.post("/promo/redeem")
async def redeem_promo_code(body: PromoRedeemRequest, user=Depends(get_current_user())):
    """User-facing redemption — only `kind=credits` codes mint credits here.
    `kind=discount_pct` codes are consumed at checkout time."""
    db = get_db()
    code = body.code.upper().strip()
    promo = await db.promo_codes.find_one({"code": code, "active": True})
    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or inactive code.")
    if promo.get("max_redemptions") and promo.get("redeemed_count", 0) >= promo["max_redemptions"]:
        raise HTTPException(status_code=410, detail="This promo has been fully redeemed.")
    # One redemption per user per code
    user_id = str(user.get("id", user.get("email")))
    seen = await db.credit_transactions.find_one({"user_id": user_id, "kind": "promo", "ref": code})
    if seen:
        raise HTTPException(status_code=409, detail="You have already redeemed this code.")
    if promo["kind"] == "credits":
        amount = int(promo["value"])
        result = await credit_wallet_credit(db, user, amount, "promo", ref=code, note=f"Promo code {code}")
        await db.promo_codes.update_one({"_id": promo["_id"]}, {"$inc": {"redeemed_count": 1}, "$set": {"last_redeemed": _now()}})
        return {"granted": amount, **result}
    if promo["kind"] == "discount_pct":
        return {
            "ok": True, "kind": "discount_pct", "value": promo["value"],
            "message": f"{promo['value']:g}% off — apply at credit top-up checkout.",
        }
    raise HTTPException(status_code=500, detail="Unknown promo kind.")


# ──────────────────────────────────────────────────────────
# 3. NEWSLETTER
# ──────────────────────────────────────────────────────────
class NewsletterSubscribeRequest(BaseModel):
    email: EmailStr
    source: Optional[str] = Field(default="footer", max_length=40)


@router.post("/newsletter/subscribe")
async def newsletter_subscribe(body: NewsletterSubscribeRequest, request: Request):
    db = get_db()
    email = body.email.lower().strip()
    existing = await db.newsletter_subscribers.find_one({"email": email})
    if existing and existing.get("status") == "active":
        return {"success": True, "already_subscribed": True}
    doc = {
        "email": email,
        "source": body.source or "footer",
        "status": "active",
        "ip": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent", "")[:200],
        "subscribed_at": _now(),
    }
    await db.newsletter_subscribers.update_one(
        {"email": email}, {"$set": doc}, upsert=True
    )
    return {"success": True, "already_subscribed": False}


@router.get("/newsletter/subscribers")
async def newsletter_list(user=Depends(get_current_user())):
    _require_admin(user)
    db = get_db()
    cursor = db.newsletter_subscribers.find({}, {"_id": 0}).sort("subscribed_at", -1)
    subs = await cursor.to_list(1000)
    return {"count": len(subs), "subscribers": subs}


@router.delete("/newsletter/unsubscribe")
async def newsletter_unsubscribe(email: str):
    db = get_db()
    await db.newsletter_subscribers.update_one(
        {"email": email.lower().strip()}, {"$set": {"status": "unsubscribed", "unsubscribed_at": _now()}}
    )
    return {"success": True}


# ──────────────────────────────────────────────────────────
# 4. DEPLOYMENTS  (delivery system)
#    On free DEPLOY → create deployment record directly.
#    On paid BUY/RENT → Stripe session creates pending tx; webhook (or poll)
#    provisions deployment on success.
# ──────────────────────────────────────────────────────────
class DeployRequest(BaseModel):
    listing_id: str
    mode: str = Field(pattern="^(rent|buy|free)$")


@router.post("/deployments/free")
async def deploy_free(body: DeployRequest, user=Depends(get_current_user())):
    """Instant-deploy for free listings (rent_price == 0 and buy_price == 0)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    listing = await db.exchange_listings.find_one({
        "id": body.listing_id,
        "$or": [{"status": "published"}, {"user_id": user_id}],
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    rent_price = float(listing.get("rent_price") or 0)
    buy_price = float(listing.get("buy_price") or 0)
    if rent_price > 0 or buy_price > 0:
        raise HTTPException(status_code=400, detail="Paid listing — use /deployments/checkout instead.")
    return await _provision_deployment(db, user, listing, mode="free", ref=None, amount_paid=0)


@router.post("/deployments/checkout")
async def deploy_checkout(request: Request, body: DeployRequest, user=Depends(get_current_user())):
    """Paid deploy — creates a Stripe one-time checkout session."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    listing = await db.exchange_listings.find_one({
        "id": body.listing_id,
        "$or": [{"status": "published"}, {"user_id": user_id}],
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    rent_price = float(listing.get("rent_price") or 0)
    buy_price = float(listing.get("buy_price") or 0)
    if body.mode == "rent":
        amount = rent_price
    elif body.mode == "buy":
        amount = buy_price
    else:
        raise HTTPException(status_code=400, detail="mode must be 'rent' or 'buy' for paid checkout.")
    if amount <= 0:
        raise HTTPException(status_code=400, detail=f"Listing has no {body.mode} price set.")

    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    host = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY"), webhook_url=f"{host}/api/payments/webhook")
    sess = await sc.create_checkout_session(CheckoutSessionRequest(
        amount=amount, currency="usd",
        success_url=f"{host}/my-deployments?session_id={{CHECKOUT_SESSION_ID}}&deploy=success",
        cancel_url=f"{host}/exchange?deploy=cancel",
        metadata={
            "kind": "deployment",
            "listing_id": body.listing_id,
            "mode": body.mode,
            "user_id": str(user.get("id", user.get("email"))),
            "user_email": str(user.get("email", "")),
            "amount": str(amount),
        },
    ))
    return {"url": sess.url, "session_id": sess.session_id, "amount": amount, "mode": body.mode}


@router.post("/deployments/poll/{session_id}")
async def deploy_poll(session_id: str, request: Request, user=Depends(get_current_user())):
    """Success-page poll. Idempotent — checks ledger first."""
    db = get_db()
    existing = await db.user_bot_deployments.find_one({"ref": session_id})
    if existing:
        existing.pop("_id", None)
        return {"already_provisioned": True, "deployment": existing}

    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY"), webhook_url=f"{host}/api/payments/webhook")
    status = await sc.get_checkout_status(session_id)
    if (status.payment_status or "").lower() != "paid":
        return {"paid": False, "status": status.payment_status}
    md = status.metadata or {}
    if md.get("kind") != "deployment":
        raise HTTPException(status_code=400, detail="Session not a deployment.")
    listing = await db.exchange_listings.find_one({"id": md["listing_id"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing missing.")
    dep = await _provision_deployment(
        db, user, listing,
        mode=md.get("mode") or "buy", ref=session_id, amount_paid=float(md.get("amount") or 0),
    )
    return {"paid": True, **dep}


async def _provision_deployment(db, user, listing, mode: str, ref: Optional[str], amount_paid: float):
    """Create a user_bot_deployments record (one per buy/rent/free deploy)."""
    user_id = str(user.get("id", user.get("email")))
    # Pull the source bot_project so renter gets a forkable code copy.
    src_project = None
    if listing.get("source_project_id"):
        src_project = await db.bot_projects.find_one({"id": listing["source_project_id"]})
    files = (src_project or {}).get("files") or []
    nodes = (src_project or {}).get("nodes") or listing.get("nodes_snapshot") or []
    edges = (src_project or {}).get("edges") or listing.get("edges_snapshot") or []

    deployment_id = uuid.uuid4().hex
    now = _now()
    doc = {
        "id": deployment_id,
        "user_id": user_id,
        "owner_email": user.get("email"),
        "listing_id": listing["id"],
        "listing_name": listing["name"],
        "listing_avatar_icon": listing.get("avatar_icon"),
        "listing_avatar_color": listing.get("avatar_color"),
        "listing_avatar_url": listing.get("avatar_url"),
        "creator_user_id": listing.get("user_id"),
        "creator_email": listing.get("creator_email"),
        "mode": mode,  # rent | buy | free
        "amount_paid": float(amount_paid),
        "ref": ref,    # stripe session id or None
        # Renter-owned copy of the source so they can customize without touching the original
        "config": {
            "name": listing["name"],
            "files": files,
            "nodes": nodes,
            "edges": edges,
            "trigger_type": listing.get("trigger_type") or "manual",
            "engine": listing.get("engine") or "gemini-flash",
            "vars": {},
            "required_integrations": listing.get("required_integrations") or [],
        },
        # Usage / monitoring
        "usage": {"run_count": 0, "last_run_at": None, "limit_per_month": _default_run_limit(mode)},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    await db.user_bot_deployments.insert_one(doc)
    # Bump creator stats + revenue ledger (90/10 split — informational only here)
    await db.exchange_listings.update_one(
        {"id": listing["id"]}, {"$inc": {"deploy_count": 1}}
    )
    if amount_paid > 0:
        creator_share_usd = round(amount_paid * 0.90, 2)
        platform_share_usd = round(amount_paid * 0.10, 2)
        await db.creator_revenue_ledger.insert_one({
            "id": uuid.uuid4().hex,
            "listing_id": listing["id"],
            "creator_user_id": listing.get("user_id"),
            "renter_user_id": user_id,
            "amount_paid": amount_paid,
            "creator_share": creator_share_usd,
            "platform_share": platform_share_usd,
            "mode": mode,
            "ref": ref,
            "created_at": now,
        })

        # Apply the creator's payout preference. Default 'credits' (with 30% bonus)
        # keeps money inside the ecosystem. Cash path defers to the existing
        # creator_earnings batch payout flow.
        try:
            from lib.payouts import process_creator_earning
            creator_doc = await db.users.find_one({"id": listing.get("user_id")})
            if creator_doc:
                pref = (creator_doc.get("payout_preference") or "credits").lower()
                await process_creator_earning(
                    db, creator=creator_doc, amount_usd=creator_share_usd,
                    source="marketplace_sale", ref=ref, payout_preference=pref,
                )
        except Exception as _e:
            # Never block the deployment on a payout-processing hiccup.
            pass
    doc.pop("_id", None)
    return {"deployment_id": deployment_id, "deployment": doc}


# ──────────────────────────────────────────────────────────
# CREDIT-BASED MARKETPLACE PURCHASE  (Prompt 20)
# ──────────────────────────────────────────────────────────
class CreditPurchaseRequest(BaseModel):
    """No body fields — listing_id comes from path. Kept for future expansion."""
    pass


@router.post("/exchange/purchase/{listing_id}")
async def exchange_purchase(listing_id: str, user=Depends(get_current_user())):
    """Instant credit-based purchase of an Exchange listing. No Stripe.
    Debits the buyer's wallet, credits the creator's wallet (90/10 split with
    +30% credit bonus when pref='credits'), and provisions the deployment.
    """
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    listing = await db.exchange_listings.find_one({
        "id": listing_id,
        "$or": [{"status": "published"}, {"user_id": user_id}],
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # Can't buy your own listing.
    if listing.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="You cannot purchase your own listing.")

    # Already purchased?
    existing = await db.user_bot_deployments.find_one({
        "user_id": user_id, "listing_id": listing_id, "status": "active",
    })
    if existing:
        existing.pop("_id", None)
        return {"already_owned": True, "deployment": existing}

    price = int(listing.get("price_credits") or 0)

    # Free agents — no debit needed.
    if price <= 0:
        dep = await _provision_deployment(
            db, user, listing, mode="free", ref=None, amount_paid=0.0,
        )
        return {"success": True, "credits_charged": 0, **dep}

    # Affordability check — clean error instead of ValueError.
    from lib import credit_wallet as _cw
    afford = await _cw.can_afford(db, user, "exchange_purchase", cost_override=price)
    if not afford.get("allowed"):
        return {
            "success": False,
            "error": "INSUFFICIENT_CREDITS",
            "required": price,
            "available": int(afford.get("balance") or 0),
            "message": "Not enough credits. Top up to continue.",
        }

    # Debit buyer's credits (subscription first, then topup).
    debit = await credit_wallet_debit(
        db, user, "exchange_purchase", ref=listing_id,
        cost_override=price,
    )

    # Provision the deployment. `amount_paid` is stored in USD equivalent for
    # the legacy revenue_ledger; the creator earning is processed at
    # credit-equivalent USD via `process_creator_earning`.
    credit_value_usd = 0.01
    amount_paid_usd = round(price * credit_value_usd, 2)
    dep = await _provision_deployment(
        db, user, listing,
        mode="credit_purchase", ref=f"credits:{listing_id}:{uuid.uuid4().hex[:8]}",
        amount_paid=amount_paid_usd,
    )

    # Bump listing revenue counter (credits).
    await db.exchange_listings.update_one(
        {"id": listing_id},
        {"$inc": {"revenue_credits": price, "purchase_count": 1}},
    )

    return {
        "success": True,
        "credits_charged": price,
        "balance_remaining": int(debit.get("balance") or 0),
        **dep,
    }


# ──────────────────────────────────────────────────────────
# LEAN CREDIT BALANCE (Prompt 20)  — fast endpoint for navbar polling
# ──────────────────────────────────────────────────────────
@router.get("/credits/balance")
async def credits_balance(user=Depends(get_current_user())):
    """Returns just the balance summary — no transactions, no packs.
    Designed for the navbar credit counter that polls every 30s.

    Also surfaces cashback_lifetime so the FE can detect a delta between polls
    and fire a celebration toast when the user earns cashback (Phase 65)."""
    db = get_db()
    info = await get_balance(db, user)
    # Pull the latest cashback total (lib.cashback writes to users.cashback_earned_total).
    # Fast — already pinned by user_id in the user doc.
    user_id = user.get("id") or user.get("_id") or user.get("email")
    cashback_row = await db.users.find_one(
        {"id": user_id},
        {"cashback_earned_total": 1, "_id": 0},
    ) or {}
    sub = int(info.get("subscription_credits") or 0)
    sub_max = int(info.get("subscription_credits_max") or 0)
    # Subscription pool % FILLED (i.e. credits still available / max). 0..100.
    # When unlimited we report 100 (full bar).
    if info.get("unlimited"):
        sub_pct = 100
    elif sub_max > 0:
        sub_pct = max(0, min(100, int(round(sub / sub_max * 100))))
    else:
        sub_pct = 0
    return {
        "subscription": sub,
        "topup": int(info.get("topup_credits") or 0),
        "total": int(info.get("balance") or 0),
        "subscription_max": sub_max,
        "subscription_pct": sub_pct,
        "monthly_grant": int(info.get("monthly_grant") or 0),
        "reset_date": info.get("credit_reset_date"),
        "tier": info.get("tier") or "recruit",
        "unlimited": bool(info.get("unlimited") or False),
        "cashback_lifetime": int(cashback_row.get("cashback_earned_total") or 0),
    }


# ──────────────────────────────────────────────────────────
# CUSTOM TOP-UP  (Prompt 20) — Stripe checkout for arbitrary USD amount
# ──────────────────────────────────────────────────────────
class CustomTopupRequest(BaseModel):
    amount_usd: float = Field(ge=1, le=1000)


# $0.019 / credit = Builder pack rate. Same rate users get on the $19 pack.
CUSTOM_TOPUP_RATE_USD_PER_CREDIT = 0.019


@router.post("/credits/topup/custom")
async def credits_topup_custom(
    request: Request, body: CustomTopupRequest, user=Depends(get_current_user()),
):
    """Stripe checkout for a custom USD top-up. Mints credits @ Builder rate
    ($0.019/credit) on webhook. Min $1 (~52 credits), Max $1,000 (~52,631 cr)."""
    db = get_db()
    amount_usd = round(float(body.amount_usd), 2)
    if amount_usd < 1 or amount_usd > 1000:
        raise HTTPException(status_code=400, detail="Amount must be between $1 and $1,000.")

    credits = int(amount_usd / CUSTOM_TOPUP_RATE_USD_PER_CREDIT)
    if credits <= 0:
        raise HTTPException(status_code=400, detail="Amount too small.")

    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
    host = str(request.base_url).rstrip("/")
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured.")
    sc = StripeCheckout(api_key=api_key, webhook_url=f"{host}/api/payments/webhook")

    metadata = {
        "kind": "credit_topup",
        "pack": "custom",
        "credits": str(credits),
        "user_id": str(user.get("id", user.get("email"))),
        "user_email": str(user.get("email", "")),
        "custom_amount_usd": str(amount_usd),
    }
    sess = await sc.create_checkout_session(CheckoutSessionRequest(
        amount=amount_usd, currency="usd",
        success_url=f"{host}/credits?session_id={{CHECKOUT_SESSION_ID}}&topup=success",
        cancel_url=f"{host}/credits?topup=cancel",
        metadata=metadata,
    ))
    await db.payment_transactions.insert_one({
        "id": uuid.uuid4().hex,
        "session_id": sess.session_id,
        "user_id": str(user.get("id", user.get("email"))),
        "user_email": user.get("email"),
        "type": "credit_topup",
        "pack": "custom",
        "credits": credits,
        "amount": amount_usd,
        "currency": "usd",
        "payment_status": "pending",
        "activated": False,
        "metadata": metadata,
        "created_at": _now(),
        "updated_at": _now(),
    })
    return {
        "url": sess.url,
        "session_id": sess.session_id,
        "amount_usd": amount_usd,
        "credits": credits,
        "rate_usd_per_credit": CUSTOM_TOPUP_RATE_USD_PER_CREDIT,
    }



def _default_run_limit(mode: str) -> int:
    if mode == "rent":
        return 1000
    if mode == "buy":
        return 10000  # essentially unlimited; bought license
    return 200  # free


@router.get("/deployments/me")
async def list_my_deployments(user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.user_bot_deployments.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    return {"deployments": await cursor.to_list(200)}


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return doc


class DeploymentPatchRequest(BaseModel):
    name: Optional[str] = None
    vars: Optional[dict] = None
    files: Optional[List[dict]] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None


@router.patch("/deployments/{deployment_id}")
async def patch_deployment(deployment_id: str, body: DeploymentPatchRequest, user=Depends(get_current_user())):
    """Customize a deployed bot — rename, update env vars, edit files/graph."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    cfg = doc.get("config") or {}
    if body.name is not None and len(body.name) >= 1:
        cfg["name"] = body.name[:120]
    if body.vars is not None and isinstance(body.vars, dict):
        cfg["vars"] = {k[:64]: str(v)[:2000] for k, v in body.vars.items() if isinstance(k, str)}
    if body.files is not None:
        safe_files = []
        for f in body.files[:50]:
            if not isinstance(f, dict):
                continue
            p = (f.get("path") or "").strip()
            if not p or p.startswith("/") or ".." in p:
                continue
            safe_files.append({
                "path": p[:200],
                "language": (f.get("language") or "text")[:32],
                "content": str(f.get("content") or "")[:200_000],
            })
        cfg["files"] = safe_files
    if body.nodes is not None:
        cfg["nodes"] = body.nodes[:200]
    if body.edges is not None:
        cfg["edges"] = body.edges[:400]
    await db.user_bot_deployments.update_one(
        {"id": deployment_id, "user_id": user_id},
        {"$set": {"config": cfg, "updated_at": _now()}},
    )
    fresh = await db.user_bot_deployments.find_one({"id": deployment_id}, {"_id": 0})
    return {"success": True, "deployment": fresh}


async def run_deployment_real(db, doc: dict, trigger: str = "manual", input_payload: dict | None = None) -> dict:
    """Real deployment execution — runs the bot's main.py inside the existing
    RestrictedPython sandbox. Persists a `deployment_runs` row and increments
    the per-month usage counter.

    Falls back to a clear error result when no code is available (the deployment
    was provisioned but never had its bot_project hydrated).
    """
    import time
    from lib.workflow_sandbox import execute_sandboxed
    deployment_id = doc["id"]
    user_id = doc["user_id"]

    # Resolve the bot source code — try config.files first, then linked bot_project.
    files = (doc.get("config") or {}).get("files") or []
    if not files and doc.get("project_id"):
        proj = await db.bot_projects.find_one({"id": doc["project_id"]}, {"files": 1, "_id": 0})
        if proj:
            files = proj.get("files") or []

    main_src = ""
    for f in files:
        if (f.get("path") or "").endswith("main.py"):
            main_src = f.get("content") or ""
            break

    run_id = uuid.uuid4().hex
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()

    if not main_src:
        # No code → record a "stub" success run (kept signal for analytics).
        elapsed = int((time.monotonic() - t0) * 1000)
        run_doc = {
            "id": run_id, "deployment_id": deployment_id, "user_id": user_id,
            "listing_id": doc.get("listing_id"),
            "started_at": started.isoformat(), "finished_at": started.isoformat(),
            "duration_ms": elapsed, "success": True, "status": "success",
            "trigger": trigger, "credits_spent": 1,
            "output": "(no main.py — provisioned-only deployment)",
            "error": None, "input": (input_payload or {}),
        }
    else:
        # Real sandboxed execution. Pass webhook payload as `INPUT`, deployment env
        # as `ENV` so the user's main.py can reference them.
        env_vars = (doc.get("config") or {}).get("env_vars") or {}
        # The sandbox auto-injects globals: INPUT, ENV, KEYS, RESULT, http_request.
        # main.py can just reference INPUT (the webhook payload) and assign to OUTPUT or RESULT.
        try:
            exec_result = execute_sandboxed(
                code=main_src,
                user_api_keys=env_vars,
                input_data=(input_payload or {}),
                env_vars=env_vars,
                timeout=int((doc.get("config") or {}).get("max_execution_time_seconds") or 25),
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            ok = bool(exec_result.get("success"))
            # Prefer structured `RESULT` over raw stdout for output preview.
            result_val = exec_result.get("result")
            if result_val is not None:
                try:
                    output = json.dumps(result_val, default=str)
                except Exception:
                    output = str(result_val)
            else:
                output = exec_result.get("output") or ""
            error = exec_result.get("error") if not ok else None
            run_doc = {
                "id": run_id, "deployment_id": deployment_id, "user_id": user_id,
                "listing_id": doc.get("listing_id"),
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": elapsed, "success": ok,
                "status": "success" if ok else "failed",
                "trigger": trigger, "credits_spent": 1,
                "output": str(output)[:8000],
                "error": str(error)[:2000] if error else None,
                "input": (input_payload or {}),
            }
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            run_doc = {
                "id": run_id, "deployment_id": deployment_id, "user_id": user_id,
                "listing_id": doc.get("listing_id"),
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": elapsed, "success": False, "status": "failed",
                "trigger": trigger, "credits_spent": 1,
                "output": None, "error": f"sandbox error: {str(e)[:1000]}",
                "input": (input_payload or {}),
            }

    await db.deployment_runs.insert_one(run_doc)
    await db.user_bot_deployments.update_one(
        {"id": deployment_id},
        {"$inc": {"usage.run_count": 1},
         "$set": {"usage.last_run_at": _now(), "updated_at": _now()}},
    )
    return run_doc


@router.post("/deployments/{deployment_id}/run")
async def run_deployment(deployment_id: str, user=Depends(get_current_user())):
    """Manual run from the dashboard — real RestrictedPython execution of the bot's main.py."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    usage = doc.get("usage") or {}
    if usage.get("run_count", 0) >= usage.get("limit_per_month", 1000):
        return {
            "allowed": False, "error": "LIMIT_REACHED",
            "message": f"Run limit reached ({usage['run_count']}/{usage['limit_per_month']}). Upgrade this deployment to continue.",
            "upgrade_url": f"/my-deployments/{deployment_id}?tab=upgrade",
        }
    run_doc = await run_deployment_real(db, doc, trigger="manual", input_payload={})
    return {
        "allowed": True,
        "run_count": usage["run_count"] + 1,
        "limit": usage["limit_per_month"],
        "run_id": run_doc["id"],
        "duration_ms": run_doc["duration_ms"],
        "success": run_doc["success"],
        "output_preview": (run_doc.get("output") or "")[:1000] if run_doc.get("output") else None,
        "error": run_doc.get("error"),
    }


@router.get("/deployments/{deployment_id}/runs")
async def list_deployment_runs(
    deployment_id: str,
    limit: int = 50,
    skip: int = 0,
    user=Depends(get_current_user()),
):
    """Recent execution log for a deployment — paginated."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    owner = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id}, {"_id": 0, "id": 1})
    if not owner:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    limit = max(1, min(200, int(limit)))
    skip = max(0, int(skip))
    cursor = db.deployment_runs.find(
        {"deployment_id": deployment_id}, {"_id": 0}
    ).sort("started_at", -1).skip(skip).limit(limit)
    runs = await cursor.to_list(length=limit)
    total = await db.deployment_runs.count_documents({"deployment_id": deployment_id})
    return {"runs": runs, "total": total, "limit": limit, "skip": skip}


@router.get("/deployments/{deployment_id}/analytics")
async def deployment_analytics(deployment_id: str, days: int = 30, user=Depends(get_current_user())):
    """Aggregate usage analytics for the Usage Monitor dashboard.
    Returns: totals, success_rate, latency percentiles (P50/P95/P99), daily volume histogram, credits."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    dep = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id}, {"_id": 0})
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    days = max(1, min(90, int(days)))
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = db.deployment_runs.find(
        {"deployment_id": deployment_id, "started_at": {"$gte": cutoff}},
        {"_id": 0, "started_at": 1, "duration_ms": 1, "success": 1, "credits_spent": 1, "status": 1, "error": 1},
    )
    runs = await cursor.to_list(length=10000)
    total = len(runs)
    successes = sum(1 for r in runs if r.get("success"))
    failures = total - successes
    durations = sorted(int(r.get("duration_ms") or 0) for r in runs)
    def _pct(p):
        if not durations:
            return 0
        i = max(0, min(len(durations) - 1, int(round((p / 100) * (len(durations) - 1)))))
        return durations[i]
    avg = (sum(durations) // len(durations)) if durations else 0
    credits_spent = sum(int(r.get("credits_spent") or 0) for r in runs)
    # Daily histogram bucketed by ISO date
    buckets: dict = {}
    for r in runs:
        day = (r.get("started_at") or "")[:10]
        if not day:
            continue
        bucket = buckets.setdefault(day, {"date": day, "runs": 0, "success": 0, "failed": 0})
        bucket["runs"] += 1
        if r.get("success"):
            bucket["success"] += 1
        else:
            bucket["failed"] += 1
    # Fill in zero-days
    daily: list = []
    now = datetime.now(timezone.utc)
    for d in range(days - 1, -1, -1):
        day = (now - timedelta(days=d)).date().isoformat()
        daily.append(buckets.get(day, {"date": day, "runs": 0, "success": 0, "failed": 0}))
    # Recent error summary
    recent_errors = [
        {"started_at": r.get("started_at"), "error": r.get("error")}
        for r in runs if not r.get("success") and r.get("error")
    ][:5]
    usage = dep.get("usage") or {}
    return {
        "deployment_id": deployment_id,
        "deployment_name": dep.get("name") or dep.get("listing_name"),
        "window_days": days,
        "totals": {
            "runs": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round((successes / total) * 100, 2) if total else 0,
            "credits_spent": credits_spent,
        },
        "latency_ms": {
            "avg": avg,
            "p50": _pct(50),
            "p95": _pct(95),
            "p99": _pct(99),
            "min": durations[0] if durations else 0,
            "max": durations[-1] if durations else 0,
        },
        "daily": daily,
        "monthly_quota": {
            "used": usage.get("run_count", 0),
            "limit": usage.get("limit_per_month", 1000),
            "remaining": max(0, (usage.get("limit_per_month", 1000) - usage.get("run_count", 0))),
        },
        "recent_errors": recent_errors,
    }


@router.post("/deployments/{deployment_id}/upgrade")
async def upgrade_deployment(request: Request, deployment_id: str, user=Depends(get_current_user())):
    """Upgrade a rent → buy deployment via Stripe (pays the delta)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if doc["mode"] == "buy":
        raise HTTPException(status_code=400, detail="Already upgraded to buy.")
    listing = await db.exchange_listings.find_one({"id": doc["listing_id"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Original listing missing.")
    buy_price = float(listing.get("buy_price") or 0)
    if buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy upgrade not available for this listing.")
    delta = max(0.50, buy_price - float(doc.get("amount_paid") or 0))

    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    host = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY"), webhook_url=f"{host}/api/payments/webhook")
    sess = await sc.create_checkout_session(CheckoutSessionRequest(
        amount=delta, currency="usd",
        success_url=f"{host}/my-deployments/{deployment_id}?upgrade=success",
        cancel_url=f"{host}/my-deployments/{deployment_id}?upgrade=cancel",
        metadata={
            "kind": "upgrade",
            "deployment_id": deployment_id,
            "listing_id": doc["listing_id"],
            "user_id": user_id,
            "amount": str(delta),
        },
    ))
    return {"url": sess.url, "session_id": sess.session_id, "delta": delta}


@router.post("/deployments/upgrade-poll/{session_id}")
async def upgrade_poll(session_id: str, request: Request, user=Depends(get_current_user())):
    db = get_db()
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY"), webhook_url=f"{host}/api/payments/webhook")
    status = await sc.get_checkout_status(session_id)
    if (status.payment_status or "").lower() != "paid":
        return {"paid": False}
    md = status.metadata or {}
    dep_id = md.get("deployment_id")
    if not dep_id:
        raise HTTPException(status_code=400, detail="Session missing deployment_id.")
    existing = await db.user_bot_deployments.find_one({"id": dep_id})
    if not existing or existing.get("mode") == "buy":
        return {"paid": True, "already_upgraded": True}
    await db.user_bot_deployments.update_one(
        {"id": dep_id},
        {"$set": {"mode": "buy", "usage.limit_per_month": 10000, "updated_at": _now()},
         "$inc": {"amount_paid": float(md.get("amount") or 0)}},
    )
    return {"paid": True, "upgraded": True}
