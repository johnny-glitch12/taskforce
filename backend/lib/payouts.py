"""
payouts — Creator earnings + payout-preference logic.

Two payout paths:
  1. CREDITS (default, 30% platform bonus) — locks earnings into the credit
     ecosystem. Creator gets `topup_credits` they can spend on builds/runs/etc.
     The bonus is funded by the platform: minting `N` credits costs us nothing
     in DB terms but represents `N × $0.01` of future LLM-call entitlement that
     we now owe. At our typical 60% gross margin this stays profitable.
  2. CASH — Stripe Connect payout at face value. Standard 90/10 split applies
     upstream (we deduct platform fee before this function runs).

Why default to credits: every credit kept in-platform compounds engagement.
A creator who cashes out leaves; one who reinvests keeps building.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("payouts")

# Tunables (also exposed via /api/settings for the FE so copy stays in sync)
CREDIT_BONUS_RATE: float = 0.30       # 30% credit bonus for picking credits
CREDIT_VALUE_USD:  float = 0.01       # 1 credit == $0.01
MIN_CASH_PAYOUT:   float = 10.00      # USD threshold for cash withdrawal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def process_creator_earning(
    db,
    *,
    creator: dict,
    amount_usd: float,
    source: str,                        # "marketplace_sale" | "bounty_win"
    ref: str,
    payout_preference: Optional[str] = None,
) -> dict:
    """Apply a creator's earning according to their payout preference.

    Returns one of three shapes:
      • {payout_type: "credits", base_credits, bonus_credits, total_credits, balance}
      • {payout_type: "cash",    amount_usd, stripe_transfer_id?}
      • {error: "MINIMUM_NOT_MET", message, suggested_credits}  (cash < $10)
    """
    pref = (payout_preference or creator.get("payout_preference") or "credits").lower()
    if pref not in ("credits", "cash"):
        pref = "credits"

    creator_id = creator.get("id") or creator.get("_id")

    if pref == "credits":
        base_credits  = int(round(amount_usd / CREDIT_VALUE_USD))
        bonus_credits = int(round(base_credits * CREDIT_BONUS_RATE))
        total_credits = base_credits + bonus_credits

        # Add to topup pool (never expires).
        updated = await db.users.find_one_and_update(
            {"id": creator_id},
            {"$inc": {"topup_credits": total_credits,
                      "credits_earned_total": total_credits,
                      "bonus_credits_earned_total": bonus_credits}},
            return_document=True,
        )
        balance = (updated or {}).get("topup_credits", total_credits)

        await db.credit_transactions.insert_one({
            "id": _txn_id(creator_id, source, ref),
            "user_id": creator_id,
            "action": "creator_earning_credits",
            "amount": total_credits,
            "metadata": {
                "source": source,
                "usd_value": amount_usd,
                "base_credits": base_credits,
                "bonus_credits": bonus_credits,
                "bonus_rate": CREDIT_BONUS_RATE,
                "payout_type": "credits",
                "ref": ref,
            },
            "sub_remaining":   (updated or {}).get("subscription_credits", 0),
            "topup_remaining": balance,
            "created_at": _now_iso(),
        })
        logger.info(f"[payouts] credits to {creator_id}: {total_credits} ({bonus_credits} bonus)")
        return {
            "payout_type": "credits",
            "base_credits": base_credits,
            "bonus_credits": bonus_credits,
            "total_credits": total_credits,
            "balance": balance,
            "message": f"Earned {total_credits} credits ({bonus_credits} bonus!)",
        }

    # Cash path
    if amount_usd < MIN_CASH_PAYOUT:
        # Sweeten the rejection: surface what they'd get with credits instead.
        base = int(round(amount_usd / CREDIT_VALUE_USD))
        bonus = int(round(base * CREDIT_BONUS_RATE))
        return {
            "error": "MINIMUM_NOT_MET",
            "min_usd": MIN_CASH_PAYOUT,
            "amount_usd": amount_usd,
            "suggested_credits": base + bonus,
            "message": (
                f"Minimum cash payout is ${MIN_CASH_PAYOUT:.2f}. You have "
                f"${amount_usd:.2f}. Switch to credits to get "
                f"{base + bonus} ({bonus} bonus) — they never expire."
            ),
        }

    # Real cash payout (Stripe Connect) is handled by the calling endpoint
    # because it owns the Connect account + transfer ID lifecycle. We just
    # log the ledger entry.
    await db.credit_transactions.insert_one({
        "id": _txn_id(creator_id, source, ref),
        "user_id": creator_id,
        "action": "creator_earning_cash",
        "amount": 0,
        "metadata": {
            "source": source, "usd_value": amount_usd,
            "payout_type": "cash", "ref": ref,
        },
        "created_at": _now_iso(),
    })
    return {
        "payout_type": "cash",
        "amount_usd": amount_usd,
        "message": f"${amount_usd:.2f} sent to your connected bank account",
    }


def _txn_id(creator_id, source: str, ref: str) -> str:
    import uuid
    return f"earn-{source}-{ref}-{uuid.uuid4().hex[:8]}"


async def earnings_summary(db, user_id: str) -> dict:
    """Aggregate earnings for the Creator Earnings dashboard.

    Returns totals + breakdown by source + lifetime cashback.
    """
    pipeline_credits = [
        {"$match": {"user_id": user_id, "action": "creator_earning_credits"}},
        {"$group": {
            "_id": "$metadata.source",
            "total_credits": {"$sum": "$amount"},
            "bonus_credits": {"$sum": "$metadata.bonus_credits"},
            "total_usd_value": {"$sum": "$metadata.usd_value"},
            "count": {"$sum": 1},
        }},
    ]
    pipeline_cash = [
        {"$match": {"user_id": user_id, "action": "creator_earning_cash"}},
        {"$group": {
            "_id": "$metadata.source",
            "total_usd": {"$sum": "$metadata.usd_value"},
            "count": {"$sum": 1},
        }},
    ]
    pipeline_cashback = [
        {"$match": {"user_id": user_id, "action": "cashback_reward"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"},
                    "count": {"$sum": 1}}},
    ]

    credits_rows = await db.credit_transactions.aggregate(pipeline_credits).to_list(20)
    cash_rows    = await db.credit_transactions.aggregate(pipeline_cash).to_list(20)
    cb_rows      = await db.credit_transactions.aggregate(pipeline_cashback).to_list(1)

    def _by_source(rows, key):
        out = {}
        for r in rows:
            out[(r.get("_id") or "unknown")] = r
        return out

    by_credits = _by_source(credits_rows, "credits")
    by_cash    = _by_source(cash_rows, "cash")

    total_credits = sum(r.get("total_credits", 0) for r in credits_rows)
    total_bonus   = sum(r.get("bonus_credits", 0) for r in credits_rows)
    total_cash    = sum(r.get("total_usd", 0.0) for r in cash_rows)
    total_usd_value_credits = sum(r.get("total_usd_value", 0.0) for r in credits_rows)
    total_lifetime_usd = total_cash + total_usd_value_credits
    cashback_total = (cb_rows[0]["total"] if cb_rows else 0)
    cashback_count = (cb_rows[0]["count"] if cb_rows else 0)

    return {
        "total_earned_usd": round(total_lifetime_usd, 2),
        "credits": {
            "total_credits":    total_credits,
            "bonus_credits":    total_bonus,
            "usd_equivalent":   round(total_usd_value_credits, 2),
            "marketplace_sales":     by_credits.get("marketplace_sale", {}).get("total_credits", 0),
            "bounty_wins":           by_credits.get("bounty_win",       {}).get("total_credits", 0),
            "marketplace_count":     by_credits.get("marketplace_sale", {}).get("count", 0),
            "bounty_count":          by_credits.get("bounty_win",       {}).get("count", 0),
        },
        "cash": {
            "total_usd":            round(total_cash, 2),
            "marketplace_sales":    round(by_cash.get("marketplace_sale", {}).get("total_usd", 0.0), 2),
            "bounty_wins":          round(by_cash.get("bounty_win",       {}).get("total_usd", 0.0), 2),
            "marketplace_count":    by_cash.get("marketplace_sale", {}).get("count", 0),
            "bounty_count":         by_cash.get("bounty_win",       {}).get("count", 0),
        },
        "cashback": {
            "total_credits": cashback_total,
            "events": cashback_count,
        },
    }


__all__ = [
    "process_creator_earning",
    "earnings_summary",
    "CREDIT_BONUS_RATE",
    "CREDIT_VALUE_USD",
    "MIN_CASH_PAYOUT",
]
