"""
Reviews & ratings for Exchange listings.

5-star + comment, ONE review per user per listing, owner can reply ONCE.
Reviews bump `aggregate` fields on the listing for fast card-grid sort.

Storage:
    agent_reviews:
        id, listing_id, user_id, user_email, user_name,
        stars (1-5), comment (max 1500), created_at,
        owner_reply: {content (max 1500), created_at} | null

    exchange_listings.aggregates: { reviews_count, reviews_avg } — denormalised
    for marketplace card sort.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("reviews")
router = APIRouter()


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


class CreateReviewRequest(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=1500)


class ReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1500)


async def _refresh_aggregates(db, listing_id: str):
    """Recompute `aggregates.reviews_count` and `reviews_avg` on the listing.
    Hidden (shadow-moderated) reviews are EXCLUDED from the aggregate."""
    cursor = db.agent_reviews.aggregate([
        {"$match": {"listing_id": listing_id, "hidden": {"$ne": True}}},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "avg": {"$avg": "$stars"},
        }},
    ])
    rows = await cursor.to_list(length=1)
    if rows:
        agg = {"reviews_count": int(rows[0]["count"]),
               "reviews_avg": round(float(rows[0]["avg"] or 0), 2)}
    else:
        agg = {"reviews_count": 0, "reviews_avg": 0.0}
    await db.exchange_listings.update_one(
        {"id": listing_id},
        {"$set": {"aggregates.reviews_count": agg["reviews_count"],
                  "aggregates.reviews_avg": agg["reviews_avg"],
                  "updated_at": _now()}},
    )
    return agg


@router.get("/listings/{listing_id}/reviews")
async def list_reviews(
    listing_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0, le=1000),
):
    """Public list — hidden reviews are always excluded.
    Admins should use /listings/{id}/reviews/all for a moderation view."""
    db = get_db()
    listing = await db.exchange_listings.find_one({"id": listing_id}, {"_id": 0, "id": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    base_q = {"listing_id": listing_id, "hidden": {"$ne": True}}
    total = await db.agent_reviews.count_documents(base_q)
    cursor = db.agent_reviews.find(base_q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    agg = await _refresh_aggregates(db, listing_id)
    # Star distribution histogram (1..5) — also excludes hidden.
    hist_cursor = db.agent_reviews.aggregate([
        {"$match": {"listing_id": listing_id, "hidden": {"$ne": True}}},
        {"$group": {"_id": "$stars", "n": {"$sum": 1}}},
    ])
    hist_rows = await hist_cursor.to_list(length=10)
    histogram = {str(i): 0 for i in range(1, 6)}
    for r in hist_rows:
        histogram[str(r["_id"])] = int(r["n"])
    return {"items": items, "total": total, "aggregate": agg, "histogram": histogram}


@router.get("/listings/{listing_id}/reviews/all")
async def list_reviews_admin(
    listing_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0, le=5000),
    user=Depends(get_current_user()),
):
    """Admin-only moderation view — surfaces ALL reviews including hidden."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    db = get_db()
    listing = await db.exchange_listings.find_one({"id": listing_id}, {"_id": 0, "id": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    total = await db.agent_reviews.count_documents({"listing_id": listing_id})
    cursor = db.agent_reviews.find({"listing_id": listing_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total}


class HideRequest(BaseModel):
    hidden: bool = True
    reason: str = Field(default="", max_length=500)


@router.post("/reviews/{review_id}/hide")
async def hide_review(review_id: str, body: HideRequest, user=Depends(get_current_user())):
    """Admin-only — shadow-hide (or un-hide) a review.
    Hidden reviews stay in the DB (audit trail) but are excluded from public
    list + aggregate + histogram. Recomputes the listing's aggregates on toggle."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    db = get_db()
    rv = await db.agent_reviews.find_one({"id": review_id})
    if not rv:
        raise HTTPException(status_code=404, detail="Review not found.")
    await db.agent_reviews.update_one(
        {"id": review_id},
        {"$set": {
            "hidden": bool(body.hidden),
            "hidden_by": _user_id(user) if body.hidden else None,
            "hidden_at": _now() if body.hidden else None,
            "hidden_reason": body.reason.strip() if body.hidden else "",
        }},
    )
    agg = await _refresh_aggregates(db, rv["listing_id"])
    fresh = await db.agent_reviews.find_one({"id": review_id}, {"_id": 0})
    logger.info(f"[reviews] review {review_id} hidden={body.hidden} by {user.get('email')} reason={body.reason!r}")
    return {"success": True, "review": fresh, "aggregate": agg}


@router.post("/listings/{listing_id}/reviews")
async def create_review(listing_id: str, body: CreateReviewRequest,
                        user=Depends(get_current_user())):
    db = get_db()
    user_id = _user_id(user)
    listing = await db.exchange_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.get("user_id") == user_id:
        raise HTTPException(status_code=403, detail="You can't review your own listing.")
    if await db.agent_reviews.find_one({"listing_id": listing_id, "user_id": user_id}):
        raise HTTPException(status_code=409, detail="You've already reviewed this listing.")

    doc = {
        "id": uuid.uuid4().hex,
        "listing_id": listing_id,
        "user_id": user_id,
        "user_email": user.get("email"),
        "user_name": user.get("display_name") or user.get("name") or user.get("email"),
        "stars": int(body.stars),
        "comment": body.comment.strip(),
        "owner_reply": None,
        "created_at": _now(),
    }
    await db.agent_reviews.insert_one(doc)
    await _refresh_aggregates(db, listing_id)
    doc.pop("_id", None)
    return {"success": True, "review": doc}


@router.delete("/reviews/{review_id}")
async def delete_review(review_id: str, user=Depends(get_current_user())):
    """A user can delete their OWN review (or admin can delete anyone's)."""
    db = get_db()
    rv = await db.agent_reviews.find_one({"id": review_id})
    if not rv:
        raise HTTPException(status_code=404, detail="Review not found.")
    if rv["user_id"] != _user_id(user) and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own review.")
    await db.agent_reviews.delete_one({"id": review_id})
    await _refresh_aggregates(db, rv["listing_id"])
    return {"success": True}


@router.post("/reviews/{review_id}/reply")
async def reply_to_review(review_id: str, body: ReplyRequest,
                          user=Depends(get_current_user())):
    """Listing owner posts a one-time reply to a review."""
    db = get_db()
    rv = await db.agent_reviews.find_one({"id": review_id})
    if not rv:
        raise HTTPException(status_code=404, detail="Review not found.")
    listing = await db.exchange_listings.find_one(
        {"id": rv["listing_id"]}, {"_id": 0, "user_id": 1, "creator_email": 1},
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing["user_id"] != _user_id(user):
        raise HTTPException(status_code=403, detail="Only the listing owner can reply.")
    if rv.get("owner_reply"):
        raise HTTPException(status_code=409, detail="You've already replied to this review.")

    reply = {
        "content": body.content.strip(),
        "created_at": _now(),
        "author_name": user.get("display_name") or user.get("name") or user.get("email"),
    }
    await db.agent_reviews.update_one(
        {"id": review_id},
        {"$set": {"owner_reply": reply}},
    )
    fresh = await db.agent_reviews.find_one({"id": review_id}, {"_id": 0})
    return {"success": True, "review": fresh}


@router.get("/listings/{listing_id}/reviews/my-review")
async def my_review(listing_id: str, user=Depends(get_current_user())):
    """For the FE to know whether the current user has already reviewed."""
    db = get_db()
    rv = await db.agent_reviews.find_one(
        {"listing_id": listing_id, "user_id": _user_id(user)}, {"_id": 0},
    )
    return {"review": rv}


__all__ = ["router"]
