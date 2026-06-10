"""
Agent Operations Hub — unified agent surface (Prompt 31, Phase 1).

Aggregates `bot_projects` (canonical agent) + `agent_packages` (external
.tfagent uploads) into a single user-facing concept. Adds pause/resume,
duplicate, cascade delete, settings PATCH, export.

All endpoints under `/api/agents/...`. JWT-scoped — cross-user → 404 via
`ensure_ownership`. Audit events via `lib.memory_audit.log_memory_event`.

NOTE: This module touches NOTHING in the memory phase. The pause-enforcement
hook in `routes/apps.py` is the only edit to an existing endpoint and lives
in that file (not here).
"""
from __future__ import annotations

import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from lib.ownership import ensure_ownership
from lib.memory_audit import log_memory_event
from lib.per_user_rate_limit import user_rate_limit
from lib.agent_normalize import (
    aggregate_runs_24h,
    default_phase1_fields,
    fetch_exchange_status_map,
    normalize_agent,
    sort_key,
)

router = APIRouter()


# ─── DI helpers (avoid circular imports) ──────────────────────────────────
def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id(user: dict) -> str:
    return str(user.get("id") or user.get("email") or "")


def _is_dev_env() -> bool:
    return (os.environ.get("TASKFORCE_ENV") or "").lower() in ("dev", "test", "development")


def _slugify(text: str) -> str:
    """Lowercase a-z 0-9 + hyphens. Used for app_slug derivation."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or uuid.uuid4().hex[:8]


# ─── Schemas ──────────────────────────────────────────────────────────────
class AgentPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    tags: Optional[list] = None
    input_template: Optional[dict] = None
    mini_app_settings: Optional[dict] = None
    agent_settings: Optional[dict] = None


class PauseRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=120)


class DuplicateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)


class DeleteRequest(BaseModel):
    confirm: str = Field(min_length=1)


class SeedRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=20)
    with_runs: bool = False


# ─── Internal: load + ownership-check a bot_project ───────────────────────
async def _load_owned_project(db, agent_id: str, user_id: str) -> dict:
    doc = await db.bot_projects.find_one(
        {"$or": [{"id": agent_id}, {"app_slug": agent_id}]},
        {"_id": 0},
    )
    return ensure_ownership(doc, user_id)


async def _load_package(db, agent_id: str, user_id: str) -> Optional[dict]:
    """For `agent_packages` (external .tfagent). Returns the doc only if owned
    by user_id; returns None if not an external package (signals caller to
    fall back to bot_project path)."""
    doc = await db.agent_packages.find_one({"id": agent_id}, {"_id": 0})
    if not doc:
        return None
    if doc.get("user_id") != user_id:
        # Cross-user — surface as 404 just like ensure_ownership does
        raise HTTPException(status_code=404, detail="Not found")
    return doc


# ═════════════════════════════════════════════════════════════════════════
# GET /api/agents/mine — unified aggregator
# ═════════════════════════════════════════════════════════════════════════
@router.get("/agents/mine")
async def list_my_agents(
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_mine", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)

    # ── Fan-out fetch: bot_projects + agent_packages ─────────────────────
    bot_cursor = db.bot_projects.find(
        {"user_id": uid},
        {"_id": 0, "files": 0, "commit_history": 0, "nodes": 0, "edges": 0, "frontend": 0},
    ).sort("updated_at", -1).limit(200)
    bot_docs = await bot_cursor.to_list(200)

    pkg_cursor = db.agent_packages.find(
        {"user_id": uid},
        {"_id": 0, "files": 0},
    ).sort("updated_at", -1).limit(200)
    pkg_docs = await pkg_cursor.to_list(200)

    # ── Single aggregation for 24h run stats ─────────────────────────────
    bot_ids = [d.get("id") for d in bot_docs if d.get("id")]
    pkg_ids = [d.get("id") for d in pkg_docs if d.get("id")]
    runs_map = await aggregate_runs_24h(db, bot_ids + pkg_ids)

    # ── Exchange status lookup (only for bot_projects — packages aren't listed) ─
    exch_map = await fetch_exchange_status_map(db, bot_ids)

    items = []
    for d in bot_docs:
        items.append(normalize_agent(
            d, kind="bot_project",
            runs_stats=runs_map.get(d.get("id")),
            exchange_status=exch_map.get(d.get("id")),
        ))
    for d in pkg_docs:
        items.append(normalize_agent(
            d, kind="external_package",
            runs_stats=runs_map.get(d.get("id")),
            exchange_status=None,
        ))

    items.sort(key=sort_key)
    return {"agents": items, "count": len(items)}


# ═════════════════════════════════════════════════════════════════════════
# GET /api/agents/stats/overview — top-of-page stats
# ═════════════════════════════════════════════════════════════════════════
@router.get("/agents/stats/overview")
async def stats_overview(
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_stats", 60, 60)),
):
    db = get_db()
    uid = _user_id(user)

    total_bot = await db.bot_projects.count_documents({"user_id": uid})
    total_pkg = await db.agent_packages.count_documents({"user_id": uid})
    active_bot = await db.bot_projects.count_documents(
        {"user_id": uid, "agent_state": "active"},
    )
    active_pkg = await db.agent_packages.count_documents(
        {"user_id": uid, "agent_state": "active"},
    )

    # ── 24h aggregation across all the user's agents ─────────────────────
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    # Pull ids first (cheap projection)
    ids_bot = [d["id"] async for d in db.bot_projects.find(
        {"user_id": uid}, {"_id": 0, "id": 1},
    )]
    ids_pkg = [d["id"] async for d in db.agent_packages.find(
        {"user_id": uid}, {"_id": 0, "id": 1},
    )]
    all_ids = ids_bot + ids_pkg

    runs_today = 0
    credits_used_today = 0
    if all_ids:
        pipeline = [
            {"$match": {"app_id": {"$in": all_ids}, "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": None,
                "runs": {"$sum": 1},
                "credits": {"$sum": {"$ifNull": ["$credits_used", 0]}},
            }},
        ]
        async for row in db.app_runs.aggregate(pipeline):
            runs_today = int(row.get("runs") or 0)
            credits_used_today = int(row.get("credits") or 0)

    return {
        "total_agents": total_bot + total_pkg,
        "active_now": active_bot + active_pkg,
        "runs_today": runs_today,
        "credits_used_today": credits_used_today,
    }


# ═════════════════════════════════════════════════════════════════════════
# GET /api/agents/{id} — unified detail
# ═════════════════════════════════════════════════════════════════════════
@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_get", 60, 60)),
):
    db = get_db()
    uid = _user_id(user)

    proj = await _load_owned_project(db, agent_id, uid)

    # Recent runs (last 5)
    runs_cursor = db.app_runs.find(
        {"app_id": proj["id"]},
        {"_id": 0},
    ).sort("created_at", -1).limit(5)
    recent_runs = await runs_cursor.to_list(5)

    # 24h stats
    runs_map = await aggregate_runs_24h(db, [proj["id"]])
    exch_map = await fetch_exchange_status_map(db, [proj["id"]])
    stats_24h = runs_map.get(proj["id"]) or {"runs": 0, "errors": 0, "credits": 0, "last_run_at": None}
    success_rate = 0
    if stats_24h["runs"] > 0:
        success_rate = int(round(
            100 * (stats_24h["runs"] - stats_24h["errors"]) / stats_24h["runs"]
        ))
    stats_24h["success_rate"] = success_rate

    # Sanitize doc: keep files but trim commit_history to last 5
    sanitized = dict(proj)
    if isinstance(sanitized.get("commit_history"), list):
        sanitized["commit_history"] = sanitized["commit_history"][-5:]

    normalized = normalize_agent(
        proj,
        kind="bot_project",
        runs_stats=stats_24h,
        exchange_status=exch_map.get(proj["id"]),
    )
    return {
        "agent": {**normalized, "files": sanitized.get("files", []),
                  "nodes": sanitized.get("nodes", []),
                  "edges": sanitized.get("edges", []),
                  "commit_history": sanitized.get("commit_history", [])},
        "stats_24h": stats_24h,
        "recent_runs": recent_runs,
    }


# ═════════════════════════════════════════════════════════════════════════
# PATCH /api/agents/{id} — update meta fields only
# ═════════════════════════════════════════════════════════════════════════
@router.patch("/agents/{agent_id}")
async def patch_agent(
    agent_id: str,
    body: AgentPatchRequest,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_patch", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    update: dict = {}
    if body.name is not None:
        update["name"] = body.name[:200]
    if body.description is not None:
        update["description"] = body.description[:4000]
    if body.category is not None:
        update["category"] = body.category[:64]
    if body.tags is not None and isinstance(body.tags, list):
        update["tags"] = body.tags[:32]
    if body.input_template is not None:
        update["input_template"] = body.input_template
    if body.mini_app_settings is not None:
        # Merge over current value
        current = proj.get("mini_app_settings") or {}
        merged = {**current, **body.mini_app_settings}
        update["mini_app_settings"] = merged
    if body.agent_settings is not None:
        current = proj.get("agent_settings") or {}
        # Nested notifications: shallow merge so users can update one knob at a time
        merged = {**current, **body.agent_settings}
        if "notifications" in body.agent_settings and isinstance(body.agent_settings["notifications"], dict):
            merged["notifications"] = {
                **(current.get("notifications") or {}),
                **body.agent_settings["notifications"],
            }
        update["agent_settings"] = merged

    if not update:
        return {"agent": normalize_agent(proj, "bot_project"), "updated": False}

    update["updated_at"] = _now_iso()
    await db.bot_projects.update_one({"id": proj["id"]}, {"$set": update})
    fresh = await db.bot_projects.find_one({"id": proj["id"]}, {"_id": 0})

    await log_memory_event(uid, "agent_settings_updated", {
        "agent_id": proj["id"], "fields": sorted(list(update.keys())),
    }, request=request)

    return {"agent": normalize_agent(fresh, "bot_project"), "updated": True}


# ═════════════════════════════════════════════════════════════════════════
# POST /api/agents/{id}/pause
# ═════════════════════════════════════════════════════════════════════════
@router.post("/agents/{agent_id}/pause")
async def pause_agent(
    agent_id: str,
    body: PauseRequest,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_pause", 20, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    reason = (body.reason or "manual")[:120]
    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {
            "agent_state": "paused",
            "paused_at": _now_iso(),
            "auto_pause_reason": reason,
            "updated_at": _now_iso(),
        }},
    )
    fresh = await db.bot_projects.find_one({"id": proj["id"]}, {"_id": 0})
    await log_memory_event(uid, "agent_paused", {
        "agent_id": proj["id"], "reason": reason,
    }, request=request)
    return {"agent": normalize_agent(fresh, "bot_project")}


# ═════════════════════════════════════════════════════════════════════════
# POST /api/agents/{id}/resume
# ═════════════════════════════════════════════════════════════════════════
@router.post("/agents/{agent_id}/resume")
async def resume_agent(
    agent_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_resume", 20, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {
            "agent_state": "active",
            "paused_at": None,
            "auto_pause_reason": None,
            "consecutive_errors": 0,
            "updated_at": _now_iso(),
        }},
    )
    fresh = await db.bot_projects.find_one({"id": proj["id"]}, {"_id": 0})
    await log_memory_event(uid, "agent_resumed", {
        "agent_id": proj["id"],
    }, request=request)
    return {"agent": normalize_agent(fresh, "bot_project")}


# ═════════════════════════════════════════════════════════════════════════
# POST /api/agents/{id}/duplicate
# ═════════════════════════════════════════════════════════════════════════
@router.post("/agents/{agent_id}/duplicate")
async def duplicate_agent(
    agent_id: str,
    body: DuplicateRequest,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_duplicate", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    new_id = uuid.uuid4().hex
    base_name = (body.name or f"{proj.get('name', 'Agent')} (copy)")[:200]
    new_slug = f"{_slugify(base_name)}-{new_id[:6]}"
    now = _now_iso()

    # Clone — skip app_runs (fresh history), commit_history (fresh), exchange linkage
    new_doc = {
        **proj,
        "id": new_id,
        "name": base_name,
        "app_slug": new_slug,
        "agent_state": "draft",
        "paused_at": None,
        "auto_pause_reason": None,
        "consecutive_errors": 0,
        "commit_history": [],
        "is_public": False,
        "created_at": now,
        "updated_at": now,
    }
    # Drop any stale exchange / publishing markers
    for k in ("source_listing_id", "published_at"):
        new_doc.pop(k, None)

    await db.bot_projects.insert_one(new_doc)
    await log_memory_event(uid, "agent_duplicated", {
        "source_id": proj["id"], "new_id": new_id,
    }, request=request)
    fresh = await db.bot_projects.find_one({"id": new_id}, {"_id": 0})
    return {"agent": normalize_agent(fresh, "bot_project"), "new_id": new_id}


# ═════════════════════════════════════════════════════════════════════════
# DELETE /api/agents/{id} — cascade
# ═════════════════════════════════════════════════════════════════════════
@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    body: DeleteRequest,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_delete", 5, 3600)),
):
    if body.confirm != "DELETE_AGENT":
        raise HTTPException(
            status_code=400,
            detail='Confirmation string mismatch. Body must be {"confirm": "DELETE_AGENT"}.',
        )

    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)
    pid = proj["id"]

    deleted: dict = {}

    # bot_projects (the agent itself)
    res = await db.bot_projects.delete_one({"id": pid, "user_id": uid})
    deleted["bot_projects"] = res.deleted_count

    # app_runs (run history)
    res = await db.app_runs.delete_many({"app_id": pid})
    deleted["app_runs"] = res.deleted_count

    # Future Phase-2/3 collections — best-effort, no-op if missing
    for coll in ("agent_run_logs", "agent_data_files", "agent_env_vars"):
        try:
            res = await db[coll].delete_many({"agent_id": pid})
            if res.deleted_count:
                deleted[coll] = res.deleted_count
        except Exception:  # noqa: BLE001
            pass

    # exchange_listings (link field is `source_project_id` per exchange.py publish flow)
    res = await db.exchange_listings.delete_many({"source_project_id": pid})
    if res.deleted_count:
        deleted["exchange_listings"] = res.deleted_count

    # user_bot_deployments (link field is `source_project_id` or `bot_project_id`)
    res = await db.user_bot_deployments.delete_many({
        "$or": [{"source_project_id": pid}, {"bot_project_id": pid}],
    })
    if res.deleted_count:
        deleted["user_bot_deployments"] = res.deleted_count

    await log_memory_event(uid, "agent_deleted", {
        "agent_id": pid, "deleted_counts": deleted,
    }, request=request)

    return {"ok": True, "agent_id": pid, "deleted_counts": deleted}


# ═════════════════════════════════════════════════════════════════════════
# GET /api/agents/{id}/export — .zip download
# ═════════════════════════════════════════════════════════════════════════
@router.get("/agents/{agent_id}/export")
async def export_agent(
    agent_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agents_export", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    slug = proj.get("app_slug") or _slugify(proj.get("name", "agent")) or proj["id"][:8]
    files = proj.get("files") or []

    manifest = {
        "id": proj["id"],
        "name": proj.get("name"),
        "description": proj.get("description"),
        "category": proj.get("category"),
        "tags": proj.get("tags") or [],
        "agent_state": proj.get("agent_state") or "draft",
        "input_template": proj.get("input_template"),
        "mini_app_settings": proj.get("mini_app_settings"),
        "agent_settings": proj.get("agent_settings"),
        "created_at": proj.get("created_at"),
        "updated_at": proj.get("updated_at"),
        "exported_at": _now_iso(),
        "exported_by": uid,
        "file_count": len(files),
    }
    readme = (
        f"# {proj.get('name') or 'Untitled Agent'}\n\n"
        f"{proj.get('description') or ''}\n\n"
        f"Exported from Task Force AI on {_now_iso()}.\n\n"
        f"This archive contains:\n"
        f"- `manifest.json` — agent metadata + settings snapshot\n"
        f"- `files/` — source files (main.py, App.jsx, etc.)\n\n"
        f"To re-import: drop this `.zip` into the Armory upload surface "
        f"(coming in Phase 2 of the Hub).\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        z.writestr("README.md", readme)
        for f in files:
            path = (f.get("path") or "").lstrip("/")
            if not path or ".." in path:
                continue
            content = f.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            z.writestr(f"files/{path}", content)

    await log_memory_event(uid, "agent_exported", {
        "agent_id": proj["id"], "file_count": len(files),
    }, request=request)

    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.zip"',
            "Cache-Control": "no-store",
        },
    )


# ═════════════════════════════════════════════════════════════════════════
# DEV/TEST seed — TASKFORCE_ENV-gated
# ═════════════════════════════════════════════════════════════════════════
@router.post("/agents/_test_seed")
async def test_seed_agents(
    body: SeedRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    if not _is_dev_env():
        # Mirror the memory phase pattern — 404 when not in dev
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    uid = _user_id(user)
    now = _now_iso()

    # Cycle through states so the aggregator + sort logic is exercised
    states_cycle = ["draft", "active", "active", "paused", "active"]
    inserted = []
    for i in range(body.count):
        aid = uuid.uuid4().hex
        state = states_cycle[i % len(states_cycle)]
        defaults = default_phase1_fields()
        defaults["agent_state"] = state
        if state == "paused":
            defaults["paused_at"] = now
            defaults["auto_pause_reason"] = "manual"
        slug_base = f"seed-agent-{i + 1}-{aid[:6]}"
        doc = {
            "id": aid,
            "user_id": uid,
            "creator_email": user.get("email"),
            "name": f"Seed Agent #{i + 1}",
            "description": f"Phase 1 seed agent #{i + 1} for Hub testing.",
            "category": ["productivity", "sales", "ops", "data"][i % 4],
            "tags": ["seed", "test"],
            "app_slug": slug_base,
            "has_ui": True,
            "is_public": False,
            "files": [
                {"path": "main.py", "language": "python",
                 "content": "def run(input):\n    return {'ok': True, 'echo': input}\n"},
                {"path": "App.jsx", "language": "javascript",
                 "content": "export default function App(){return <div>Seed</div>}\n"},
            ],
            "nodes": [],
            "edges": [],
            "commit_history": [],
            "created_at": now,
            "updated_at": now,
            **defaults,
        }
        await db.bot_projects.insert_one(doc)
        inserted.append(aid)

        if body.with_runs:
            # Insert a handful of synthetic app_runs for the 24h aggregator
            for j in range(4):
                success = (j != 0)  # one failure per agent for the errors_24h check
                await db.app_runs.insert_one({
                    "id": uuid.uuid4().hex,
                    "app_id": aid,
                    "user_id": uid,
                    "caller_id": uid,
                    "input": {"seed_round": j},
                    "output": {"ok": success},
                    "success": success,
                    "error": None if success else "SeedError: synthetic failure",
                    "duration_ms": 12,
                    "credits_used": 1,
                    "created_at": now,
                })

    return {"inserted": inserted, "count": len(inserted), "with_runs": bool(body.with_runs)}
