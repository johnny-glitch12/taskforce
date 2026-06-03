"""
admin_seeds — one-shot demo data seeders for empty environments.

P3 task — gives /marketplace + /listing/:id walkthrough content out of the box.
Admin-only. Idempotent (skips listings whose id is already present).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger("admin_seeds")
router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(user):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")


# ── Demo listings catalog (2 realistic walkthrough agents) ──────────────────
DEMO_LISTINGS = [
    {
        "_seed_id": "demo-listing-customer-support-v1",
        "name": "Triage-3 · Email Support Pilot",
        "description": (
            "A customer-support pilot that triages inbound emails. "
            "Classifies the message into one of 4 lanes (billing, technical, sales, other), "
            "drafts a reply in the brand voice, and escalates angry messages to a designated "
            "Slack channel. Plug in your IMAP/SMTP credentials in the Vault and run it on a "
            "schedule.\n\n"
            "**What you get**\n"
            "- 4 nodes: Email Trigger → LLM Classifier → LLM Draft Reply → Slack Send\n"
            "- Configurable confidence threshold (default 0.7) for escalation\n"
            "- Sample fixtures + a one-click Test Run from the Armory\n\n"
            "**Best for**\n"
            "Small teams getting >50 support emails a day with predictable categories. "
            "Not a replacement for a human agent — it triages and drafts, you review and send."
        ),
        "category": "customer_support",
        "tags": ["email", "support", "slack", "triage"],
        "rent_price": 29.0,
        "buy_price": 199.0,
        "trust_score": 92,
        "deploy_count": 47,
        "rating": 4.6,
        "node_count": 4,
        "edge_count": 3,
        "avatar_color": "#22d3ee",
        "nodes_snapshot": [
            {"id": "n1", "type": "email_trigger", "label": "Inbox", "position": {"x": 40, "y": 40}},
            {"id": "n2", "type": "llm",           "label": "Classify",  "position": {"x": 180, "y": 40}},
            {"id": "n3", "type": "llm",           "label": "Draft Reply", "position": {"x": 320, "y": 40}},
            {"id": "n4", "type": "slack",         "label": "Escalate",   "position": {"x": 180, "y": 130}},
        ],
        "edges_snapshot": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n2", "target": "n4"},
        ],
    },
    {
        "_seed_id": "demo-listing-lead-qualifier-v1",
        "name": "FastQual · Inbound Lead Qualifier",
        "description": (
            "Scores inbound leads from Typeform, HubSpot forms, or webhooks on a 1-10 scale "
            "using GPT, posts the score back as a HubSpot contact property, and pushes "
            "qualified leads (score ≥ 7) into a dedicated Slack channel for the sales team.\n\n"
            "**What you get**\n"
            "- 5 nodes: Webhook → Enrich (LLM) → Score (LLM) → HubSpot Update → Slack Notify\n"
            "- Configurable scoring rubric and qualification threshold\n"
            "- Idempotent via lead_id hash — safe to re-run on same data\n\n"
            "**Best for**\n"
            "B2B SaaS sales teams getting 100+ inbound leads/week. Cuts time-to-first-touch "
            "by 80% on qualified leads."
        ),
        "category": "sales",
        "tags": ["lead-gen", "hubspot", "scoring", "slack", "typeform"],
        "rent_price": 49.0,
        "buy_price": 349.0,
        "trust_score": 89,
        "deploy_count": 23,
        "rating": 4.4,
        "node_count": 5,
        "edge_count": 4,
        "avatar_color": "#a855f7",
        "nodes_snapshot": [
            {"id": "n1", "type": "webhook", "label": "Webhook",      "position": {"x": 40,  "y": 60}},
            {"id": "n2", "type": "llm",     "label": "Enrich",       "position": {"x": 180, "y": 60}},
            {"id": "n3", "type": "llm",     "label": "Score",        "position": {"x": 320, "y": 60}},
            {"id": "n4", "type": "hubspot", "label": "Update Lead",  "position": {"x": 460, "y": 60}},
            {"id": "n5", "type": "slack",   "label": "Notify Sales", "position": {"x": 460, "y": 150}},
        ],
        "edges_snapshot": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n3", "target": "n5"},
        ],
    },
]


@router.post("/admin/seed-demo-listings")
async def seed_demo_listings(user=Depends(get_current_user())):
    """Inserts the demo Exchange listings if not already present. Idempotent.
    Returns counts of {inserted, skipped, total} so the caller can show a toast."""
    _require_admin(user)
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    inserted = 0
    skipped = 0
    for tpl in DEMO_LISTINGS:
        seed_id = tpl["_seed_id"]
        existing = await db.exchange_listings.find_one({"_seed_id": seed_id}, {"id": 1})
        if existing:
            skipped += 1
            continue
        listing_id = uuid.uuid4().hex
        now = _now()
        doc = {
            "id": listing_id,
            "_seed_id": seed_id,
            "user_id": user_id,                  # owned by the admin who triggered the seed
            "creator_email": user.get("email", "admin@nova.ai"),
            "creator_name": "Task Force AI · Official",
            "source_workflow_id": None,
            "name": tpl["name"],
            "description": tpl["description"],
            "category": tpl["category"],
            "tags": tpl["tags"],
            "rent_price": tpl["rent_price"],
            "buy_price": tpl["buy_price"],
            "video_url": None,
            "photo_urls": [],
            "avatar_url": None,
            "avatar_color": tpl["avatar_color"],
            "node_count": tpl["node_count"],
            "edge_count": tpl["edge_count"],
            "nodes_snapshot": tpl["nodes_snapshot"],
            "edges_snapshot": tpl["edges_snapshot"],
            "trust_score": tpl["trust_score"],
            "deploy_count": tpl["deploy_count"],
            "rating": tpl["rating"],
            "status": "published",
            "is_demo": True,
            "aggregates": {"reviews_count": 0, "reviews_avg": 0.0},
            "created_at": now,
            "updated_at": now,
        }
        await db.exchange_listings.insert_one(doc)
        inserted += 1
        logger.info(f"[admin_seeds] inserted demo listing {tpl['name']} ({listing_id})")
    return {
        "success": True,
        "inserted": inserted,
        "skipped": skipped,
        "total": len(DEMO_LISTINGS),
    }


@router.delete("/admin/seed-demo-listings")
async def unseed_demo_listings(user=Depends(get_current_user())):
    """Removes all demo listings (and their reviews). Useful for testing."""
    _require_admin(user)
    db = get_db()
    cursor = db.exchange_listings.find({"is_demo": True}, {"id": 1, "_id": 0})
    ids = [d["id"] async for d in cursor]
    if not ids:
        return {"success": True, "removed": 0}
    r1 = await db.exchange_listings.delete_many({"id": {"$in": ids}})
    r2 = await db.agent_reviews.delete_many({"listing_id": {"$in": ids}})
    return {
        "success": True,
        "removed": r1.deleted_count,
        "reviews_removed": r2.deleted_count,
    }


__all__ = ["router"]
