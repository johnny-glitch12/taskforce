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
    aggregate_runs_for_period,
    compute_uptime_buckets,
    default_phase1_fields,
    fetch_exchange_status_map,
    list_recent_activity,
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
                  "commit_history": sanitized.get("commit_history", []),
                  "schedule": sanitized.get("schedule")},
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
    for coll in ("agent_run_logs",):
        try:
            res = await db[coll].delete_many({"agent_id": pid})
            if res.deleted_count:
                deleted[coll] = res.deleted_count
        except Exception:  # noqa: BLE001
            pass

    # ── Phase 3: data files — delete GridFS bytes + metadata rows ─────────
    try:
        from server import fs_bucket as _fs
        async for df in db.agent_data_files.find(
            {"agent_id": pid}, {"_id": 0, "gridfs_file_id": 1},
        ):
            try:
                await _fs.delete(df["gridfs_file_id"])
            except Exception:  # noqa: BLE001
                pass  # already gone or never persisted
        res = await db.agent_data_files.delete_many({"agent_id": pid})
        if res.deleted_count:
            deleted["agent_data_files"] = res.deleted_count
    except Exception:  # noqa: BLE001
        pass

    # ── Phase 3: env vars (encrypted) ─────────────────────────────────────
    try:
        res = await db.agent_env_vars.delete_many({"agent_id": pid})
        if res.deleted_count:
            deleted["agent_env_vars"] = res.deleted_count
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



# ═════════════════════════════════════════════════════════════════════════
# PHASE 2 — Run history, logs, stats
# ═════════════════════════════════════════════════════════════════════════

# ── Helper: opaque cursor encode/decode (created_at + id tie-breaker) ────
def _encode_cursor(created_at: str, row_id: str) -> str:
    import base64
    raw = f"{created_at}|{row_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: Optional[str]) -> Optional[tuple]:
    if not cursor:
        return None
    try:
        import base64
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        ts, rid = raw.split("|", 1)
        return (ts, rid)
    except Exception:  # noqa: BLE001
        return None


_DATE_RANGE_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30, "all": 24 * 365 * 5}


def _date_range_cutoff_iso(date_range: str) -> Optional[str]:
    """Return ISO cutoff for `date_range`. `all` returns None (no filter)."""
    if date_range == "all":
        return None
    hours = _DATE_RANGE_HOURS.get(date_range, 24 * 7)
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _serialize_run_row(r: dict, *, truncate_io: bool = False) -> dict:
    out = {
        "id": r.get("id"),
        "agent_id": r.get("app_id"),
        "status": "success" if r.get("success") else "error",
        "input": r.get("input"),
        "output": r.get("output"),
        "error": r.get("error"),
        "execution_time_ms": int(r.get("duration_ms") or 0),
        "credits_charged": int(r.get("credits_used") or 0),
        "model_used": r.get("model"),
        "created_at": r.get("created_at"),
    }
    if truncate_io:
        # Listing view: cap large blobs for transport efficiency. Detail
        # endpoint passes truncate_io=False to give the full payload.
        for k in ("input", "output"):
            v = out.get(k)
            if isinstance(v, (dict, list)):
                import json as _json
                serialized = _json.dumps(v, default=str)
                if len(serialized) > 2000:
                    out[k] = serialized[:2000] + "... (truncated)"
            elif isinstance(v, str) and len(v) > 2000:
                out[k] = v[:2000] + "... (truncated)"
    return out


# ─── GET /api/agents/{id}/runs ───────────────────────────────────────────
@router.get("/agents/{agent_id}/runs")
async def list_agent_runs(
    agent_id: str,
    status: str = "all",
    date_range: str = "7d",
    limit: int = 25,
    cursor: Optional[str] = None,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)
    limit = max(1, min(int(limit or 25), 100))

    query: dict = {"app_id": proj["id"]}
    cutoff = _date_range_cutoff_iso(date_range)
    if cutoff:
        query["created_at"] = {"$gte": cutoff}
    if status == "success":
        query["success"] = True
    elif status == "error":
        query["success"] = False

    # Cursor: (created_at, id). Newest-first ordering with tie-breaker on id.
    decoded = _decode_cursor(cursor)
    if decoded:
        ts, rid = decoded
        # Strictly older OR same-ts-but-id-less-than (lexicographic)
        prev = query.get("created_at") or {}
        if isinstance(prev, dict):
            query["$or"] = [
                {**({"created_at": {**prev, "$lt": ts}})},
                {**({"created_at": {**prev, "$eq": ts}}), "id": {"$lt": rid}},
            ]
        else:
            query["$or"] = [{"created_at": {"$lt": ts}},
                            {"created_at": {"$eq": ts}, "id": {"$lt": rid}}]

    rows_cursor = db.app_runs.find(query, {"_id": 0}).sort(
        [("created_at", -1), ("id", -1)]
    ).limit(limit + 1)
    rows = await rows_cursor.to_list(limit + 1)

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.get("created_at", ""), last.get("id", ""))

    return {
        "runs": [_serialize_run_row(r, truncate_io=True) for r in rows],
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


# ─── GET /api/agents/{id}/runs/export ────────────────────────────────────
# IMPORTANT: declare BEFORE the path-param route below so /export wins
@router.get("/agents/{agent_id}/runs/export")
async def export_agent_runs_csv(
    agent_id: str,
    date_range: str = "30d",
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    query: dict = {"app_id": proj["id"]}
    cutoff = _date_range_cutoff_iso(date_range)
    if cutoff:
        query["created_at"] = {"$gte": cutoff}

    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["run_id", "status", "created_at", "execution_time_ms",
                "credits_charged", "input_summary", "output_summary", "error"])

    def _summarize(v) -> str:
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            import json as _json
            try:
                return _json.dumps(v, default=str)[:80]
            except Exception:  # noqa: BLE001
                return str(v)[:80]
        return str(v)[:80]

    rows_cursor = db.app_runs.find(query, {"_id": 0}).sort("created_at", -1).limit(5000)
    count = 0
    async for r in rows_cursor:
        w.writerow([
            r.get("id", ""),
            "success" if r.get("success") else "error",
            r.get("created_at", ""),
            int(r.get("duration_ms") or 0),
            int(r.get("credits_used") or 0),
            _summarize(r.get("input")),
            _summarize(r.get("output")),
            (r.get("error") or "")[:200],
        ])
        count += 1

    slug = proj.get("app_slug") or proj["id"][:8]
    datestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{slug}-runs-{datestamp}.csv"

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Run-Count": str(count),
        },
    )


# ─── GET /api/agents/{id}/runs/{run_id} ──────────────────────────────────
@router.get("/agents/{agent_id}/runs/{run_id}")
async def get_agent_run(
    agent_id: str,
    run_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    row = await db.app_runs.find_one(
        {"id": run_id, "app_id": proj["id"]},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize_run_row(row, truncate_io=False)


# ─── GET /api/agents/{id}/logs ───────────────────────────────────────────
@router.get("/agents/{agent_id}/logs")
async def list_agent_logs(
    agent_id: str,
    level: str = "all",
    limit: int = 100,
    cursor: Optional[str] = None,
    run_id: Optional[str] = None,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)
    limit = max(1, min(int(limit or 100), 500))

    query: dict = {"agent_id": proj["id"]}
    if level in ("info", "warn", "error"):
        query["level"] = level
    if run_id:
        query["run_id"] = run_id

    decoded = _decode_cursor(cursor)
    if decoded:
        ts, rid = decoded
        query["$or"] = [
            {"timestamp": {"$lt": ts}},
            {"timestamp": {"$eq": ts}, "id": {"$lt": rid}},
        ]

    rows_cursor = db.agent_run_logs.find(query, {"_id": 0}).sort(
        [("timestamp", -1), ("id", -1)]
    ).limit(limit + 1)
    rows = await rows_cursor.to_list(limit + 1)

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.get("timestamp", ""), last.get("id", ""))

    return {
        "logs": rows,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


# ─── GET /api/agents/{id}/stats ──────────────────────────────────────────
@router.get("/agents/{agent_id}/stats")
async def agent_stats(
    agent_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)
    pid = proj["id"]

    now = datetime.now(timezone.utc)

    # ── 24h stats block ──
    stats_24h = await aggregate_runs_for_period(
        db, pid, (now - timedelta(hours=24)).isoformat(),
    )

    # ── 7-day daily buckets ──
    stats_7d = []
    for back in range(6, -1, -1):
        day_start = (now - timedelta(days=back)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        pipeline = [
            {"$match": {
                "app_id": pid,
                "created_at": {"$gte": day_start.isoformat(), "$lt": day_end.isoformat()},
            }},
            {"$group": {
                "_id": None,
                "runs": {"$sum": 1},
                "errors": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}},
                "credits": {"$sum": {"$ifNull": ["$credits_used", 0]}},
            }},
        ]
        runs, errors, credits = 0, 0, 0
        async for row in db.app_runs.aggregate(pipeline):
            runs = int(row.get("runs") or 0)
            errors = int(row.get("errors") or 0)
            credits = int(row.get("credits") or 0)
        stats_7d.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "runs": runs,
            "errors": errors,
            "credits": credits,
        })

    # ── Uptime (288 buckets × 5min over 24h) ──
    uptime_24h = await compute_uptime_buckets(
        db, pid, bucket_minutes=5, lookback_hours=24,
    )

    # ── Recent activity (last 10) ──
    recent_activity = await list_recent_activity(db, pid, limit=10)

    return {
        "agent_id": pid,
        "stats_24h": stats_24h,
        "stats_7d": stats_7d,
        "uptime_24h": uptime_24h,
        "recent_activity": recent_activity,
    }


# ═════════════════════════════════════════════════════════════════════════
# DEV/TEST seed for run history — TASKFORCE_ENV-gated
# ═════════════════════════════════════════════════════════════════════════
class SeedRunsRequest(BaseModel):
    agent_id: str
    run_count: int = Field(default=20, ge=1, le=500)
    success_ratio: float = Field(default=0.85, ge=0.0, le=1.0)


@router.post("/agents/_test_seed_runs")
async def test_seed_runs(
    body: SeedRunsRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, body.agent_id, uid)
    pid = proj["id"]

    import random
    runs_inserted: list = []
    logs_inserted = 0
    base = datetime.now(timezone.utc)

    for i in range(body.run_count):
        # Spread across the last 24h so the uptime chart looks realistic
        ts = base - timedelta(minutes=random.randint(0, 24 * 60 - 1))
        ts_iso = ts.isoformat()
        success = random.random() < body.success_ratio
        duration = random.randint(20, 1200)
        rid = uuid.uuid4().hex

        run_doc = {
            "id": rid,
            "app_id": pid,
            "user_id": uid,
            "caller_id": uid,
            "input": {"seed_round": i, "value": f"sample-{i}"},
            "output": {"ok": success, "result": f"output-{i}"},
            "success": success,
            "error": None if success else random.choice([
                "RuntimeError: synthetic seeded failure",
                "ValueError: input not parseable",
                "TimeoutError: upstream slow",
            ]),
            "duration_ms": duration,
            "credits_used": 1,
            "created_at": ts_iso,
        }
        await db.app_runs.insert_one(run_doc)
        runs_inserted.append(rid)

        # Log rows: start + body + end
        log_rows = [
            {"id": uuid.uuid4().hex, "agent_id": pid, "run_id": rid, "user_id": uid,
             "level": "info", "message": f"Run {rid[:8]} started (seeded)",
             "timestamp": ts_iso, "source": "system", "metadata": {}},
            {"id": uuid.uuid4().hex, "agent_id": pid, "run_id": rid, "user_id": uid,
             "level": "info", "message": f"Processing input sample-{i}",
             "timestamp": ts_iso, "source": "stdout", "metadata": {}},
        ]
        if not success:
            log_rows.append({
                "id": uuid.uuid4().hex, "agent_id": pid, "run_id": rid, "user_id": uid,
                "level": "error", "message": run_doc["error"],
                "timestamp": ts_iso, "source": "stderr", "metadata": {},
            })
        log_rows.append({
            "id": uuid.uuid4().hex, "agent_id": pid, "run_id": rid, "user_id": uid,
            "level": "info" if success else "error",
            "message": (f"Run completed in {duration}ms — success"
                        if success else f"Run failed in {duration}ms"),
            "timestamp": ts_iso, "source": "system",
            "metadata": {"duration_ms": duration, "credits_used": 1},
        })
        await db.agent_run_logs.insert_many(log_rows, ordered=False)
        logs_inserted += len(log_rows)

    return {
        "ok": True,
        "agent_id": pid,
        "runs_inserted": len(runs_inserted),
        "logs_inserted": logs_inserted,
        "success_ratio": body.success_ratio,
    }


# ═════════════════════════════════════════════════════════════════════════
# PHASE 3 — Data files (GridFS) + encrypted env vars + input template
# ═════════════════════════════════════════════════════════════════════════
from fastapi import File, UploadFile  # noqa: E402

MAX_DATA_FILE_BYTES = 10 * 1024 * 1024  # 10MB per file
MAX_DATA_FILES_PER_AGENT = 10
PREVIEW_CHAR_CAP = 500
ENV_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _mask_env_value(value: str) -> str:
    """●●●…last4 — preserves the last 4 chars so the user can recognise the
    key in the UI. Mask length floors at 4 bullets even for short values."""
    if not value:
        return ""
    if len(value) <= 4:
        return "●" * len(value)
    visible = value[-4:]
    mask_len = max(len(value) - 4, 4)
    return ("●" * mask_len) + visible


def _get_fs_bucket():
    """Lazy-import so route file can be imported even if server.py isn't
    fully initialised. Returns the AsyncIOMotorGridFSBucket."""
    from server import fs_bucket
    return fs_bucket


# ─── Data files ──────────────────────────────────────────────────────────
@router.get("/agents/{agent_id}/data")
async def list_agent_data_files(
    agent_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    rows = []
    async for df in db.agent_data_files.find(
        {"agent_id": proj["id"], "user_id": uid},
        {"_id": 0, "preview_chars": 0},
    ).sort("uploaded_at", -1):
        if df.get("gridfs_file_id") is not None:
            df["gridfs_file_id"] = str(df["gridfs_file_id"])
        rows.append(df)
    return {"files": rows, "count": len(rows)}


@router.post("/agents/{agent_id}/data")
async def upload_agent_data_file(
    agent_id: str,
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_upload", 5, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    existing = await db.agent_data_files.count_documents({"agent_id": proj["id"]})
    if existing >= MAX_DATA_FILES_PER_AGENT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit reached — max {MAX_DATA_FILES_PER_AGENT} data files per agent.",
        )

    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_DATA_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large — limit is {MAX_DATA_FILE_BYTES // (1024 * 1024)}MB.",
            )
        chunks.append(chunk)
    body_bytes = b"".join(chunks)

    filename = (file.filename or "untitled.dat").split("/")[-1][:200]
    content_type = file.content_type or "application/octet-stream"

    row_count = None
    preview_chars = ""
    try:
        sample = body_bytes[:PREVIEW_CHAR_CAP * 2].decode("utf-8", errors="replace")
        preview_chars = sample[:PREVIEW_CHAR_CAP]
        if filename.lower().endswith(".csv"):
            try:
                full_text = body_bytes.decode("utf-8", errors="replace")
                row_count = max(0, full_text.count("\n") - 1)
            except Exception:  # noqa: BLE001
                pass
        elif filename.lower().endswith(".json"):
            try:
                parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
                row_count = len(parsed) if isinstance(parsed, list) else None
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass

    fs = _get_fs_bucket()
    gridfs_id = await fs.upload_from_stream(
        filename,
        body_bytes,
        metadata={"agent_id": proj["id"], "user_id": uid, "content_type": content_type},
    )

    file_id = uuid.uuid4().hex
    doc = {
        "id": file_id,
        "agent_id": proj["id"],
        "user_id": uid,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": total,
        "gridfs_file_id": gridfs_id,
        "row_count": row_count,
        "preview_chars": preview_chars,
        "uploaded_at": _now_iso(),
    }
    await db.agent_data_files.insert_one(doc)
    await log_memory_event(uid, "data_file_uploaded", {
        "agent_id": proj["id"], "filename": filename, "size_bytes": total,
    }, request=request)

    return {
        "id": file_id,
        "agent_id": proj["id"],
        "filename": filename,
        "content_type": content_type,
        "size_bytes": total,
        "row_count": row_count,
        "gridfs_file_id": str(gridfs_id),
        "uploaded_at": doc["uploaded_at"],
    }


@router.get("/agents/{agent_id}/data/{file_id}")
async def download_agent_data_file(
    agent_id: str,
    file_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    df = await db.agent_data_files.find_one(
        {"id": file_id, "agent_id": proj["id"], "user_id": uid},
    )
    if not df:
        raise HTTPException(status_code=404, detail="Data file not found")

    fs = _get_fs_bucket()
    import io as _io
    buf = _io.BytesIO()
    await fs.download_to_stream(df["gridfs_file_id"], buf)

    return Response(
        content=buf.getvalue(),
        media_type=df.get("content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{df.get("filename", "data.bin")}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/agents/{agent_id}/data/{file_id}/preview")
async def preview_agent_data_file(
    agent_id: str,
    file_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    df = await db.agent_data_files.find_one(
        {"id": file_id, "agent_id": proj["id"], "user_id": uid},
        {"_id": 0},
    )
    if not df:
        raise HTTPException(status_code=404, detail="Data file not found")

    preview = df.get("preview_chars") or ""
    parsed_rows = None
    filename = (df.get("filename") or "").lower()
    if filename.endswith(".csv"):
        try:
            import csv as _csv
            import io as _io2
            reader = _csv.reader(_io2.StringIO(preview))
            rows = []
            for i, row in enumerate(reader):
                if i >= 10:
                    break
                rows.append(row)
            parsed_rows = rows
        except Exception:  # noqa: BLE001
            pass
    elif filename.endswith(".json"):
        try:
            data = json.loads(preview)
            if isinstance(data, list):
                parsed_rows = data[:10]
            else:
                parsed_rows = [data]
        except Exception:  # noqa: BLE001
            pass

    return {
        "filename": df.get("filename"),
        "content_type": df.get("content_type"),
        "size_bytes": df.get("size_bytes"),
        "row_count": df.get("row_count"),
        "preview_chars": preview,
        "parsed_rows": parsed_rows,
    }


@router.delete("/agents/{agent_id}/data/{file_id}")
async def delete_agent_data_file(
    agent_id: str,
    file_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    df = await db.agent_data_files.find_one(
        {"id": file_id, "agent_id": proj["id"], "user_id": uid},
        {"_id": 0, "gridfs_file_id": 1, "filename": 1},
    )
    if not df:
        raise HTTPException(status_code=404, detail="Data file not found")

    fs = _get_fs_bucket()
    try:
        await fs.delete(df["gridfs_file_id"])
    except Exception:  # noqa: BLE001
        pass
    await db.agent_data_files.delete_one({"id": file_id})
    await log_memory_event(uid, "data_file_deleted", {
        "agent_id": proj["id"], "filename": df.get("filename"),
    }, request=request)
    return {"ok": True, "deleted_id": file_id}


@router.patch("/agents/{agent_id}/input-template")
async def patch_agent_input_template(
    agent_id: str,
    body: dict,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 20, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    template = body.get("template") if isinstance(body, dict) else None
    if template is not None and not isinstance(template, (dict, list)):
        raise HTTPException(status_code=400, detail="`template` must be a JSON object or array.")
    try:
        size = len(json.dumps(template or {}, default=str))
        if size > 16 * 1024:
            raise HTTPException(status_code=400, detail="Input template exceeds 16KB serialised size.")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Input template is not JSON-serializable.")

    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {"input_template": template, "updated_at": _now_iso()}},
    )
    await log_memory_event(uid, "input_template_updated", {
        "agent_id": proj["id"], "size_bytes": size,
    }, request=request)
    return {"ok": True, "input_template": template}


# ─── Env vars ────────────────────────────────────────────────────────────
class EnvVarCreate(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=8192)


class EnvVarUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=8192)


@router.get("/agents/{agent_id}/env")
async def list_agent_env_vars(
    agent_id: str,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    rows = []
    async for ev in db.agent_env_vars.find(
        {"agent_id": proj["id"], "user_id": uid},
        {"_id": 0, "value_encrypted": 0},
    ).sort("created_at", -1):
        rows.append(ev)
    return {"env": rows, "count": len(rows)}


@router.post("/agents/{agent_id}/env")
async def create_agent_env_var(
    agent_id: str,
    body: EnvVarCreate,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    key = body.key.strip()
    if not ENV_KEY_PATTERN.match(key):
        raise HTTPException(
            status_code=400,
            detail="Invalid env key format. Must be UPPERCASE letters, digits, underscores; must start with letter or underscore.",
        )

    from lib import memory_crypto as _mem_crypto
    enc = _mem_crypto.encrypt_text(body.value)
    masked = _mask_env_value(body.value)
    now = _now_iso()

    existing = await db.agent_env_vars.find_one(
        {"agent_id": proj["id"], "key": key}, {"_id": 0, "id": 1, "created_at": 1},
    )
    if existing:
        env_id = existing["id"]
        await db.agent_env_vars.update_one(
            {"id": env_id},
            {"$set": {
                "value_encrypted": enc,
                "value_masked": masked,
                "updated_at": now,
            }},
        )
        await log_memory_event(uid, "env_var_updated", {
            "agent_id": proj["id"], "key": key,
        }, request=request)
    else:
        env_id = uuid.uuid4().hex
        await db.agent_env_vars.insert_one({
            "id": env_id,
            "agent_id": proj["id"],
            "user_id": uid,
            "key": key,
            "value_encrypted": enc,
            "value_masked": masked,
            "created_at": now,
            "updated_at": now,
        })
        await log_memory_event(uid, "env_var_created", {
            "agent_id": proj["id"], "key": key,
        }, request=request)

    return {
        "id": env_id,
        "agent_id": proj["id"],
        "key": key,
        "value_masked": masked,
        "created_at": existing.get("created_at") if existing else now,
        "updated_at": now,
    }


@router.patch("/agents/{agent_id}/env/{env_id}")
async def update_agent_env_var(
    agent_id: str,
    env_id: str,
    body: EnvVarUpdate,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    ev = await db.agent_env_vars.find_one(
        {"id": env_id, "agent_id": proj["id"], "user_id": uid},
        {"_id": 0, "key": 1},
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Env var not found")

    from lib import memory_crypto as _mem_crypto
    enc = _mem_crypto.encrypt_text(body.value)
    masked = _mask_env_value(body.value)
    now = _now_iso()
    await db.agent_env_vars.update_one(
        {"id": env_id},
        {"$set": {"value_encrypted": enc, "value_masked": masked, "updated_at": now}},
    )
    await log_memory_event(uid, "env_var_updated", {
        "agent_id": proj["id"], "key": ev["key"],
    }, request=request)
    return {"id": env_id, "key": ev["key"], "value_masked": masked, "updated_at": now}


@router.delete("/agents/{agent_id}/env/{env_id}")
async def delete_agent_env_var(
    agent_id: str,
    env_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    ev = await db.agent_env_vars.find_one(
        {"id": env_id, "agent_id": proj["id"], "user_id": uid},
        {"_id": 0, "key": 1},
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Env var not found")

    await db.agent_env_vars.delete_one({"id": env_id})
    await log_memory_event(uid, "env_var_deleted", {
        "agent_id": proj["id"], "key": ev["key"],
    }, request=request)
    return {"ok": True, "deleted_id": env_id}




# ═════════════════════════════════════════════════════════════════════════
# PHASE 4 — Mini-app public route + mini-app settings + schedule PATCH
# ═════════════════════════════════════════════════════════════════════════

SCHEDULE_PRESETS = {
    "hourly":  60,
    "6h":      60 * 6,
    "daily":   60 * 24,
    "weekly":  60 * 24 * 7,
}


# ─── Public mini-app metadata (no auth wall) ─────────────────────────────
@router.get("/apps/public/{slug}")
async def get_public_mini_app(slug: str, request: Request):
    db = get_db()
    proj = await db.bot_projects.find_one(
        {"$or": [{"app_slug": slug}, {"id": slug}]},
        {
            "_id": 0,
            "id": 1, "name": 1, "description": 1, "category": 1, "tags": 1,
            "input_template": 1, "mini_app_settings": 1, "has_ui": 1,
            "creator_email": 1, "creator_name": 1, "app_slug": 1,
            "price_credits": 1, "agent_state": 1, "user_id": 1,
        },
    )
    if not proj:
        raise HTTPException(status_code=404, detail="Not found")

    settings = proj.get("mini_app_settings") or {}
    visibility = settings.get("visibility") or "public"

    if visibility == "private":
        auth_header = request.headers.get("Authorization", "")
        owner_match = False
        if auth_header.startswith("Bearer "):
            try:
                import jwt as _jwt
                token = auth_header.split(" ", 1)[1]
                payload = _jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
                uid = payload.get("sub") or payload.get("user_id")
                owner_match = bool(uid == proj.get("user_id"))
            except Exception:  # noqa: BLE001
                owner_match = False
        if not owner_match:
            raise HTTPException(status_code=404, detail="Not found")

    creator_handle = None
    if proj.get("creator_email") and "@" in proj["creator_email"]:
        creator_handle = proj["creator_email"].split("@", 1)[0]

    return {
        "slug": proj.get("app_slug") or proj.get("id"),
        "name": proj.get("name") or "Untitled Agent",
        "description": proj.get("description") or "",
        "category": proj.get("category"),
        "tags": proj.get("tags") or [],
        "input_template": proj.get("input_template"),
        "mini_app_settings": {
            "visibility": visibility,
            "cover_url": settings.get("cover_url"),
            "input_mode": settings.get("input_mode") or "json",
            "show_branding": settings.get("show_branding", True),
            "allow_sharing": settings.get("allow_sharing", True),
        },
        "creator": {
            "name": proj.get("creator_name"),
            "handle": creator_handle,
        },
        "credits_per_run": int(proj.get("price_credits") or 1),
        "has_ui": bool(proj.get("has_ui")),
        "agent_state": proj.get("agent_state") or "draft",
    }


# ─── PATCH mini-app settings ─────────────────────────────────────────────
class MiniAppSettingsBody(BaseModel):
    visibility: Optional[str] = Field(default=None, pattern="^(public|private)$")
    cover_url: Optional[str] = Field(default=None, max_length=512)
    input_mode: Optional[str] = Field(default=None, pattern="^(json|form)$")
    show_branding: Optional[bool] = None
    allow_sharing: Optional[bool] = None


@router.patch("/agents/{agent_id}/mini-app")
async def patch_mini_app_settings(
    agent_id: str,
    body: MiniAppSettingsBody,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    current = proj.get("mini_app_settings") or {}
    updates: dict = {**current}
    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        if v is not None:
            updates[k] = v

    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {"mini_app_settings": updates, "updated_at": _now_iso()}},
    )
    await log_memory_event(uid, "mini_app_settings_updated", {
        "agent_id": proj["id"], "fields": sorted(list(payload.keys())),
    }, request=request)
    return {"ok": True, "mini_app_settings": updates}


# ─── PATCH per-agent schedule ────────────────────────────────────────────
class AgentScheduleBody(BaseModel):
    enabled: bool
    preset: Optional[str] = Field(default=None, pattern="^(hourly|6h|daily|weekly|off)$")


@router.patch("/agents/{agent_id}/schedule")
async def patch_agent_schedule(
    agent_id: str,
    body: AgentScheduleBody,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("agent_write", 10, 60)),
):
    db = get_db()
    uid = _user_id(user)
    proj = await _load_owned_project(db, agent_id, uid)

    now_iso = _now_iso()
    existing = proj.get("schedule") or {}

    if not body.enabled or body.preset == "off":
        new_schedule = {
            **existing,
            "enabled": False,
            "updated_at": now_iso,
        }
    else:
        if body.preset not in SCHEDULE_PRESETS:
            raise HTTPException(status_code=422, detail="preset is required when enabled=true")
        interval = SCHEDULE_PRESETS[body.preset]
        next_run = (datetime.now(timezone.utc) + timedelta(minutes=interval)).isoformat()
        new_schedule = {
            "enabled": True,
            "preset": body.preset,
            "interval_minutes": interval,
            "next_run_at": next_run,
            "last_run_at": existing.get("last_run_at"),
            "last_run_id": existing.get("last_run_id"),
            "last_run_success": existing.get("last_run_success"),
            "consecutive_failures": existing.get("consecutive_failures", 0),
            "created_at": existing.get("created_at") or now_iso,
            "updated_at": now_iso,
        }

    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {"schedule": new_schedule, "updated_at": now_iso}},
    )
    await log_memory_event(uid, "agent_schedule_updated", {
        "agent_id": proj["id"], "enabled": new_schedule["enabled"],
        "preset": new_schedule.get("preset"),
    }, request=request)
    return {"ok": True, "schedule": new_schedule}


# ─── Internal: scheduled tick for bot_projects (called by APScheduler) ────
async def tick_scheduled_bot_projects(db) -> int:
    """Phase-4 second-pass scheduler — scans `bot_projects.schedule`.

    Honors agent_state (paused/archived → skip), agent_settings rate caps,
    and a 3-strike circuit breaker. Records a synthetic app_runs row for
    each scheduled tick so the Hub's Run History reflects the activity.
    Returns the count of runs dispatched.
    """
    import logging as _lg
    _log = _lg.getLogger("schedules.bot_projects")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    dispatched = 0

    candidates = await db.bot_projects.find(
        {"schedule.enabled": True, "schedule.next_run_at": {"$lte": now_iso}},
        {"_id": 0},
    ).to_list(length=200)

    for proj in candidates:
        pid = proj.get("id")
        sched = proj.get("schedule") or {}
        state = proj.get("agent_state") or "draft"

        if state in ("paused", "archived"):
            _log.info(f"[sched:bot_projects] {pid[:8]} skipped — state={state}")
            continue

        settings = proj.get("agent_settings") or {}
        max_hour = int(settings.get("max_runs_per_hour") or 0)
        max_day = int(settings.get("max_runs_per_day") or 0)
        if max_hour > 0:
            hr_cutoff = (now - timedelta(hours=1)).isoformat()
            cnt = await db.app_runs.count_documents(
                {"app_id": pid, "created_at": {"$gte": hr_cutoff}}
            )
            if cnt >= max_hour:
                _log.info(f"[sched:bot_projects] {pid[:8]} skipped — hour cap {cnt}/{max_hour}")
                continue
        if max_day > 0:
            day_cutoff = (now - timedelta(hours=24)).isoformat()
            cnt = await db.app_runs.count_documents(
                {"app_id": pid, "created_at": {"$gte": day_cutoff}}
            )
            if cnt >= max_day:
                _log.info(f"[sched:bot_projects] {pid[:8]} skipped — day cap {cnt}/{max_day}")
                continue

        success = False
        run_id = uuid.uuid4().hex
        try:
            input_payload = proj.get("input_template") or {}
            await db.app_runs.insert_one({
                "id": run_id,
                "app_id": pid,
                "user_id": proj.get("user_id"),
                "caller_id": "scheduler",
                "input": input_payload,
                "output": {"_scheduled": True},
                "success": True,
                "error": None,
                "duration_ms": 0,
                "credits_used": 0,
                "created_at": now_iso,
            })
            success = True
            dispatched += 1
        except Exception as e:  # noqa: BLE001
            _log.warning(f"[sched:bot_projects] {pid[:8]} dispatch failed: {e}")

        interval = int(sched.get("interval_minutes") or 60)
        cur_fails = int(sched.get("consecutive_failures") or 0)
        new_fails = 0 if success else cur_fails + 1
        update = {
            "schedule.next_run_at": (now + timedelta(minutes=interval)).isoformat(),
            "schedule.last_run_at": now_iso,
            "schedule.last_run_id": run_id,
            "schedule.last_run_success": success,
            "schedule.consecutive_failures": new_fails,
            "schedule.updated_at": now_iso,
        }
        if new_fails >= 3:
            update["schedule.enabled"] = False
            update["schedule.last_disabled_reason"] = "circuit_breaker"
            _log.warning(f"[sched:bot_projects] {pid[:8]} circuit breaker tripped")
        await db.bot_projects.update_one({"id": pid}, {"$set": update})

    return dispatched


# ─── Dev: trigger the bot_projects scheduler tick manually ───────────────
@router.post("/agents/_test_tick_schedule")
async def test_tick_schedule(
    user=Depends(get_current_user()),
):
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")
    db = get_db()
    count = await tick_scheduled_bot_projects(db)
    return {"ok": True, "dispatched": count}
