"""
Exchange Listings Routes — Task Force AI

Users publish their workflows to The Exchange as agent listings with:
- video demo (mp4/webm/mov, max 50MB)
- screenshot photos (jpg/png/webp, max 5 photos × 10MB)
- description (rich text/markdown)
- pricing (rent $/run + buy $ flat)
- category + tags

Endpoints:
    POST   /api/exchange/listings                  publish a workflow → listing
    GET    /api/exchange/listings                  paginated public catalog
    GET    /api/exchange/listings/{id}             single
    PUT    /api/exchange/listings/{id}             update own listing
    DELETE /api/exchange/listings/{id}             delist
    POST   /api/exchange/listings/{id}/upload      multipart video/photo upload
"""
import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

UPLOAD_ROOT = Path(__file__).parent.parent / "uploads" / "exchange"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_VIDEO_MB = 50
MAX_PHOTO_MB = 10
MAX_PHOTOS = 5
ALLOWED_VIDEO_MIME = {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska"}
ALLOWED_PHOTO_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


async def _enforce_publish_quota(db, user, listing_id: str) -> None:
    """Enforce the creator's hosting-plan cap when a listing transitions to
    'published'. Raises 403 (or 402-style hosting upsell) when no plan or cap hit.
    On success, atomically increments the active subscription's agents_used + appends
    the listing_id to agents_published. Idempotent via $addToSet.

    Admin users bypass enforcement (still increments the counter for visibility)."""
    from routes.hosting import can_publish, increment_agents
    creator_id = str(user.get("id", user.get("email")))
    if user.get("role") != "admin":
        check = await can_publish(db, creator_id)
        if not check.get("allowed"):
            if check.get("reason") == "no_subscription":
                raise HTTPException(status_code=402, detail={
                    "error": "NO_HOSTING_PLAN",
                    "message": check.get("message"),
                    "upgrade_url": "/hosting",
                })
            raise HTTPException(status_code=403, detail={
                "error": check.get("reason") or "QUOTA",
                "message": check.get("message"),
                "tier": check.get("tier"),
                "agents_used": check.get("agents_used"),
                "max_agents": check.get("max_agents"),
                "upgrade_url": "/hosting",
            })
    # Bump the counter (admins included — gives the dashboard a count).
    await increment_agents(db, creator_id, listing_id)


async def _release_publish_quota(db, user_id: str, listing_id: str) -> None:
    """Mirror of _enforce_publish_quota for delist / delete. Best-effort —
    failure to decrement should NOT block the user's delete operation."""
    try:
        from routes.hosting import decrement_agents
        await decrement_agents(db, user_id, listing_id)
    except Exception:
        pass


# ── Pydantic models ──
class PublishListingRequest(BaseModel):
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    category: str = Field(min_length=2, max_length=64)
    tags: List[str] = Field(default_factory=list, max_length=10)
    rent_price: float = Field(ge=0, le=10000)
    buy_price: float = Field(ge=0, le=100000)

    @field_validator("tags")
    @classmethod
    def _tag_len(cls, tags: List[str]) -> List[str]:
        cleaned = []
        for t in tags:
            if isinstance(t, str) and 1 <= len(t) <= 30:
                cleaned.append(t.strip().lower())
        return cleaned[:10]


class UpdateListingRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, min_length=10, max_length=4000)
    category: Optional[str] = Field(default=None, min_length=2, max_length=64)
    tags: Optional[List[str]] = Field(default=None, max_length=10)
    rent_price: Optional[float] = Field(default=None, ge=0, le=10000)
    buy_price: Optional[float] = Field(default=None, ge=0, le=100000)
    status: Optional[str] = Field(default=None, pattern="^(draft|published|delisted)$")


# ── Routes ──
class DirectPublishRequest(BaseModel):
    """Direct-from-Exchange publish: user uploads a full bot package without
    needing a saved workflow in The Armory first."""
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    category: str = Field(min_length=2, max_length=64)
    tags: List[str] = Field(default_factory=list, max_length=10)
    rent_price: float = Field(default=0, ge=0, le=10000)
    buy_price: float = Field(default=0, ge=0, le=100000)
    # Marketplace metadata (new in iter37)
    avatar_icon: str = Field(default="Bot", max_length=40)         # lucide-react icon name
    avatar_color: str = Field(default="#22d3ee", max_length=20)    # hex
    avatar_url: Optional[str] = Field(default=None, max_length=500)  # overrides icon if set
    required_integrations: List[str] = Field(default_factory=list, max_length=20)
    trigger_type: str = Field(default="manual", pattern="^(manual|webhook|schedule)$")
    engine: str = Field(default="gemini-flash", pattern="^(gemini-flash|gemini-pro|byok-openai|byok-claude)$")
    # Optional bot payload (files + node graph)
    files: List[dict] = Field(default_factory=list, max_length=20)
    nodes: List[dict] = Field(default_factory=list, max_length=200)
    edges: List[dict] = Field(default_factory=list, max_length=400)
    language: str = Field(default="python", max_length=32)


@router.post("/exchange/listings/direct")
async def direct_publish(req: DirectPublishRequest, user=Depends(get_current_user())):
    """
    Direct publish path — bypasses The Armory.  Creates an underlying bot_project
    + an exchange_listing in a single shot so users can upload a finished bot
    package directly into The Exchange.  Media (video/photo) uploads go through
    the existing /api/exchange/listings/{id}/upload endpoint after this returns.
    """
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    # 1) Create the underlying bot_project so the listing has runnable code.
    project_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    safe_files = []
    for f in req.files[:20]:
        if not isinstance(f, dict):
            continue
        path = (f.get("path") or "").strip()
        if not path or path.startswith("/") or ".." in path:
            continue
        safe_files.append({
            "path": path[:200],
            "language": (f.get("language") or "text")[:32],
            "content": str(f.get("content") or "")[:200_000],
        })

    project = {
        "id": project_id,
        "user_id": user_id,
        "creator_email": user.get("email"),
        "name": req.name,
        "description": req.description,
        "language": req.language,
        "prompt": "direct-publish-from-exchange",
        "files": safe_files,
        "nodes": req.nodes,
        "edges": req.edges,
        "forked_from": None,
        "forked_from_creator": None,
        "commit_history": [{
            "commit_id": uuid.uuid4().hex[:12],
            "message": "Initial upload via direct-publish",
            "author": user.get("email"),
            "files": safe_files,
            "nodes": req.nodes,
            "edges": req.edges,
            "created_at": now,
        }],
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.bot_projects.insert_one(project)

    # 2) Create the listing pointing at the new bot_project.
    listing_id = uuid.uuid4().hex
    listing = {
        "id": listing_id,
        "user_id": user_id,
        "creator_email": user.get("email"),
        "creator_name": user.get("name", user.get("email", "operator").split("@")[0]),
        "source_workflow_id": None,
        "source_project_id": project_id,
        "name": req.name,
        "description": req.description,
        "category": req.category,
        "tags": [t.strip().lower() for t in req.tags if isinstance(t, str) and 1 <= len(t) <= 30][:10],
        "rent_price": float(req.rent_price),
        "buy_price": float(req.buy_price),
        # Marketplace metadata (iter37)
        "avatar_icon": req.avatar_icon,
        "avatar_color": req.avatar_color,
        "avatar_url": req.avatar_url,
        "required_integrations": req.required_integrations[:20],
        "trigger_type": req.trigger_type,
        "engine": req.engine,
        "video_url": None,
        "photo_urls": [],
        "node_count": len(req.nodes),
        "edge_count": len(req.edges),
        "nodes_snapshot": req.nodes,
        "edges_snapshot": req.edges,
        "trust_score": min(95, 60 + len(req.nodes) * 2),
        "deploy_count": 0,
        "rating": 0,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    await db.exchange_listings.insert_one(listing)
    listing.pop("_id", None)
    return {**listing, "nodes_snapshot": None, "edges_snapshot": None, "project_id": project_id}


@router.post("/exchange/listings")
async def publish_listing(req: PublishListingRequest, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    # Verify workflow ownership
    wf = await db.user_workflows.find_one({"id": req.workflow_id, "user_id": user_id}, {"_id": 0})
    if not wf:
        raise HTTPException(status_code=404, detail="Source workflow not found.")
    if not wf.get("nodes"):
        raise HTTPException(status_code=400, detail="Cannot publish an empty workflow.")

    listing_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    # Snapshot the workflow at publish-time (decouples future edits)
    doc = {
        "id": listing_id,
        "user_id": user_id,
        "creator_email": user.get("email"),
        "creator_name": user.get("name", user.get("email", "operator").split("@")[0]),
        "source_workflow_id": req.workflow_id,
        "name": req.name,
        "description": req.description,
        "category": req.category,
        "tags": req.tags,
        "rent_price": req.rent_price,
        "buy_price": req.buy_price,
        "video_url": None,
        "photo_urls": [],
        "node_count": len(wf["nodes"]),
        "edge_count": len(wf.get("edges", [])),
        "nodes_snapshot": wf["nodes"],
        "edges_snapshot": wf.get("edges", []),
        "trust_score": min(95, 60 + len(wf["nodes"]) * 2),
        "deploy_count": 0,
        "rating": 0,
        "status": "draft",  # becomes 'published' after at least description (required) + optional media
        "created_at": now,
        "updated_at": now,
    }
    await db.exchange_listings.insert_one(doc)
    doc.pop("_id", None)
    # Strip heavy snapshot from response
    return {**doc, "nodes_snapshot": None, "edges_snapshot": None}


@router.get("/exchange/listings")
async def list_listings(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
):
    """Public catalog — no auth required."""
    limit = max(1, min(limit, 100))
    skip = max(0, skip)
    db = get_db()
    query: dict = {"status": "published"}
    if category and category != "ALL":
        query["category"] = category
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"tags": {"$in": [search.lower()]}},
        ]

    projection = {"_id": 0, "nodes_snapshot": 0, "edges_snapshot": 0}
    cursor = db.exchange_listings.find(query, projection).sort("created_at", -1).skip(skip).limit(limit)
    listings = await cursor.to_list(limit)
    total = await db.exchange_listings.count_documents(query)
    return {"listings": listings, "total": total, "limit": limit, "skip": skip}


@router.get("/exchange/listings/{listing_id}")
async def get_listing(listing_id: str):
    db = get_db()
    doc = await db.exchange_listings.find_one({"id": listing_id}, {"_id": 0, "nodes_snapshot": 0, "edges_snapshot": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found.")
    return doc


@router.put("/exchange/listings/{listing_id}")
async def update_listing(listing_id: str, req: UpdateListingRequest, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.exchange_listings.find_one({"id": listing_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found.")

    patch = {k: v for k, v in req.model_dump(exclude_unset=True).items() if v is not None}

    # Hosting-quota enforcement: only when status is actually transitioning.
    old_status = doc.get("status")
    new_status = patch.get("status")
    if new_status and new_status != old_status:
        if new_status == "published":
            await _enforce_publish_quota(db, user, listing_id)
        elif old_status == "published":
            # delisted or back to draft → release a slot.
            await _release_publish_quota(db, user_id, listing_id)

    if patch:
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.exchange_listings.update_one({"_id": doc["_id"]}, {"$set": patch})
    updated = await db.exchange_listings.find_one({"id": listing_id}, {"_id": 0, "nodes_snapshot": 0, "edges_snapshot": 0})
    return updated


@router.delete("/exchange/listings/{listing_id}")
async def delete_listing(listing_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.exchange_listings.find_one({"id": listing_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found.")
    # Release the hosting slot BEFORE deleting the row so the listing_id is still in scope.
    if doc.get("status") == "published":
        await _release_publish_quota(db, user_id, listing_id)
    # Delete files
    listing_dir = UPLOAD_ROOT / listing_id
    if listing_dir.exists():
        shutil.rmtree(listing_dir, ignore_errors=True)
    await db.exchange_listings.delete_one({"id": listing_id, "user_id": user_id})
    return {"success": True}


# ── Multipart uploads — video + photos ──
@router.post("/exchange/listings/{listing_id}/upload")
async def upload_media(
    listing_id: str,
    kind: str = Form(...),                      # "video" or "photo"
    file: UploadFile = File(...),
    user=Depends(get_current_user()),
):
    """Upload a video (1 per listing), photo (max 5), or avatar (1 per listing)."""
    if kind not in ("video", "photo", "avatar"):
        raise HTTPException(status_code=400, detail="kind must be 'video', 'photo', or 'avatar'")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    listing = await db.exchange_listings.find_one({"id": listing_id, "user_id": user_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # MIME + size validation
    if kind == "video":
        if file.content_type not in ALLOWED_VIDEO_MIME:
            raise HTTPException(status_code=400, detail=f"Unsupported video MIME. Allowed: {sorted(ALLOWED_VIDEO_MIME)}")
        max_bytes = MAX_VIDEO_MB * 1024 * 1024
    elif kind == "avatar":
        if file.content_type not in ALLOWED_PHOTO_MIME:
            raise HTTPException(status_code=400, detail=f"Unsupported avatar MIME. Allowed: {sorted(ALLOWED_PHOTO_MIME)}")
        max_bytes = 2 * 1024 * 1024  # avatars: 2MB cap, smaller than full photos
    else:
        if file.content_type not in ALLOWED_PHOTO_MIME:
            raise HTTPException(status_code=400, detail=f"Unsupported photo MIME. Allowed: {sorted(ALLOWED_PHOTO_MIME)}")
        max_bytes = MAX_PHOTO_MB * 1024 * 1024
        if len(listing.get("photo_urls", [])) >= MAX_PHOTOS:
            raise HTTPException(status_code=400, detail=f"Max {MAX_PHOTOS} photos per listing.")

    # Save to /app/backend/uploads/exchange/{listing_id}/<uuid>.<ext>
    listing_dir = UPLOAD_ROOT / listing_id
    listing_dir.mkdir(parents=True, exist_ok=True)

    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()[:8]

    file_id = uuid.uuid4().hex[:12]
    out_path = listing_dir / f"{kind}_{file_id}{ext}"

    # Stream-write with size cap
    bytes_written = 0
    with out_path.open("wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                f.close()
                out_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail=f"File exceeds {max_bytes // (1024*1024)}MB limit.")
            f.write(chunk)

    public_url = f"/static/exchange/{listing_id}/{out_path.name}"

    # Update Mongo
    update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if kind == "video":
        # Replace any prior video file
        prior = listing.get("video_url")
        if prior:
            prior_path = UPLOAD_ROOT.parent / "exchange" / prior.replace("/static/exchange/", "")
            try:
                Path(str(prior_path)).unlink(missing_ok=True)
            except Exception:
                pass
        update["video_url"] = public_url
    elif kind == "avatar":
        # Replace any prior avatar file
        prior = listing.get("avatar_url")
        if prior:
            prior_path = UPLOAD_ROOT.parent / "exchange" / prior.replace("/static/exchange/", "")
            try:
                Path(str(prior_path)).unlink(missing_ok=True)
            except Exception:
                pass
        update["avatar_url"] = public_url
    else:
        photos = listing.get("photo_urls", [])
        photos.append(public_url)
        update["photo_urls"] = photos

    # Auto-promote draft → published once at least video OR 1 photo is uploaded
    if listing.get("status") == "draft":
        await _enforce_publish_quota(db, user, listing_id)
        update["status"] = "published"

    await db.exchange_listings.update_one({"_id": listing["_id"]}, {"$set": update})

    return {"success": True, "url": public_url, "kind": kind, "bytes": bytes_written}


@router.delete("/exchange/listings/{listing_id}/media")
async def delete_media(listing_id: str, url: str, user=Depends(get_current_user())):
    """Remove a single uploaded photo or video by its public URL."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    listing = await db.exchange_listings.find_one({"id": listing_id, "user_id": user_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if listing.get("video_url") == url:
        update["video_url"] = None
    elif url in listing.get("photo_urls", []):
        update["photo_urls"] = [u for u in listing["photo_urls"] if u != url]
    else:
        raise HTTPException(status_code=404, detail="Media not found on this listing.")

    # Best-effort delete the file from disk
    if url.startswith("/static/exchange/"):
        path = UPLOAD_ROOT.parent / url.replace("/static/", "")
        try:
            Path(str(path)).unlink(missing_ok=True)
        except Exception:
            pass

    await db.exchange_listings.update_one({"_id": listing["_id"]}, {"$set": update})
    return {"success": True}


@router.get("/exchange/my-listings")
async def my_listings(user=Depends(get_current_user())):
    """Current user's own listings (drafts + published)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.exchange_listings.find(
        {"user_id": user_id},
        {"_id": 0, "nodes_snapshot": 0, "edges_snapshot": 0},
    ).sort("updated_at", -1)
    listings = await cursor.to_list(200)
    return {"listings": listings}


# ── Fork a single listing into the caller's user_workflows ──
@router.post("/exchange/listings/{listing_id}/fork")
async def fork_listing(listing_id: str, user=Depends(get_current_user())):
    """
    Clone ONLY this specific published listing's node graph into the caller's
    runtime user_workflows. Records forked_from lineage for the creator-revenue
    share. Does NOT pull any other catalog items.
    """
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    listing = await db.exchange_listings.find_one({"id": listing_id, "status": "published"})
    if not listing:
        raise HTTPException(status_code=404, detail="Published listing not found.")

    nodes = listing.get("nodes_snapshot") or []
    edges = listing.get("edges_snapshot") or []
    if not nodes:
        raise HTTPException(status_code=400, detail="Listing has no node graph to fork.")

    wf_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": wf_id,
        "user_id": user_id,
        "name": f"{listing['name']} (forked)",
        "nodes": nodes,
        "edges": edges,
        "source_template": None,
        "forked_from_listing": listing_id,
        "forked_from_creator": listing.get("user_id"),
        "created_at": now,
        "updated_at": now,
    }
    await db.user_workflows.insert_one(doc)
    # Bump deploy_count on the listing for the creator dashboard.
    await db.exchange_listings.update_one(
        {"id": listing_id}, {"$inc": {"deploy_count": 1}}
    )
    doc.pop("_id", None)
    return {"success": True, "workflow_id": wf_id, "workflow": doc}
