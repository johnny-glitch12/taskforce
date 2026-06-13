"""
settings — User-level account settings (payout preference, etc.).

Endpoints:
  • GET  /api/settings              — fetch the user's settings + ecosystem constants
  • PUT  /api/settings/payout-preference  — toggle credits vs cash payout
  • GET  /api/earnings              — Creator Earnings dashboard summary
  • GET  /api/cashback/summary      — lifetime cashback earned (no progress bar)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lib.cashback import pending_cashback_for
from lib.payouts import (
    CREDIT_BONUS_RATE, CREDIT_VALUE_USD, MIN_CASH_PAYOUT, earnings_summary,
)

router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


class PayoutPrefRequest(BaseModel):
    preference: str = Field(pattern=r"^(credits|cash)$")


class DeveloperModeRequest(BaseModel):
    enabled: bool


@router.get("/settings")
async def get_settings(user=Depends(get_current_user())):
    """Return the user's account settings + ecosystem constants so the
    Payout-Settings UI can render without hardcoding bonus rates."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    u = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "payout_preference": 1, "cashback_earned_total": 1,
         "credits_earned_total": 1, "bonus_credits_earned_total": 1,
         "developer_mode": 1},
    ) or {}
    return {
        "payout_preference": (u.get("payout_preference") or "credits"),
        "developer_mode": bool(u.get("developer_mode", False)),
        "stats": {
            "credits_earned_total":     int(u.get("credits_earned_total") or 0),
            "bonus_credits_earned":     int(u.get("bonus_credits_earned_total") or 0),
            "cashback_earned_total":    int(u.get("cashback_earned_total") or 0),
        },
        "ecosystem": {
            "credit_bonus_rate":  CREDIT_BONUS_RATE,
            "credit_value_usd":   CREDIT_VALUE_USD,
            "min_cash_payout":    MIN_CASH_PAYOUT,
        },
    }


@router.put("/settings/payout-preference")
async def set_payout_preference(req: PayoutPrefRequest, user=Depends(get_current_user())):
    """Switch between 'credits' (default, 30% bonus) and 'cash' (Stripe Connect)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    if req.preference not in ("credits", "cash"):
        raise HTTPException(status_code=400, detail="Must be 'credits' or 'cash'.")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"payout_preference": req.preference}},
    )
    return {"payout_preference": req.preference}


@router.put("/settings/developer-mode")
async def set_developer_mode(req: DeveloperModeRequest, user=Depends(get_current_user())):
    """Toggle developer mode. When OFF (default), the UI hides all raw-code and
    node-graph surfaces so the product stays no-code. When ON, power users get
    the generated source, flow graph, and Workflows editor back."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"developer_mode": bool(req.enabled)}},
    )
    return {"developer_mode": bool(req.enabled)}


@router.get("/earnings")
async def my_earnings(user=Depends(get_current_user())):
    """Aggregated earnings dashboard for creators — sales + bounties + cashback."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    summary = await earnings_summary(db, user_id)
    pref = (user.get("payout_preference") or "credits")
    return {
        "payout_preference": pref,
        **summary,
    }


@router.get("/cashback/summary")
async def cashback_summary(user=Depends(get_current_user())):
    """Lifetime cashback earned (no progress bar — keeps the surprise alive)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    return await pending_cashback_for(db, user_id)
