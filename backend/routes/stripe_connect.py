"""
Stripe Connect Express — onboarding + payouts for marketplace creators.

The platform holds funds in escrow (via the existing emergentintegrations
Checkout flow for the poster's payment). On award, funds are transferred to
the WINNER's connected Express account using stripe.Transfer.create with
source_transaction pointing at the original charge — this satisfies Stripe's
"separate charges and transfers" pattern.

If the winner hasn't onboarded yet (or their account is restricted), the
award flow returns 409 with the onboarding URL so the user can finish first.

Endpoints exposed here:
    GET   /api/stripe-connect/account              — current user's status (live-refreshed)
    POST  /api/stripe-connect/onboard              — start or resume onboarding
    POST  /api/stripe-connect/refresh-link         — fresh AccountLink for incomplete onboarding
    POST  /api/stripe-connect/dashboard-link       — Express dashboard for an onboarded creator
    POST  /api/stripe-connect/refresh-status       — force a server-side refresh

Helpers (called by routes.bounties):
    ensure_account_for_user(db, user) -> connect_account_doc
    is_ready_for_payout(connect_account_doc) -> bool
    create_transfer(amount_usd, destination, source_charge, metadata) -> stripe.Transfer
    refund_charge(charge_id, metadata) -> stripe.Refund
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import stripe

load_dotenv()
logger = logging.getLogger("stripe_connect")

router = APIRouter()
STRIPE_KEY = os.environ.get("STRIPE_API_KEY")
stripe.api_key = STRIPE_KEY


# ── DI shims ───────────────────────────────────────────────────────────────
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


# ── Pydantic ───────────────────────────────────────────────────────────────
class OnboardRequest(BaseModel):
    return_url: str = Field(min_length=8, max_length=2_000)
    refresh_url: Optional[str] = Field(default=None, max_length=2_000)


# ── Account lifecycle ──────────────────────────────────────────────────────
def _project_account(doc: dict) -> dict:
    """Public-safe projection of a connect_accounts row."""
    if not doc:
        return None
    return {
        "stripe_account_id": doc.get("stripe_account_id"),
        "country": doc.get("country") or "US",
        "charges_enabled": bool(doc.get("charges_enabled")),
        "payouts_enabled": bool(doc.get("payouts_enabled")),
        "details_submitted": bool(doc.get("details_submitted")),
        "onboarded_at": doc.get("onboarded_at"),
        "updated_at": doc.get("updated_at"),
        "requirements_currently_due": doc.get("requirements_currently_due") or [],
        "ready_for_payout": bool(
            doc.get("charges_enabled") and doc.get("payouts_enabled") and doc.get("details_submitted")
        ),
    }


async def _fetch_or_create_account(db, user: dict, country: str = "US") -> dict:
    """Idempotent — returns the connect_accounts row for this user, creating a
    fresh Stripe Express account on first call. Does NOT mutate the on-Stripe
    object beyond initial create."""
    user_id = _user_id(user)
    existing = await db.connect_accounts.find_one({"user_id": user_id})
    if existing:
        return existing

    # Create a fresh Express account on Stripe.
    try:
        account = stripe.Account.create(
            type="express",
            country=country,
            email=user.get("email"),
            capabilities={
                "transfers": {"requested": True},
                "card_payments": {"requested": True},
            },
            business_type="individual",
            metadata={"tfai_user_id": user_id, "tfai_email": user.get("email") or ""},
        )
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.error(f"stripe.Account.create failed for {user_id}: {e}")
        raise HTTPException(status_code=502,
                            detail=f"Stripe Connect setup failed: {e.user_message or str(e)}")

    doc = {
        "user_id": user_id,
        "user_email": user.get("email"),
        "stripe_account_id": account.id,
        "country": country,
        "charges_enabled": bool(getattr(account, "charges_enabled", False)),
        "payouts_enabled": bool(getattr(account, "payouts_enabled", False)),
        "details_submitted": bool(getattr(account, "details_submitted", False)),
        "requirements_currently_due": list(
            (getattr(account, "requirements", None) and account.requirements.get("currently_due")) or [],
        ),
        "created_at": _now(),
        "updated_at": _now(),
        "onboarded_at": None,
    }
    await db.connect_accounts.insert_one(doc)
    # Mirror the account id onto the users row for quick lookups.
    await db.users.update_one(
        {"$or": [{"id": user_id}, {"email": user.get("email")}]},
        {"$set": {"stripe_account_id": account.id, "updated_at": _now()}},
    )
    return doc


async def _refresh_account_status(db, account_doc: dict) -> dict:
    """Live-pull the account from Stripe and persist the latest flags."""
    try:
        acct = stripe.Account.retrieve(account_doc["stripe_account_id"])
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.warning(f"refresh failed for {account_doc.get('stripe_account_id')}: {e}")
        return account_doc

    updates = {
        "charges_enabled": bool(getattr(acct, "charges_enabled", False)),
        "payouts_enabled": bool(getattr(acct, "payouts_enabled", False)),
        "details_submitted": bool(getattr(acct, "details_submitted", False)),
        "requirements_currently_due": list(
            (getattr(acct, "requirements", None) and acct.requirements.get("currently_due")) or [],
        ),
        "updated_at": _now(),
    }
    # First-time fully-onboarded → stamp onboarded_at.
    if (updates["charges_enabled"] and updates["payouts_enabled"]
            and updates["details_submitted"] and not account_doc.get("onboarded_at")):
        updates["onboarded_at"] = _now()

    await db.connect_accounts.update_one(
        {"stripe_account_id": account_doc["stripe_account_id"]},
        {"$set": updates},
    )
    fresh = await db.connect_accounts.find_one(
        {"stripe_account_id": account_doc["stripe_account_id"]},
    )
    return fresh


# ── Routes ─────────────────────────────────────────────────────────────────
@router.get("/stripe-connect/account")
async def get_account(user=Depends(get_current_user())):
    """Return the current user's Connect status (live-refreshed if account exists)."""
    db = get_db()
    user_id = _user_id(user)
    doc = await db.connect_accounts.find_one({"user_id": user_id})
    if not doc:
        return {"account": None, "ready_for_payout": False}
    fresh = await _refresh_account_status(db, doc)
    return {"account": _project_account(fresh), "ready_for_payout": _project_account(fresh)["ready_for_payout"]}


@router.post("/stripe-connect/onboard")
async def start_onboarding(req: OnboardRequest, user=Depends(get_current_user())):
    """Create (or reuse) a Stripe Express account, then mint an AccountLink the
    user is redirected to. The user finishes onboarding on Stripe-hosted pages
    and returns to `return_url`."""
    db = get_db()
    doc = await _fetch_or_create_account(db, user)
    refresh_url = req.refresh_url or req.return_url
    try:
        link = stripe.AccountLink.create(
            account=doc["stripe_account_id"],
            refresh_url=refresh_url,
            return_url=req.return_url,
            type="account_onboarding",
        )
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "url": link.url,
        "expires_at": link.expires_at,
        "account": _project_account(doc),
    }


@router.post("/stripe-connect/refresh-link")
async def refresh_onboarding_link(req: OnboardRequest, user=Depends(get_current_user())):
    """Alias for start_onboarding — semantic clarity on the FE side when the
    user returned with an incomplete account and needs a NEW link."""
    return await start_onboarding(req, user)


@router.post("/stripe-connect/dashboard-link")
async def dashboard_link(user=Depends(get_current_user())):
    """Express Dashboard login link — only valid once the account is fully
    onboarded. Returns 409 otherwise so the FE can prompt for onboarding instead."""
    db = get_db()
    doc = await db.connect_accounts.find_one({"user_id": _user_id(user)})
    if not doc:
        raise HTTPException(status_code=404, detail="No Stripe Connect account on file.")
    # Live-refresh before issuing the dashboard link.
    fresh = await _refresh_account_status(db, doc)
    if not _project_account(fresh)["ready_for_payout"]:
        raise HTTPException(status_code=409,
                            detail="Finish onboarding before opening the Stripe dashboard.")
    try:
        link = stripe.Account.create_login_link(fresh["stripe_account_id"])
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        raise HTTPException(status_code=502, detail=str(e))
    return {"url": link.url}


@router.post("/stripe-connect/refresh-status")
async def refresh_status(user=Depends(get_current_user())):
    """Pull-fresh from Stripe — used by the FE after onboarding redirects."""
    db = get_db()
    doc = await db.connect_accounts.find_one({"user_id": _user_id(user)})
    if not doc:
        return {"account": None, "ready_for_payout": False}
    fresh = await _refresh_account_status(db, doc)
    return {"account": _project_account(fresh), "ready_for_payout": _project_account(fresh)["ready_for_payout"]}


# ── Helpers consumed by routes.bounties ────────────────────────────────────
async def get_account_for_user(db, user_id: str) -> Optional[dict]:
    return await db.connect_accounts.find_one({"user_id": str(user_id)})


def is_ready_for_payout(account_doc: Optional[dict]) -> bool:
    if not account_doc:
        return False
    return bool(
        account_doc.get("charges_enabled")
        and account_doc.get("payouts_enabled")
        and account_doc.get("details_submitted")
    )


def create_transfer(amount_usd: float, destination_account: str,
                    source_charge: Optional[str] = None,
                    transfer_group: Optional[str] = None,
                    metadata: Optional[dict] = None) -> "stripe.Transfer":
    """Wraps stripe.Transfer.create. `amount_usd` is dollars (float); we convert
    to integer cents here. `source_transaction` (when provided) pins the transfer
    to a specific PaymentIntent charge — required for Separate Charges & Transfers."""
    kwargs = {
        "amount": int(round(float(amount_usd) * 100)),
        "currency": "usd",
        "destination": destination_account,
        "metadata": metadata or {},
    }
    if source_charge:
        kwargs["source_transaction"] = source_charge
    if transfer_group:
        kwargs["transfer_group"] = transfer_group
    return stripe.Transfer.create(**kwargs)


def refund_charge(charge_id: str, reason: str = "requested_by_customer",
                  metadata: Optional[dict] = None) -> "stripe.Refund":
    return stripe.Refund.create(
        charge=charge_id,
        reason=reason,
        metadata=metadata or {},
    )


__all__ = [
    "router",
    "get_account_for_user",
    "is_ready_for_payout",
    "create_transfer",
    "refund_charge",
]
