"""
The Bounty Board — Prompt 9

Demand-driven counterpart to The Exchange. Users post requests for agents they
need, attach a credit bounty held in escrow, and creators compete to build the
solution. Winner gets the bounty + their agent is auto-listed on The Exchange
(or, if already published, gets a "Bounty Winner" badge on its listing).

Schema:
    bounties:
        id, poster_id, poster_email, poster_name,
        title, description, category, required_integrations[],
        input_expectations, output_expectations, example_use_case,
        reward_type ("credits" — cash deferred to Stripe-Connect work),
        reward_amount (>= 50),
        escrow_status (held | released | refunded),
        deadline (ISO), max_submissions (1..50, default 10),
        status (open | in_review | awarded | expired | cancelled),
        winner_id, winner_submission_id, winner_listing_id,
        submission_count, created_at, updated_at, awarded_at, expired_at

    bounty_submissions:
        id, bounty_id, creator_id, creator_email, creator_name,
        agent_source ("exchange" | "external"),
        source_id (listing_id or package_id),
        agent_label (snapshot of name for display),
        pitch (max 2000 chars),
        status (submitted | winner | rejected),
        submitted_at, reviewed_at

Janitor:
    `expire_lapsed_bounties(db)` — runs hourly via APScheduler. Flips open
    bounties past (deadline + 7d grace) to status='expired' and refunds the
    escrow if no winner was selected. Also flips bounties past deadline w/
    submissions to 'in_review' (poster has 7d to award before auto-refund).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("bounties")

router = APIRouter()


# ── Constants ──────────────────────────────────────────────────────────────
MIN_REWARD = 50
MAX_REWARD = 1_000_000
MIN_DAYS = 3
MAX_DAYS = 30
GRACE_PERIOD_DAYS = 7  # how long after deadline poster has to award before auto-refund
MIN_SUBS = 1
MAX_SUBS = 50
# Cash bounty bounds (USD).
MIN_CASH_USD = 10.0
MAX_CASH_USD = 10_000.0

CATEGORIES = (
    "customer_support", "sales", "data_analysis",
    "coding", "creative", "finance", "automation", "other",
)

VALID_STATUS = ("open", "in_review", "awarded", "expired", "cancelled")


# ── DI shims ───────────────────────────────────────────────────────────────
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


def _project(b: dict) -> dict:
    """Strip Mongo `_id` + compute denormalised fields for the UI."""
    if not b:
        return None
    out = {k: v for k, v in b.items() if k != "_id"}
    # Computed: time remaining vs deadline
    try:
        dl = datetime.fromisoformat(b.get("deadline").replace("Z", "+00:00"))
        delta = dl - _now_dt()
        out["seconds_remaining"] = max(0, int(delta.total_seconds()))
    except Exception:
        out["seconds_remaining"] = 0
    return out


# ── Pydantic ───────────────────────────────────────────────────────────────
class CreateBountyRequest(BaseModel):
    title: str = Field(min_length=8, max_length=120)
    description: str = Field(min_length=20, max_length=10_000)
    category: str
    required_integrations: List[str] = Field(default_factory=list, max_length=20)
    input_expectations: str = Field(default="", max_length=2_000)
    output_expectations: str = Field(default="", max_length=2_000)
    example_use_case: str = Field(default="", max_length=2_000)
    # `reward_type` defaults to credits for backward compat. For cash, provide
    # `cash_amount_usd` (USD float) — `reward_amount` is ignored.
    reward_type: str = Field(default="credits", pattern="^(credits|cash)$")
    reward_amount: int = Field(default=0, ge=0, le=MAX_REWARD)
    cash_amount_usd: Optional[float] = Field(default=None, ge=MIN_CASH_USD, le=MAX_CASH_USD)
    origin_url: Optional[str] = Field(default=None, max_length=2_000,
                                      description="Required for cash bounties — frontend host for "
                                                  "success/cancel redirect URLs.")
    deadline_days: int = Field(ge=MIN_DAYS, le=MAX_DAYS,
                               description="Number of days from now until the bounty closes.")
    max_submissions: int = Field(default=10, ge=MIN_SUBS, le=MAX_SUBS)


class UpdateBountyRequest(BaseModel):
    """Posters can extend the deadline OR bump max_submissions BEFORE awarding.
    Reward/description/title are LOCKED once the first submission lands so creators
    aren't bait-and-switched after committing time."""
    deadline_days: Optional[int] = Field(default=None, ge=MIN_DAYS, le=MAX_DAYS)
    max_submissions: Optional[int] = Field(default=None, ge=MIN_SUBS, le=MAX_SUBS)
    description: Optional[str] = Field(default=None, min_length=20, max_length=10_000)


class SubmitRequest(BaseModel):
    agent_source: str = Field(pattern="^(exchange|external)$")
    source_id: str = Field(min_length=4, max_length=64)
    pitch: str = Field(min_length=20, max_length=2_000)


class AwardRequest(BaseModel):
    submission_id: str = Field(min_length=4, max_length=64)


# ── Helpers ────────────────────────────────────────────────────────────────
async def _verify_agent_belongs_to_creator(db, source: str, source_id: str, creator_id: str):
    """Confirm the submitted agent_source/source_id pair is actually owned by the
    creator. Prevents submitting someone else's listing/package as one's own."""
    if source == "exchange":
        doc = await db.exchange_listings.find_one(
            {"id": source_id, "user_id": creator_id},
            {"id": 1, "name": 1, "status": 1, "agent_name": 1, "title": 1},
        )
        if not doc:
            raise HTTPException(status_code=403,
                                detail="You do not own that Exchange listing.")
        return doc.get("name") or doc.get("agent_name") or doc.get("title") or "Exchange agent"
    if source == "external":
        doc = await db.agent_packages.find_one(
            {"id": source_id, "user_id": creator_id},
            {"id": 1, "manifest": 1},
        )
        if not doc:
            raise HTTPException(status_code=403,
                                detail="You do not own that external agent package.")
        m = doc.get("manifest") or {}
        return m.get("display_name") or m.get("name") or "External agent"
    raise HTTPException(status_code=400, detail="invalid agent_source")


def _emit_notification(db, recipient_id: str, kind: str, message: str,
                       payload: Optional[dict] = None):
    """Fire-and-forget in-app notification. v1 just inserts into `notifications`
    so a future bell UI can read them; toast emission is frontend-side."""
    async def _insert():
        await db.notifications.insert_one({
            "id": uuid.uuid4().hex,
            "user_id": recipient_id,
            "kind": kind,
            "message": message,
            "payload": payload or {},
            "read": False,
            "created_at": _now(),
        })
    # Schedule but don't await — never block the request on notifications.
    import asyncio
    asyncio.create_task(_insert())


# ── Create / List / Read / Update / Cancel ─────────────────────────────────
@router.post("/bounties")
async def create_bounty(req: CreateBountyRequest, user=Depends(get_current_user())):
    """Post a new bounty. For credit bounties, debits the wallet immediately into
    escrow. For cash bounties, returns a Stripe Checkout URL — the bounty is
    created in `status='pending_payment'` and activated by the success page poll."""
    from lib import credit_wallet
    db = get_db()
    if req.category not in CATEGORIES:
        raise HTTPException(status_code=400,
                            detail=f"category must be one of {CATEGORIES}")

    if req.reward_type == "credits":
        if req.reward_amount < MIN_REWARD:
            raise HTTPException(status_code=422,
                                detail=f"Credit bounties must offer at least {MIN_REWARD} credits.")
        # Affordability precheck — clean 402 instead of ValueError.
        afford = await credit_wallet.can_afford(db, user, "bounty_escrow",
                                                cost_override=req.reward_amount)
        if not afford.get("allowed"):
            raise HTTPException(status_code=402, detail={
                "error": "INSUFFICIENT_CREDITS",
                "needed": req.reward_amount,
                "balance": afford.get("balance"),
                "message": f"You need {req.reward_amount} credits to escrow this bounty. "
                           "Top up your wallet to post.",
            })
        bounty_id = uuid.uuid4().hex
        debit = await credit_wallet.debit(
            db, user, "bounty_escrow", ref=bounty_id, cost_override=req.reward_amount,
        )
        deadline = _now_dt() + timedelta(days=req.deadline_days)
        doc = {
            "id": bounty_id,
            "poster_id": _user_id(user),
            "poster_email": user.get("email"),
            "poster_name": user.get("display_name") or user.get("name") or user.get("email"),
            "title": req.title.strip(),
            "description": req.description.strip(),
            "category": req.category,
            "required_integrations": [s.strip() for s in req.required_integrations if s.strip()][:20],
            "input_expectations": req.input_expectations.strip(),
            "output_expectations": req.output_expectations.strip(),
            "example_use_case": req.example_use_case.strip(),
            "reward_type": "credits",
            "reward_amount": req.reward_amount,
            "reward_currency": None,
            "escrow_status": "held",
            "deadline": deadline.isoformat(),
            "max_submissions": req.max_submissions,
            "status": "open",
            "winner_id": None,
            "winner_submission_id": None,
            "winner_listing_id": None,
            "submission_count": 0,
            "created_at": _now(),
            "updated_at": _now(),
            "awarded_at": None,
            "expired_at": None,
        }
        await db.bounties.insert_one(doc)
        return {
            "bounty": _project(doc),
            "credits_remaining": debit.get("balance"),
        }

    # ── Cash bounty path ──
    if not req.cash_amount_usd or req.cash_amount_usd < MIN_CASH_USD:
        raise HTTPException(status_code=422,
                            detail=f"Cash bounties must offer at least ${MIN_CASH_USD:.0f}.")
    if not req.origin_url:
        raise HTTPException(status_code=422,
                            detail="origin_url is required for cash bounties (for Stripe redirect URLs).")
    # Lazy import the Stripe wrapper to keep the credit path zero-dependency.
    import os as _os
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )

    bounty_id = uuid.uuid4().hex
    deadline = _now_dt() + timedelta(days=req.deadline_days)
    doc = {
        "id": bounty_id,
        "poster_id": _user_id(user),
        "poster_email": user.get("email"),
        "poster_name": user.get("display_name") or user.get("name") or user.get("email"),
        "title": req.title.strip(),
        "description": req.description.strip(),
        "category": req.category,
        "required_integrations": [s.strip() for s in req.required_integrations if s.strip()][:20],
        "input_expectations": req.input_expectations.strip(),
        "output_expectations": req.output_expectations.strip(),
        "example_use_case": req.example_use_case.strip(),
        "reward_type": "cash",
        "reward_amount": float(req.cash_amount_usd),  # store dollars for display
        "reward_currency": "USD",
        "escrow_status": "pending",  # flips to 'held' on payment success
        "deadline": deadline.isoformat(),
        "max_submissions": req.max_submissions,
        "status": "pending_payment",  # flips to 'open' on payment success
        "winner_id": None,
        "winner_submission_id": None,
        "winner_listing_id": None,
        "submission_count": 0,
        "stripe_checkout_session_id": None,
        "stripe_charge_id": None,
        "stripe_payment_intent_id": None,
        "stripe_transfer_id": None,
        "created_at": _now(),
        "updated_at": _now(),
        "awarded_at": None,
        "expired_at": None,
    }
    await db.bounties.insert_one(doc)

    host_url = req.origin_url.rstrip("/")
    webhook_url = f"{_os.environ.get('REACT_APP_BACKEND_URL', host_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=_os.environ.get("STRIPE_API_KEY"),
                                     webhook_url=webhook_url)
    checkout_req = CheckoutSessionRequest(
        amount=float(req.cash_amount_usd),
        currency="usd",
        success_url=f"{host_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&type=bounty",
        cancel_url=f"{host_url}/bounties",
        metadata={
            "type": "bounty",
            "bounty_id": bounty_id,
            "user_id": _user_id(user),
            "user_email": user.get("email") or "",
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)
    await db.bounties.update_one(
        {"id": bounty_id},
        {"$set": {"stripe_checkout_session_id": session.session_id, "updated_at": _now()}},
    )
    # Also write a payment_transactions row so the existing webhook + status
    # poller logic can pick it up.
    await db.payment_transactions.insert_one({
        "id": uuid.uuid4().hex,
        "session_id": session.session_id,
        "user_id": _user_id(user),
        "user_email": user.get("email"),
        "type": "bounty",
        "bounty_id": bounty_id,
        "amount": float(req.cash_amount_usd),
        "currency": "usd",
        "payment_status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
    })
    return {
        "bounty": _project({**doc, "stripe_checkout_session_id": session.session_id}),
        "checkout_url": session.url,
        "session_id": session.session_id,
    }


@router.post("/bounties/{bounty_id}/activate")
async def activate_cash_bounty(bounty_id: str, user=Depends(get_current_user())):
    """Frontend polls this after the Stripe redirect. If the linked payment_transactions
    row is 'paid', flip the bounty to status='open' + escrow_status='held' and
    persist the Stripe charge_id (needed later for refunds/transfers)."""
    import stripe
    import os as _os
    stripe.api_key = _os.environ.get("STRIPE_API_KEY")
    db = get_db()
    bounty = await db.bounties.find_one({"id": bounty_id})
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    if bounty["poster_id"] != _user_id(user):
        raise HTTPException(status_code=403, detail="Only the poster can activate this bounty.")
    if bounty["status"] == "open":
        return {"already_active": True, "bounty": _project(bounty)}
    if bounty["status"] != "pending_payment":
        raise HTTPException(status_code=409, detail=f"Cannot activate — status={bounty['status']}")
    sid = bounty.get("stripe_checkout_session_id")
    if not sid:
        raise HTTPException(status_code=409, detail="Missing checkout session id.")
    tx = await db.payment_transactions.find_one({"session_id": sid})
    if not tx or tx.get("payment_status") != "paid":
        raise HTTPException(status_code=402,
                            detail=f"Payment not confirmed yet (status={tx and tx.get('payment_status')}).")
    # Pull charge_id from the Stripe session for later refund/transfer.
    charge_id = bounty.get("stripe_charge_id")
    payment_intent_id = bounty.get("stripe_payment_intent_id")
    if not charge_id:
        try:
            session_obj = stripe.checkout.Session.retrieve(sid, expand=["payment_intent"])
            pi = session_obj.payment_intent
            if pi:
                payment_intent_id = pi.id if hasattr(pi, "id") else pi
                # Latest_charge may be a string id or expanded object.
                latest_charge = getattr(pi, "latest_charge", None)
                if isinstance(latest_charge, str):
                    charge_id = latest_charge
                elif latest_charge:
                    charge_id = latest_charge.id
        except Exception as e:
            logger.warning(f"failed to retrieve charge_id for bounty {bounty_id}: {e}")
    await db.bounties.update_one(
        {"id": bounty_id},
        {"$set": {
            "status": "open",
            "escrow_status": "held",
            "stripe_charge_id": charge_id,
            "stripe_payment_intent_id": payment_intent_id,
            "updated_at": _now(),
        }},
    )
    fresh = await db.bounties.find_one({"id": bounty_id})
    return {"already_active": False, "bounty": _project(fresh)}


@router.get("/bounties")
async def list_bounties(
    category: Optional[str] = None,
    status: Optional[str] = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|highest_reward|ending_soon|most_submissions)$"),
    page: int = Query(default=1, ge=1, le=200),
    page_size: int = Query(default=24, ge=1, le=100),
):
    """Public list — anyone (even unauthenticated) sees all open bounties."""
    db = get_db()
    q: dict = {}
    if category and category != "all":
        if category not in CATEGORIES:
            raise HTTPException(status_code=400, detail="invalid category")
        q["category"] = category
    if status and status != "all":
        if status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail="invalid status")
        q["status"] = status
    # If no explicit status filter, hide cancelled rows from the public feed.
    if "status" not in q:
        q["status"] = {"$nin": ["cancelled"]}

    sort_map = {
        "newest": [("created_at", -1)],
        "highest_reward": [("reward_amount", -1), ("created_at", -1)],
        "ending_soon": [("deadline", 1)],
        "most_submissions": [("submission_count", -1), ("created_at", -1)],
    }
    skip = (page - 1) * page_size
    total = await db.bounties.count_documents(q)
    cursor = db.bounties.find(q, {"_id": 0}).sort(sort_map[sort]).skip(skip).limit(page_size)
    items = [_project(b) for b in await cursor.to_list(length=page_size)]

    # Aggregate stats for the landing strip.
    stats = await db.bounties.aggregate([
        {"$group": {
            "_id": None,
            "active": {"$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}},
            "awarded_count": {"$sum": {"$cond": [{"$eq": ["$status", "awarded"]}, 1, 0]}},
            "credits_paid_out": {"$sum": {
                "$cond": [{"$eq": ["$status", "awarded"]}, "$reward_amount", 0],
            }},
        }},
    ]).to_list(length=1)
    s = stats[0] if stats else {}
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "active": int(s.get("active") or 0),
            "awarded_count": int(s.get("awarded_count") or 0),
            "credits_paid_out": int(s.get("credits_paid_out") or 0),
        },
    }


@router.get("/bounties/my-posted")
async def my_posted(user=Depends(get_current_user())):
    db = get_db()
    cursor = db.bounties.find({"poster_id": _user_id(user)}, {"_id": 0}).sort("created_at", -1)
    items = [_project(b) for b in await cursor.to_list(length=200)]
    return {"items": items}


@router.get("/bounties/my-submissions")
async def my_submissions(user=Depends(get_current_user())):
    db = get_db()
    creator_id = _user_id(user)
    subs = await db.bounty_submissions.find(
        {"creator_id": creator_id}, {"_id": 0}
    ).sort("submitted_at", -1).to_list(length=200)
    # Hydrate each submission with its bounty (so the UI knows title + reward + status).
    bounty_ids = list({s["bounty_id"] for s in subs})
    bounties = {}
    if bounty_ids:
        bs = await db.bounties.find({"id": {"$in": bounty_ids}}, {"_id": 0}).to_list(length=200)
        bounties = {b["id"]: _project(b) for b in bs}
    for s in subs:
        s["bounty"] = bounties.get(s["bounty_id"])
    return {"items": subs}


@router.get("/bounties/{bounty_id}")
async def get_bounty(bounty_id: str, user=Depends(get_current_user())):
    """Single-bounty fetch. Logged-in users see whether they've already submitted."""
    db = get_db()
    doc = await db.bounties.find_one({"id": bounty_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    out = _project(doc)
    creator_id = _user_id(user)
    out["is_poster"] = doc["poster_id"] == creator_id
    out["my_submission"] = await db.bounty_submissions.find_one(
        {"bounty_id": bounty_id, "creator_id": creator_id}, {"_id": 0},
    )
    return out


@router.put("/bounties/{bounty_id}")
async def update_bounty(bounty_id: str, req: UpdateBountyRequest,
                        user=Depends(get_current_user())):
    db = get_db()
    doc = await db.bounties.find_one({"id": bounty_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    if doc["poster_id"] != _user_id(user):
        raise HTTPException(status_code=403, detail="Only the poster can update a bounty.")
    if doc["status"] not in ("open", "in_review"):
        raise HTTPException(status_code=409, detail=f"Cannot update — status={doc['status']}")
    patch: dict = {}
    if req.deadline_days is not None:
        # Bump deadline FORWARD only (extension) — never shrink.
        new_dl = _now_dt() + timedelta(days=req.deadline_days)
        if new_dl.isoformat() < doc["deadline"]:
            raise HTTPException(status_code=400,
                                detail="New deadline must be later than the current one.")
        patch["deadline"] = new_dl.isoformat()
    if req.max_submissions is not None:
        if req.max_submissions < int(doc.get("submission_count") or 0):
            raise HTTPException(status_code=400,
                                detail="max_submissions cannot be lower than current submission count.")
        patch["max_submissions"] = req.max_submissions
    if req.description is not None:
        # Description edit locked once submissions land — bait-and-switch protection.
        if int(doc.get("submission_count") or 0) > 0:
            raise HTTPException(status_code=409,
                                detail="Description is locked once a submission has been received.")
        patch["description"] = req.description.strip()
    if not patch:
        return _project(doc)
    patch["updated_at"] = _now()
    await db.bounties.update_one({"id": bounty_id}, {"$set": patch})
    return _project(await db.bounties.find_one({"id": bounty_id}, {"_id": 0}))


@router.post("/bounties/{bounty_id}/cancel")
async def cancel_bounty(bounty_id: str, user=Depends(get_current_user())):
    """Poster cancels an OPEN bounty with NO submissions — full escrow refund.
    Cancelling with submissions is disallowed; let it run its course or pick a
    winner (the latter is what they agreed to when they posted)."""
    from lib import credit_wallet
    db = get_db()
    doc = await db.bounties.find_one({"id": bounty_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    if doc["poster_id"] != _user_id(user):
        raise HTTPException(status_code=403, detail="Only the poster can cancel.")
    if doc["status"] not in ("open", "pending_payment"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel — status={doc['status']}")
    if int(doc.get("submission_count") or 0) > 0:
        raise HTTPException(status_code=409,
                            detail="Cannot cancel a bounty that already has submissions. "
                                   "Wait it out or award a winner.")

    refunded_balance = None
    if doc.get("reward_type") == "cash":
        # Stripe refund — only if the payment was actually charged (status != pending_payment).
        if doc["status"] == "open" and doc.get("stripe_charge_id"):
            from routes.stripe_connect import refund_charge
            try:
                refund_charge(doc["stripe_charge_id"],
                              metadata={"bounty_id": bounty_id, "reason": "poster_cancel"})
            except Exception as e:
                logger.error(f"refund failed for bounty {bounty_id}: {e}")
                raise HTTPException(status_code=502,
                                    detail=f"Stripe refund failed: {e}")
    else:
        # Credit refund.
        refund = await credit_wallet.credit(
            db, user, doc["reward_amount"], source="bounty_refund",
            ref=bounty_id, note=f"Refund for cancelled bounty: {doc['title']}",
            pool="topup",
        )
        refunded_balance = refund.get("balance")

    await db.bounties.update_one(
        {"id": bounty_id},
        {"$set": {
            "status": "cancelled",
            "escrow_status": "refunded",
            "updated_at": _now(),
            "cancelled_at": _now(),
        }},
    )
    return {"success": True, "refunded": doc["reward_amount"],
            "reward_type": doc.get("reward_type", "credits"),
            "credits_remaining": refunded_balance}


# ── Submissions ────────────────────────────────────────────────────────────
@router.post("/bounties/{bounty_id}/submit")
async def submit_to_bounty(bounty_id: str, req: SubmitRequest,
                           user=Depends(get_current_user())):
    """Submit one of YOUR Exchange listings or external agents to a bounty."""
    db = get_db()
    creator_id = _user_id(user)
    doc = await db.bounties.find_one({"id": bounty_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    if doc["status"] not in ("open",):
        raise HTTPException(status_code=409,
                            detail=f"Submissions closed — bounty status={doc['status']}")
    if doc["poster_id"] == creator_id:
        raise HTTPException(status_code=403,
                            detail="You cannot submit to your own bounty.")
    if int(doc.get("submission_count") or 0) >= int(doc.get("max_submissions") or 10):
        raise HTTPException(status_code=409, detail="This bounty has reached its max submissions cap.")

    # Prevent duplicate submissions from the same creator.
    if await db.bounty_submissions.find_one(
        {"bounty_id": bounty_id, "creator_id": creator_id},
    ):
        raise HTTPException(status_code=409,
                            detail="You've already submitted to this bounty.")

    # Verify ownership of the submitted agent.
    agent_label = await _verify_agent_belongs_to_creator(
        db, req.agent_source, req.source_id, creator_id,
    )

    sub = {
        "id": uuid.uuid4().hex,
        "bounty_id": bounty_id,
        "creator_id": creator_id,
        "creator_email": user.get("email"),
        "creator_name": user.get("display_name") or user.get("name") or user.get("email"),
        "agent_source": req.agent_source,
        "source_id": req.source_id,
        "agent_label": agent_label,
        "pitch": req.pitch.strip(),
        "status": "submitted",
        "submitted_at": _now(),
        "reviewed_at": None,
    }
    await db.bounty_submissions.insert_one(sub)
    await db.bounties.update_one(
        {"id": bounty_id},
        {"$inc": {"submission_count": 1}, "$set": {"updated_at": _now()}},
    )
    _emit_notification(db, doc["poster_id"], "bounty_submission_new",
                       f"New submission on your bounty '{doc['title']}' from {sub['creator_name']}.",
                       payload={"bounty_id": bounty_id, "submission_id": sub["id"]})
    sub.pop("_id", None)
    return {"success": True, "submission": sub}


@router.get("/bounties/{bounty_id}/submissions")
async def list_submissions(bounty_id: str, user=Depends(get_current_user())):
    """Poster sees ALL submissions. Non-posters only see the count + their own."""
    db = get_db()
    doc = await db.bounties.find_one({"id": bounty_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    creator_id = _user_id(user)
    if doc["poster_id"] == creator_id or user.get("role") == "admin":
        subs = await db.bounty_submissions.find(
            {"bounty_id": bounty_id}, {"_id": 0}
        ).sort("submitted_at", -1).to_list(length=200)
        return {"submissions": subs, "total": len(subs)}
    # Non-poster: only their own submission visible.
    my = await db.bounty_submissions.find_one(
        {"bounty_id": bounty_id, "creator_id": creator_id}, {"_id": 0},
    )
    return {
        "submissions": [my] if my else [],
        "total": int(doc.get("submission_count") or 0),
    }


# ── Awarding ───────────────────────────────────────────────────────────────
@router.post("/bounties/{bounty_id}/award")
async def award_bounty(bounty_id: str, req: AwardRequest,
                       user=Depends(get_current_user())):
    """Award the bounty to a submission. Releases escrow to the winner, marks
    the bounty as 'awarded', and tags the winning Exchange listing (if any) with
    the bounty_winner badge."""
    from lib import credit_wallet
    db = get_db()
    doc = await db.bounties.find_one({"id": bounty_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Bounty not found.")
    if doc["poster_id"] != _user_id(user):
        raise HTTPException(status_code=403, detail="Only the poster can award a bounty.")
    if doc["status"] not in ("open", "in_review"):
        raise HTTPException(status_code=409, detail=f"Cannot award — status={doc['status']}")
    sub = await db.bounty_submissions.find_one(
        {"id": req.submission_id, "bounty_id": bounty_id},
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    # Pay the winner.
    winner_doc = await db.users.find_one(
        {"$or": [{"id": sub["creator_id"]}, {"email": sub["creator_email"]}]},
    )
    if not winner_doc:
        raise HTTPException(status_code=500,
                            detail="Winner account is missing — cannot disburse escrow.")

    payout_balance = None
    transfer_id = None
    if doc.get("reward_type") == "cash":
        # Need a fully-onboarded Stripe Connect account to receive cash.
        from routes.stripe_connect import (
            get_account_for_user, is_ready_for_payout, create_transfer,
        )
        connect = await get_account_for_user(db, sub["creator_id"])
        if not is_ready_for_payout(connect):
            raise HTTPException(status_code=409, detail={
                "error": "WINNER_PAYOUTS_NOT_READY",
                "message": "Winner has not completed Stripe Connect onboarding. "
                           "They must finish payout setup before you can award this cash bounty.",
                "winner_email": sub.get("creator_email"),
                "onboarding_url": "/payouts",
            })
        if not doc.get("stripe_charge_id"):
            raise HTTPException(status_code=409,
                                detail="Cash bounty has no recorded Stripe charge — cannot transfer.")
        try:
            tr = create_transfer(
                amount_usd=float(doc["reward_amount"]),
                destination_account=connect["stripe_account_id"],
                source_charge=doc["stripe_charge_id"],
                transfer_group=f"bounty_{bounty_id}",
                metadata={
                    "bounty_id": bounty_id,
                    "winner_user_id": sub["creator_id"],
                    "submission_id": sub["id"],
                },
            )
            transfer_id = tr.id
        except Exception as e:
            logger.error(f"Stripe Transfer.create failed for bounty {bounty_id}: {e}")
            raise HTTPException(status_code=502,
                                detail=f"Stripe payout failed: {e}")
    else:
        payout = await credit_wallet.credit(
            db, winner_doc, doc["reward_amount"], source="bounty_award",
            ref=bounty_id, note=f"Bounty award: {doc['title']}", pool="topup",
        )
        payout_balance = payout.get("balance")

    # Tag the winning Exchange listing (if applicable) so it gets a badge.
    winner_listing_id = None
    if sub["agent_source"] == "exchange":
        listing = await db.exchange_listings.find_one({"id": sub["source_id"]})
        if listing:
            winner_listing_id = listing["id"]
            await db.exchange_listings.update_one(
                {"id": winner_listing_id},
                {"$set": {
                    "bounty_winner": True,
                    "bounty_winner_id": bounty_id,
                    "bounty_winner_title": doc["title"],
                    "updated_at": _now(),
                }, "$inc": {"bounty_wins": 1}},
            )

    # Mark bounty + winning submission + losing submissions.
    await db.bounties.update_one(
        {"id": bounty_id},
        {"$set": {
            "status": "awarded",
            "escrow_status": "released",
            "winner_id": sub["creator_id"],
            "winner_submission_id": sub["id"],
            "winner_listing_id": winner_listing_id,
            "stripe_transfer_id": transfer_id,
            "awarded_at": _now(),
            "updated_at": _now(),
        }},
    )
    await db.bounty_submissions.update_one(
        {"id": sub["id"]},
        {"$set": {"status": "winner", "reviewed_at": _now()}},
    )
    await db.bounty_submissions.update_many(
        {"bounty_id": bounty_id, "id": {"$ne": sub["id"]}},
        {"$set": {"status": "rejected", "reviewed_at": _now()}},
    )
    # Bump the winner's reputation.
    await db.users.update_one(
        {"id": sub["creator_id"]},
        {"$inc": {"bounty_wins": 1, "credits_won_total": doc["reward_amount"]}},
    )
    await db.users.update_one(
        {"id": doc["poster_id"]},
        {"$inc": {"bounties_posted": 1, "credits_paid_out_total": doc["reward_amount"]}},
    )

    # Notify everyone involved.
    reward_label = (
        f"${doc['reward_amount']:.2f}" if doc.get("reward_type") == "cash"
        else f"+{doc['reward_amount']} credits"
    )
    _emit_notification(db, sub["creator_id"], "bounty_won",
                       f"You won the bounty '{doc['title']}'! {reward_label} awarded.",
                       payload={"bounty_id": bounty_id, "reward": doc["reward_amount"],
                                "reward_type": doc.get("reward_type", "credits")})
    # Losers
    losers = await db.bounty_submissions.find(
        {"bounty_id": bounty_id, "id": {"$ne": sub["id"]}}, {"creator_id": 1},
    ).to_list(length=200)
    for loser in losers:
        _emit_notification(db, loser["creator_id"], "bounty_lost",
                           f"Bounty '{doc['title']}' has been awarded. Your submission was not selected.",
                           payload={"bounty_id": bounty_id})

    return {
        "success": True,
        "winner": {
            "creator_id": sub["creator_id"],
            "creator_name": sub["creator_name"],
            "agent_label": sub["agent_label"],
            "submission_id": sub["id"],
        },
        "winner_listing_id": winner_listing_id,
        "winner_credits_balance": payout_balance,
        "stripe_transfer_id": transfer_id,
        "reward_amount": doc["reward_amount"],
        "reward_type": doc.get("reward_type", "credits"),
    }


# ── Janitor (called by APScheduler) ────────────────────────────────────────
async def expire_lapsed_bounties(db) -> int:
    """Sweep that runs hourly. Two phases:
        1. open bounties past `deadline` flip to in_review (poster has grace).
        2. in_review (or open) bounties past `deadline + GRACE_PERIOD` auto-refund
           the poster + flip status='expired'.
    Returns total rows changed."""
    from lib import credit_wallet
    now_dt = _now_dt()
    grace_cutoff = (now_dt - timedelta(days=GRACE_PERIOD_DAYS)).isoformat()

    # Phase 1: open → in_review when deadline passed but grace not yet up.
    flip_p1 = await db.bounties.update_many(
        {"status": "open", "deadline": {"$lt": now_dt.isoformat()}},
        {"$set": {"status": "in_review", "updated_at": _now()}},
    )

    # Phase 2: in_review (any) past deadline+grace → expire + refund.
    candidates = await db.bounties.find(
        {"status": "in_review", "deadline": {"$lt": grace_cutoff}},
    ).to_list(length=500)
    refunded = 0
    for b in candidates:
        if b.get("escrow_status") == "held":
            if b.get("reward_type") == "cash" and b.get("stripe_charge_id"):
                try:
                    from routes.stripe_connect import refund_charge
                    refund_charge(
                        b["stripe_charge_id"],
                        metadata={"bounty_id": b["id"], "reason": "auto_expire"},
                    )
                except Exception as e:
                    logger.warning(f"[bounty-janitor] cash refund failed for {b['id']}: {e}")
                    continue
            else:
                poster = await db.users.find_one(
                    {"$or": [{"id": b["poster_id"]}, {"email": b["poster_email"]}]},
                )
                if poster:
                    try:
                        await credit_wallet.credit(
                            db, poster, b["reward_amount"], source="bounty_refund",
                            ref=b["id"], note=f"Auto-refund (no award): {b['title']}",
                            pool="topup",
                        )
                    except Exception as e:
                        logger.warning(f"[bounty-janitor] credit refund failed for {b['id']}: {e}")
                        continue
        await db.bounties.update_one(
            {"id": b["id"]},
            {"$set": {"status": "expired", "escrow_status": "refunded",
                      "expired_at": _now(), "updated_at": _now()}},
        )
        refunded += 1
    return (flip_p1.modified_count or 0) + refunded


__all__ = ["router", "expire_lapsed_bounties"]
