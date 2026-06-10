"""
File versions — Task Force AI (Phase 3)

Snapshots the OLD content of a file BEFORE an AI edit overwrites it. Powers
the undo / revert UX. One row per (user_id, session_id, filename, version).

Design:
  - Content is encrypted at rest via memory_crypto (full file body — could be
    arbitrary text including code).
  - `version` is the session message_num at which the OLD content was
    captured. Revert-to-message N picks the largest version <= N for each
    file (i.e. the most recent snapshot taken BEFORE turn N).
  - Bounded retention: at most 50 versions per (user, session, file). Older
    versions are pruned on insert.
  - We do NOT audit every save — a 10-file generate would emit 10 audits per
    turn. Audit only the higher-level revert action via memory_audit.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from lib.memory_crypto import encrypt_text, decrypt_text
from lib.ownership import ensure_ownership

logger = logging.getLogger("file_versions")

MAX_VERSIONS_PER_FILE = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_file_version(
    db,
    user_id: str,
    session_id: str,
    filename: str,
    old_content: str,
    message_num: int,
) -> str:
    """Insert a snapshot. Returns the version_id.
    Caps total snapshots per file at MAX_VERSIONS_PER_FILE — oldest pruned."""
    if not filename:
        return ""
    version_id = str(uuid.uuid4())
    now = _now_iso()
    await db.file_versions.insert_one({
        "id": version_id,
        "user_id": user_id,
        "session_id": session_id,
        "filename": filename,
        "content": encrypt_text(old_content or ""),
        "version": int(message_num),
        "created_at": now,
    })

    # Prune — keep only the most recent MAX_VERSIONS_PER_FILE.
    count = await db.file_versions.count_documents({
        "user_id": user_id, "session_id": session_id, "filename": filename,
    })
    if count > MAX_VERSIONS_PER_FILE:
        # Find the oldest (smallest version, then oldest created_at).
        excess = count - MAX_VERSIONS_PER_FILE
        cursor = db.file_versions.find(
            {"user_id": user_id, "session_id": session_id, "filename": filename},
            {"id": 1, "_id": 0},
        ).sort([("version", 1), ("created_at", 1)]).limit(excess)
        old_ids = [r["id"] async for r in cursor]
        if old_ids:
            await db.file_versions.delete_many({"id": {"$in": old_ids}})
    return version_id


async def list_versions(
    db, user_id: str, session_id: str, filename: Optional[str] = None,
) -> list[dict]:
    """Return version metadata (no content blobs) sorted by version desc, then
    created_at desc as a tie-breaker. If filename is provided, scope to that
    file; otherwise return ALL versions for the session."""
    q = {"user_id": user_id, "session_id": session_id}
    if filename:
        q["filename"] = filename
    cursor = db.file_versions.find(
        q, {"_id": 0, "content": 0},
    ).sort([("version", -1), ("created_at", -1)])
    return await cursor.to_list(length=1000)


async def get_version_content(db, user_id: str, session_id: str, version_id: str) -> str:
    """Return decrypted file content for one version. 404 (via ensure_ownership)
    on cross-user attempt."""
    row = await db.file_versions.find_one({"id": version_id}, {"_id": 0})
    ensure_ownership(row, user_id)
    # Also defensively check session match (file_versions for the wrong session
    # for the same user shouldn't leak across drafts).
    if row.get("session_id") != session_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return decrypt_text(row.get("content", ""))


async def restore_files_to_message(
    db, user_id: str, session_id: str, target_message_num: int,
) -> dict:
    """Compute the revert plan for a given target message_num.

    For every filename that has at least one snapshot, find the one with the
    largest `version <= target_message_num`. That's the state JUST BEFORE
    `target_message_num` was processed.

    Returns:
        {
          "target_message_num": N,
          "restored": [{"filename":..., "from_version": N, "content": <decrypted>, "version_id":...}, ...],
          "no_history":  [filename, ...],   # files that exist in the project but have no snapshot <= N
        }

    The `content` field is decrypted plaintext — the caller is responsible
    for writing it back to bot_projects.files[] (we keep that I/O at the
    route layer so this function stays pure-ish and testable).
    """
    # Pull every filename that has at least one snapshot for this user+session
    all_files_cursor = db.file_versions.find(
        {"user_id": user_id, "session_id": session_id},
        {"_id": 0, "filename": 1},
    )
    filenames = set()
    async for r in all_files_cursor:
        f = r.get("filename")
        if f:
            filenames.add(f)

    restored: list[dict] = []
    no_history: list[str] = []

    for fname in sorted(filenames):
        # Largest version <= target
        candidate = await db.file_versions.find_one(
            {
                "user_id": user_id, "session_id": session_id,
                "filename": fname, "version": {"$lte": int(target_message_num)},
            },
            {"_id": 0},
            sort=[("version", -1), ("created_at", -1)],
        )
        if not candidate:
            no_history.append(fname)
            continue
        restored.append({
            "filename": fname,
            "from_version": candidate.get("version"),
            "version_id": candidate.get("id"),
            "content": decrypt_text(candidate.get("content", "")),
        })

    return {
        "target_message_num": int(target_message_num),
        "restored": restored,
        "no_history": no_history,
    }


__all__ = [
    "save_file_version",
    "list_versions",
    "get_version_content",
    "restore_files_to_message",
    "MAX_VERSIONS_PER_FILE",
]
