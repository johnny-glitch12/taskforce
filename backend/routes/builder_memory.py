"""
Builder Memory CRUD — Task Force AI (Phase 1)

Read / update / delete / export endpoints for the per-user builder memory.
Extraction (the "writer") is Phase 2 — for now memories are populated only
through the dev-gated /_test_seed endpoint or direct DB inserts.

Collections owned by this module:
    builder_memories      \u2014 individual typed memories (encrypted content)
    builder_profiles      \u2014 single profile doc per user (encrypted nested dict)

Cross-user access returns 404 (never 403) so we don't confirm existence of
other users' records. The memory_access_denied audit event is still logged
so admins can spot enumeration attempts.

All decryption happens at READ time. The DB never holds plaintext content.
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from lib.memory_crypto import encrypt_text, decrypt_text, encrypt_dict, decrypt_dict
from lib.ownership import ensure_ownership
from lib.memory_audit import log_memory_event
from lib.per_user_rate_limit import user_rate_limit
from lib.memory_extractor import extract_and_persist
from lib.memory_injector import build_memory_context
from lib.memory_summarizer import update_rolling_summary, get_summary
from lib.agent_changelog import log_change, get_changelog, get_highest_message_num
from lib.file_versions import save_file_version, list_versions, restore_files_to_message
from lib.llm_context import build_chat_context

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Allowed memory types ──
MEMORY_TYPES = {"business_context", "preference", "technical", "feedback", "correction"}
MEMORY_GROUPS = ("business_context", "preference", "technical", "feedback", "correction")
MAX_MEMORIES_RETURNED = 200


# ── DI helpers (avoid circular imports) ──
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


# ── Schemas ──
class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = Field(default=None, max_length=8000)
    type: Optional[str] = None


class SeedMemoryItem(BaseModel):
    type: str
    content: str = Field(min_length=1, max_length=8000)
    source: Optional[str] = "seed"


class SeedRequest(BaseModel):
    memories: List[SeedMemoryItem] = Field(default_factory=list, max_length=50)
    profile: Optional[dict] = None  # arbitrary nested object (business / preferences / integrations)


class TestExtractRequest(BaseModel):
    """Body for the dev-only /_test_extract endpoint.

    `messages` is a chat-slice the extractor would normally see (last 6 turns).
    `mock_llm_response` is what the LLM caller would have returned — we inject
    it directly so tests don't need a real LLM key. `force` bypasses the
    triviality skip so the tester can exercise tiny conversations.
    """
    session_id: str
    messages: List[dict] = Field(default_factory=list, max_length=20)
    mock_llm_response: Optional[dict] = None
    force: bool = False


# ─── Phase 3 test/production request bodies ──────────────────────────────
class TestSummaryRequest(BaseModel):
    session_id: str
    mock_llm_response: Optional[str] = None  # str, not dict — summarizer returns plain text
    force: bool = False


class ChangelogChange(BaseModel):
    file: str
    action: str  # created | modified | deleted | renamed | reverted
    what: str = ""


class TestLogChangeRequest(BaseModel):
    session_id: str
    message_num: int
    changes: List[ChangelogChange]


class TestSaveVersionRequest(BaseModel):
    session_id: str
    filename: str
    old_content: str
    message_num: int


class TestBuildContextRequest(BaseModel):
    session_id: str
    new_message: str = ""


class RevertRequest(BaseModel):
    to_message_num: int


# ── Internal helpers ──
def _decrypt_memory_row(row: dict) -> dict:
    """Return a decrypted, JSON-safe copy of a builder_memories row.
    Strips Mongo _id; keeps id, type, source, created_at, updated_at, active, etc.
    """
    out = {k: v for k, v in row.items() if k != "_id"}
    if "content" in out:
        out["content"] = decrypt_text(out["content"])
    return out


def _empty_profile_stub() -> dict:
    return {
        "business": {},
        "preferences": {},
        "integrations": {"byok_keys": []},
    }


# ──────────────────────────────────────────────────────────────────────
# STATIC / SPECIFIC ROUTES — must come BEFORE /{memory_id} so FastAPI
# doesn't capture words like "profile" / "export" as a memory id.
# ──────────────────────────────────────────────────────────────────────

@router.get("/builder/memory/profile")
async def get_profile(
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("memory_read", 30, 60)),
):
    """Return the decrypted builder_profiles doc for the caller. If the user
    has no profile yet, return an empty stub so the UI can render placeholders
    without a 404 round-trip."""
    db = get_db()
    uid = _user_id(user)
    doc = await db.builder_profiles.find_one({"user_id": uid}, {"_id": 0})
    if not doc:
        return {"profile": _empty_profile_stub(), "exists": False}

    # Decrypt nested string values in business / preferences (NOT integrations.byok_keys
    # — those should be flags only, never raw keys).
    decrypted = {
        "user_id": doc.get("user_id"),
        "business": decrypt_dict(doc.get("business") or {}),
        "preferences": decrypt_dict(doc.get("preferences") or {}),
        "integrations": doc.get("integrations") or {"byok_keys": []},
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    await log_memory_event(uid, "memory_read", {"target": "profile"}, request=request)
    return {"profile": decrypted, "exists": True}


@router.get("/builder/memory/export")
async def export_memory(
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("memory_export", 5, 3600)),
):
    """JSON dump of profile + all active memories (decrypted). Triggers
    Content-Disposition so the browser downloads it as a file."""
    db = get_db()
    uid = _user_id(user)

    profile_doc = await db.builder_profiles.find_one({"user_id": uid}, {"_id": 0})
    profile = _empty_profile_stub() if not profile_doc else {
        "business": decrypt_dict(profile_doc.get("business") or {}),
        "preferences": decrypt_dict(profile_doc.get("preferences") or {}),
        "integrations": profile_doc.get("integrations") or {"byok_keys": []},
    }

    cursor = db.builder_memories.find(
        {"user_id": uid, "active": True}, {"_id": 0}
    ).sort("created_at", -1)
    rows = await cursor.to_list(length=10_000)
    memories = [_decrypt_memory_row(r) for r in rows]

    payload = {
        "exported_at": _now_iso(),
        "user_id": uid,
        "profile": profile,
        "memories": memories,
        "count": len(memories),
    }
    await log_memory_event(uid, "memory_exported", {"count": len(memories)}, request=request)
    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="taskforce-memory-export.json"',
        },
    )


@router.post("/builder/memory/_test_seed")
async def test_seed_memory(
    req: SeedRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    """Dev/test-only: bulk-insert encrypted memories + optionally upsert profile.

    Gated by TASKFORCE_ENV in {dev, test, development}. Returns 404 in any
    other environment so the route doesn't surface in prod-like deployments.
    Phase 2's real extractor will supersede this endpoint.
    """
    if not _is_dev_env():
        # 404 (not 403) so the route looks like it doesn't exist outside dev.
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    uid = _user_id(user)
    now = _now_iso()

    inserted_ids: List[str] = []
    for item in req.memories:
        if item.type not in MEMORY_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid memory type '{item.type}'. Valid: {sorted(MEMORY_TYPES)}",
            )
        mem_id = str(uuid.uuid4())
        await db.builder_memories.insert_one({
            "id": mem_id,
            "user_id": uid,
            "type": item.type,
            "content": encrypt_text(item.content),
            "source": item.source or "seed",
            "active": True,
            "created_at": now,
            "updated_at": now,
        })
        inserted_ids.append(mem_id)

    profile_upserted = False
    if req.profile:
        # Recursively encrypt strings inside business / preferences. integrations
        # is stored as-is (boolean flags + service ids, never raw keys).
        enc_business = encrypt_dict(req.profile.get("business") or {})
        enc_prefs = encrypt_dict(req.profile.get("preferences") or {})
        integrations = req.profile.get("integrations") or {"byok_keys": []}
        # Defensive scrub: drop anything resembling a raw key value.
        if isinstance(integrations, dict):
            integrations = {
                k: v for k, v in integrations.items()
                if k.lower() not in {"api_key", "secret", "password", "token"}
            }
        await db.builder_profiles.update_one(
            {"user_id": uid},
            {
                "$set": {
                    "user_id": uid,
                    "business": enc_business,
                    "preferences": enc_prefs,
                    "integrations": integrations,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        profile_upserted = True

    await log_memory_event(
        uid, "memory_seeded",
        {"count": len(inserted_ids), "profile_upserted": profile_upserted},
        request=request,
    )
    return {
        "ok": True,
        "inserted_count": len(inserted_ids),
        "inserted_ids": inserted_ids,
        "profile_upserted": profile_upserted,
    }


@router.post("/builder/memory/_test_extract")
async def test_extract_memory(
    req: TestExtractRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    """Dev/test-only: run the extraction pipeline with an injected mock LLM
    response. Skips the real LLM call entirely so tests don't need a key.

    Returns the same shape as `extract_and_persist`. The stored memories are
    written to THIS user's `builder_memories` regardless of what session_id
    is passed — session_id only affects the `source` tag on inserted rows.
    """
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    uid = _user_id(user)

    # Build the deterministic mock LLM caller. The extractor's signature is
    # `llm_caller(system_prompt: str, user_message: str) -> str`.
    mock_json = req.mock_llm_response or {"memories": [], "profile_updates": {}}

    async def _mock_caller(*, system_prompt: str, user_message: str) -> str:
        return json.dumps(mock_json)

    result = await extract_and_persist(
        db, uid, req.session_id, req.messages or [],
        llm_caller=_mock_caller,
        force=req.force,
    )
    return result


@router.post("/builder/memory/_test_inject")
async def test_inject_memory(
    request: Request,
    user=Depends(get_current_user()),
):
    """Dev/test-only: build the system-prompt block that WOULD be injected
    into the next vibe chat for this user. No vibe call is made; this is
    purely a preview of the injector's output for the caller's current state.
    """
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    uid = _user_id(user)

    profile_doc = await db.builder_profiles.find_one({"user_id": uid}, {"_id": 0})
    if profile_doc:
        profile = {
            "business": decrypt_dict(profile_doc.get("business") or {}),
            "preferences": decrypt_dict(profile_doc.get("preferences") or {}),
            "integrations": profile_doc.get("integrations") or {"byok_keys": []},
        }
    else:
        profile = None

    # Same query shape as the public GET / list_memory — corrections first.
    correction_rows = await db.builder_memories.find(
        {"user_id": uid, "active": True, "type": "correction"}, {"_id": 0},
    ).sort("created_at", -1).limit(MAX_MEMORIES_RETURNED).to_list(length=MAX_MEMORIES_RETURNED)
    other_rows = await db.builder_memories.find(
        {"user_id": uid, "active": True, "type": {"$ne": "correction"}}, {"_id": 0},
    ).sort("created_at", -1).limit(MAX_MEMORIES_RETURNED).to_list(length=MAX_MEMORIES_RETURNED)

    decrypted: List[dict] = []
    for r in (correction_rows + other_rows):
        decrypted.append({**r, "content": decrypt_text(r.get("content", ""))})

    block = build_memory_context(profile, decrypted)
    return {
        "system_prompt_block": block,
        "memory_count": len(decrypted),
        "profile_present": profile is not None and any([
            profile.get("business"), profile.get("preferences"),
            (profile.get("integrations") or {}).get("byok_keys"),
        ]),
    }


# ──────────────────────────────────────────────────────────────────────
# LIST + CLEAR (on the collection root)
# ──────────────────────────────────────────────────────────────────────

@router.get("/builder/memory")
async def list_memory(
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("memory_read", 30, 60)),
):
    """Return {profile, memories: {<type>: [...], ...}}. Only active rows.
    Corrections are sorted first (highest priority), then everything else
    by created_at desc. Capped at MAX_MEMORIES_RETURNED rows total."""
    db = get_db()
    uid = _user_id(user)

    # Profile
    profile_doc = await db.builder_profiles.find_one({"user_id": uid}, {"_id": 0})
    if profile_doc:
        profile = {
            "business": decrypt_dict(profile_doc.get("business") or {}),
            "preferences": decrypt_dict(profile_doc.get("preferences") or {}),
            "integrations": profile_doc.get("integrations") or {"byok_keys": []},
        }
    else:
        profile = _empty_profile_stub()

    # Memories: corrections first (always include all corrections within the cap),
    # then remaining types by created_at desc.
    grouped: dict[str, List[dict]] = {t: [] for t in MEMORY_GROUPS}

    correction_cursor = db.builder_memories.find(
        {"user_id": uid, "active": True, "type": "correction"}, {"_id": 0},
    ).sort("created_at", -1).limit(MAX_MEMORIES_RETURNED)
    correction_rows = await correction_cursor.to_list(length=MAX_MEMORIES_RETURNED)
    for r in correction_rows:
        grouped["correction"].append(_decrypt_memory_row(r))

    remaining_budget = MAX_MEMORIES_RETURNED - len(correction_rows)
    if remaining_budget > 0:
        other_cursor = db.builder_memories.find(
            {"user_id": uid, "active": True, "type": {"$ne": "correction"}}, {"_id": 0},
        ).sort("created_at", -1).limit(remaining_budget)
        other_rows = await other_cursor.to_list(length=remaining_budget)
        for r in other_rows:
            t = r.get("type")
            if t in grouped:
                grouped[t].append(_decrypt_memory_row(r))

    total = sum(len(v) for v in grouped.values())
    await log_memory_event(uid, "memory_read", {"count": total}, request=request)
    return {
        "profile": profile,
        "memories": grouped,
        "count": total,
        "capped": total >= MAX_MEMORIES_RETURNED,
    }


@router.delete("/builder/memory")
async def clear_all_memory(
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("memory_clear", 1, 3600)),
):
    """Soft-clear: flip active=False on every memory for this user.
    Profile is left intact (it's structured, low-noise data — wipe it via a
    separate explicit reset in a later phase if needed)."""
    db = get_db()
    uid = _user_id(user)
    now = _now_iso()
    res = await db.builder_memories.update_many(
        {"user_id": uid, "active": True},
        {"$set": {"active": False, "deleted_at": now, "updated_at": now}},
    )
    await log_memory_event(uid, "memory_cleared", {"count": res.modified_count}, request=request)
    return {"ok": True, "cleared_count": res.modified_count}


# ──────────────────────────────────────────────────────────────────────
# Single-memory routes  — these come last so dynamic {memory_id} doesn't
# eat any of the static paths above.
# ──────────────────────────────────────────────────────────────────────

@router.patch("/builder/memory/{memory_id}")
async def update_memory(
    memory_id: str,
    body: MemoryUpdateRequest,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("memory_write", 10, 60)),
):
    """Update content and/or type of one memory. 404 on cross-user attempt."""
    db = get_db()
    uid = _user_id(user)

    row = await db.builder_memories.find_one({"id": memory_id}, {"_id": 0})
    try:
        ensure_ownership(row, uid)
    except HTTPException:
        # Distinguish "row exists, wrong owner" for the audit log without
        # leaking it via the HTTP response.
        if row is not None:
            await log_memory_event(
                uid, "memory_access_denied",
                {"memory_id": memory_id, "verb": "PATCH"},
                request=request,
            )
        raise

    update: dict = {"updated_at": _now_iso()}
    if body.content is not None:
        update["content"] = encrypt_text(body.content)
    if body.type is not None:
        if body.type not in MEMORY_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid memory type '{body.type}'. Valid: {sorted(MEMORY_TYPES)}",
            )
        update["type"] = body.type
    if len(update) == 1:  # only updated_at — caller sent an empty patch
        raise HTTPException(status_code=400, detail="Provide at least one of {content, type}.")

    await db.builder_memories.update_one({"id": memory_id, "user_id": uid}, {"$set": update})
    await log_memory_event(
        uid, "memory_updated",
        {"memory_id": memory_id, "fields": [k for k in update.keys() if k != "updated_at"]},
        request=request,
    )

    fresh = await db.builder_memories.find_one({"id": memory_id, "user_id": uid}, {"_id": 0})
    return {"ok": True, "memory": _decrypt_memory_row(fresh) if fresh else None}


@router.delete("/builder/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("memory_write", 10, 60)),
):
    """Soft-delete a single memory. 404 on cross-user attempt."""
    db = get_db()
    uid = _user_id(user)

    row = await db.builder_memories.find_one({"id": memory_id}, {"_id": 0})
    try:
        ensure_ownership(row, uid)
    except HTTPException:
        if row is not None:
            await log_memory_event(
                uid, "memory_access_denied",
                {"memory_id": memory_id, "verb": "DELETE"},
                request=request,
            )
        raise

    now = _now_iso()
    await db.builder_memories.update_one(
        {"id": memory_id, "user_id": uid},
        {"$set": {"active": False, "deleted_at": now, "updated_at": now}},
    )
    await log_memory_event(uid, "memory_deleted", {"memory_id": memory_id}, request=request)
    return {"ok": True, "deleted_id": memory_id}


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3 — Rolling Summary / Changelog / File Versions / Undo+Revert
# ═══════════════════════════════════════════════════════════════════════════
# Helper: confirm the calling user owns the given vibe_session. 404 (not 403)
# on cross-user attempt so we don't confirm existence to enumeration attempts.
async def _own_session_or_404(db, user_id: str, session_id: str) -> dict:
    sess = await db.vibe_sessions.find_one({"id": session_id}, {"_id": 0})
    ensure_ownership(sess, user_id)
    return sess


# ─── Dev/test endpoints ──────────────────────────────────────────────────
@router.post("/builder/memory/_test_summary")
async def test_summary(
    req: TestSummaryRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    """Run the rolling-summary pipeline with either an injected mock LLM
    response (string) or the real LLM (no-op when no key)."""
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")
    db = get_db()
    uid = _user_id(user)

    caller = None
    if req.mock_llm_response is not None:
        mock_text = req.mock_llm_response

        async def _mock(*, system_prompt: str, user_message: str) -> str:
            return mock_text
        caller = _mock

    result = await update_rolling_summary(
        db, uid, req.session_id,
        llm_caller=caller, force=req.force,
    )
    return result


@router.post("/builder/memory/_test_log_change")
async def test_log_change(
    req: TestLogChangeRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    """Directly append a changelog entry (bypasses the vibe_generate hook)."""
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")
    db = get_db()
    uid = _user_id(user)
    changes = [c.model_dump() for c in req.changes]
    entry_id = await log_change(db, uid, req.session_id, req.message_num, changes)
    return {"ok": True, "entry_id": entry_id, "count": len(changes)}


@router.post("/builder/memory/_test_save_version")
async def test_save_version(
    req: TestSaveVersionRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    """Directly snapshot a file_version row (bypasses the vibe_generate hook)."""
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")
    db = get_db()
    uid = _user_id(user)
    version_id = await save_file_version(
        db, uid, req.session_id, req.filename, req.old_content, req.message_num,
    )
    return {"ok": True, "version_id": version_id}


@router.post("/builder/memory/_test_build_context")
async def test_build_context(
    req: TestBuildContextRequest,
    request: Request,
    user=Depends(get_current_user()),
):
    """Return the full context assembler output for this user+session.
    Useful for verifying memory + summary + changelog + recent messages all
    flow into one object before any LLM wiring is done."""
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="Not Found")
    db = get_db()
    uid = _user_id(user)
    ctx = await build_chat_context(db, uid, req.session_id, req.new_message)
    return ctx


# ─── Production endpoints under /api/builder/drafts/{session_id}/... ─────
@router.get("/builder/drafts/{session_id}/changelog")
async def get_draft_changelog(
    session_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("draft_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    await _own_session_or_404(db, uid, session_id)
    entries = await get_changelog(db, uid, session_id)
    return {"session_id": session_id, "entries": entries, "count": len(entries)}


@router.get("/builder/drafts/{session_id}/summary")
async def get_draft_summary(
    session_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("draft_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    await _own_session_or_404(db, uid, session_id)
    doc = await get_summary(db, uid, session_id)
    if not doc:
        return {"summary": None, "message_count": 0, "updated_at": None}
    return doc


@router.get("/builder/drafts/{session_id}/versions")
async def get_draft_versions(
    session_id: str,
    request: Request,
    user=Depends(get_current_user()),
    filename: Optional[str] = None,
    _=Depends(user_rate_limit("draft_read", 30, 60)),
):
    db = get_db()
    uid = _user_id(user)
    await _own_session_or_404(db, uid, session_id)
    versions = await list_versions(db, uid, session_id, filename)
    return {"session_id": session_id, "filename": filename, "versions": versions, "count": len(versions)}


@router.post("/builder/drafts/{session_id}/revert")
async def revert_draft(
    session_id: str,
    body: RevertRequest,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("draft_revert", 5, 60)),
):
    """Rewind the bot_project's files[] to the state JUST BEFORE
    `to_message_num`. Files with no history at or before that point are left
    untouched and listed under `no_history`.

    The session's vibe_sessions.messages[] is NOT trimmed — we keep the chat
    transcript intact so the user can see what changed. Only the file state
    is rolled back."""
    db = get_db()
    uid = _user_id(user)
    sess = await _own_session_or_404(db, uid, session_id)

    plan = await restore_files_to_message(db, uid, session_id, body.to_message_num)

    # Apply the plan to bot_projects.files[]. The session may not yet have a
    # project_id (e.g. revert called before any vibe_generate ran) — in that
    # case the plan will be empty and we just record the revert in the log.
    project_id = sess.get("project_id")
    applied_count = 0
    if project_id and plan["restored"]:
        proj = await db.bot_projects.find_one(
            {"id": project_id, "user_id": uid}, {"_id": 0, "files": 1},
        )
        if proj:
            files_by_path = {f.get("path"): f for f in (proj.get("files") or []) if isinstance(f, dict)}
            for entry in plan["restored"]:
                fname = entry["filename"]
                files_by_path[fname] = {"path": fname, "content": entry["content"]}
                applied_count += 1
            await db.bot_projects.update_one(
                {"id": project_id, "user_id": uid},
                {"$set": {"files": list(files_by_path.values()),
                          "updated_at": _now_iso()}},
            )

    # Append a changelog entry so the rewind shows up in /changelog.
    now_msg_num = len((sess.get("messages") or [])) + 1
    await log_change(
        db, uid, session_id, now_msg_num,
        [{
            "file": "<all>",
            "action": "reverted",
            "what": f"Reverted to state at message {body.to_message_num} "
                    f"({applied_count} file(s) restored)",
        }],
    )

    await log_memory_event(
        uid, "revert_applied",
        {"session_id": session_id, "to_message_num": body.to_message_num,
         "applied_count": applied_count,
         "no_history_count": len(plan["no_history"])},
        request=request,
    )

    return {
        "ok": True,
        "to_message_num": body.to_message_num,
        "applied_count": applied_count,
        "restored": [{"filename": e["filename"], "from_version": e["from_version"]}
                     for e in plan["restored"]],
        "no_history": plan["no_history"],
    }


@router.post("/builder/drafts/{session_id}/undo")
async def undo_draft(
    session_id: str,
    request: Request,
    user=Depends(get_current_user()),
    _=Depends(user_rate_limit("draft_revert", 5, 60)),
):
    """Convenience shortcut: rewind the latest AI-edited turn. Finds the
    highest `message_num` in the changelog and reverts to message_num - 1."""
    db = get_db()
    uid = _user_id(user)
    sess = await _own_session_or_404(db, uid, session_id)

    last_num = await get_highest_message_num(db, uid, session_id)
    if last_num is None:
        return {"ok": False, "reason": "no_changelog_entries"}

    target = max(0, int(last_num) - 1)
    # Delegate to the revert handler logic — duplicate the body construction
    # so we get the same response shape + audit.
    body = RevertRequest(to_message_num=target)
    return await revert_draft(session_id, body, request, user)


__all__ = ["router"]
