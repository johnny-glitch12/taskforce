"""
Creator earnings aggregation — surfaces USD + credit revenue history per creator.

Sources:
    - creator_revenue_ledger     (existing — 80/20 Stripe payouts on Exchange deploys)
    - credit_transactions        (bounty_award, bounty_refund, etc. — pool='topup')
    - bounties                   (cash bounties awarded, won by this creator)
    - deployment_runs            (run counts per their listings)

Returns rolled-up totals + recent activity. Used by /pages/CreatorEarnings.jsx.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, Response

logger = logging.getLogger("creator_earnings")
router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _user_id(u: dict) -> str:
    return str(u.get("id", u.get("email")))


@router.get("/creator/earnings/summary")
async def earnings_summary(days: int = Query(default=30, ge=1, le=365),
                           user=Depends(get_current_user())):
    db = get_db()
    user_id = _user_id(user)
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # ── 1. Stripe USD from Exchange listings (80% take-home on rent/buy).
    stripe_pipeline = [
        {"$match": {"creator_user_id": user_id, "created_at": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": None,
            "total_usd": {"$sum": "$creator_amount"},
            "tx_count": {"$sum": 1},
        }},
    ]
    stripe = await db.creator_revenue_ledger.aggregate(stripe_pipeline).to_list(length=1)
    stripe_total = float((stripe[0] if stripe else {}).get("total_usd") or 0.0)
    stripe_count = int((stripe[0] if stripe else {}).get("tx_count") or 0)

    # ── 2. Cash bounty wins (USD paid via Stripe Transfer).
    cash_bounty_pipeline = [
        {"$match": {
            "winner_id": user_id,
            "reward_type": "cash",
            "status": "awarded",
            "awarded_at": {"$gte": cutoff_iso},
        }},
        {"$group": {
            "_id": None,
            "total_usd": {"$sum": "$reward_amount"},
            "wins": {"$sum": 1},
        }},
    ]
    cash_bounty = await db.bounties.aggregate(cash_bounty_pipeline).to_list(length=1)
    cash_bounty_total = float((cash_bounty[0] if cash_bounty else {}).get("total_usd") or 0.0)
    cash_bounty_wins = int((cash_bounty[0] if cash_bounty else {}).get("wins") or 0)

    # ── 3. Credit bounty wins.
    credit_bounty_pipeline = [
        {"$match": {
            "winner_id": user_id,
            "reward_type": {"$ne": "cash"},
            "status": "awarded",
            "awarded_at": {"$gte": cutoff_iso},
        }},
        {"$group": {
            "_id": None,
            "total_credits": {"$sum": "$reward_amount"},
            "wins": {"$sum": 1},
        }},
    ]
    credit_bounty = await db.bounties.aggregate(credit_bounty_pipeline).to_list(length=1)
    credit_bounty_total = int((credit_bounty[0] if credit_bounty else {}).get("total_credits") or 0)
    credit_bounty_wins = int((credit_bounty[0] if credit_bounty else {}).get("wins") or 0)

    # ── 4. Listing run counts (how many times this user's listings have been executed).
    listing_ids = [
        doc["id"] async for doc in db.exchange_listings.find(
            {"user_id": user_id}, {"id": 1, "_id": 0},
        )
    ]
    deploy_runs = 0
    if listing_ids:
        deploy_runs = await db.deployment_runs.count_documents(
            {"listing_id": {"$in": listing_ids}, "started_at": {"$gte": cutoff_iso}},
        )

    # ── 5. Lifetime totals (no cutoff).
    lifetime_stripe = await db.creator_revenue_ledger.aggregate([
        {"$match": {"creator_user_id": user_id}},
        {"$group": {"_id": None, "total_usd": {"$sum": "$creator_amount"}}},
    ]).to_list(length=1)
    lifetime_stripe_usd = float((lifetime_stripe[0] if lifetime_stripe else {}).get("total_usd") or 0.0)
    lifetime_cash = await db.bounties.aggregate([
        {"$match": {"winner_id": user_id, "reward_type": "cash", "status": "awarded"}},
        {"$group": {"_id": None, "total_usd": {"$sum": "$reward_amount"}}},
    ]).to_list(length=1)
    lifetime_cash_usd = float((lifetime_cash[0] if lifetime_cash else {}).get("total_usd") or 0.0)
    lifetime_credit = await db.bounties.aggregate([
        {"$match": {
            "winner_id": user_id, "reward_type": {"$ne": "cash"}, "status": "awarded",
        }},
        {"$group": {"_id": None, "total_credits": {"$sum": "$reward_amount"}}},
    ]).to_list(length=1)
    lifetime_credit_total = int((lifetime_credit[0] if lifetime_credit else {}).get("total_credits") or 0)

    return {
        "window_days": days,
        "window": {
            "usd_total": round(stripe_total + cash_bounty_total, 2),
            "stripe_usd": round(stripe_total, 2),
            "stripe_tx_count": stripe_count,
            "cash_bounty_usd": round(cash_bounty_total, 2),
            "cash_bounty_wins": cash_bounty_wins,
            "credit_bounty_total": credit_bounty_total,
            "credit_bounty_wins": credit_bounty_wins,
            "deploy_runs": deploy_runs,
        },
        "lifetime": {
            "stripe_usd": round(lifetime_stripe_usd, 2),
            "cash_bounty_usd": round(lifetime_cash_usd, 2),
            "usd_total": round(lifetime_stripe_usd + lifetime_cash_usd, 2),
            "credit_bounty_total": lifetime_credit_total,
        },
    }


@router.get("/creator/earnings/ledger")
async def earnings_ledger(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0, le=5000),
    user=Depends(get_current_user()),
):
    """Combined ledger of every USD/credit earning event for this creator,
    newest-first."""
    db = get_db()
    user_id = _user_id(user)

    # Stripe one-shot revenue.
    stripe_rows = await db.creator_revenue_ledger.find(
        {"creator_user_id": user_id}, {"_id": 0},
    ).sort("created_at", -1).to_list(length=200)
    rows = []
    for r in stripe_rows:
        rows.append({
            "id": r.get("id") or r.get("payment_id") or "",
            "kind": "exchange_payout",
            "amount": float(r.get("creator_amount") or 0),
            "currency": "USD",
            "label": f"{r.get('mode', 'rent').title()} payout · {r.get('agent_name') or 'agent'}",
            "ref": r.get("payment_id"),
            "created_at": r.get("created_at"),
        })

    # Bounty wins (cash + credits).
    bounty_rows = await db.bounties.find(
        {"winner_id": user_id, "status": "awarded"}, {"_id": 0},
    ).sort("awarded_at", -1).to_list(length=200)
    for b in bounty_rows:
        is_cash = b.get("reward_type") == "cash"
        rows.append({
            "id": b["id"],
            "kind": "bounty_won" if is_cash else "bounty_won_credits",
            "amount": float(b.get("reward_amount") or 0),
            "currency": "USD" if is_cash else "cr",
            "label": f"Bounty win · {b.get('title', '(untitled)')}",
            "ref": b["id"],
            "created_at": b.get("awarded_at"),
        })

    rows.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    total = len(rows)
    sliced = rows[skip:skip + limit]
    return {"items": sliced, "total": total, "limit": limit, "skip": skip}


@router.get("/creator/earnings/export.csv")
async def export_csv(user=Depends(get_current_user())):
    """Download the full earnings ledger as CSV."""
    rows_resp = await earnings_ledger(limit=200, skip=0, user=user)
    # Pull more (up to 1000) if there are more than 200 — simple paginate.
    all_rows = rows_resp["items"]
    if rows_resp["total"] > 200:
        for skip in range(200, min(rows_resp["total"], 1000), 200):
            more = await earnings_ledger(limit=200, skip=skip, user=user)
            all_rows.extend(more["items"])

    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["created_at", "kind", "label", "amount", "currency", "ref"])
    for r in all_rows:
        w.writerow([
            r.get("created_at", ""),
            r.get("kind", ""),
            r.get("label", ""),
            r.get("amount", 0),
            r.get("currency", ""),
            r.get("ref", ""),
        ])
    csv_text = out.getvalue()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=earnings_{_user_id(user)[:8]}.csv",
        },
    )


__all__ = ["router"]
