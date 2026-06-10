"""
Agent changelog — Task Force AI (Phase 3)

Tracks user-facing edits made by the AI within a draft (vibe session).
One doc per (user_id, session_id), with an `entries[]` array. Each entry
records a message_num + a list of file-level changes the AI made at that
turn.

Used for:
  - Answering "remember when we added Slack?" — the AI can scan its own
    changelog and cite a turn number.
  - Driving the undo/revert UX in Phase 3.

What strings are NOT encrypted — they're short action-level metadata ("Added
    Slack notification", "Renamed handler.py to webhook.py"). They're capped
    at 200 chars to keep the doc bounded.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from lib.memory_audit import log_memory_event

logger = logging.getLogger("agent_changelog")

MAX_WHAT_LEN = 200
VALID_ACTIONS = {"created", "modified", "deleted", "renamed", "reverted"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_change(c: dict) -> Optional[dict]:
    """Validate + truncate a single changelog change. Returns None if invalid."""
    if not isinstance(c, dict):
        return None
    fname = (c.get("file") or "").strip()
    action = (c.get("action") or "").strip().lower()
    what = (c.get("what") or "").strip()
    if not fname or action not in VALID_ACTIONS:
        return None
    if len(what) > MAX_WHAT_LEN:
        what = what[:MAX_WHAT_LEN - 1] + "…"
    return {"file": fname[:255], "action": action, "what": what}


async def log_change(
    db,
    user_id: str,
    session_id: str,
    message_num: int,
    changes: list[dict],
) -> str:
    """Append a changelog entry. Returns the entry id."""
    cleaned = [c for c in (_normalize_change(c) for c in (changes or [])) if c]
    if not cleaned:
        return ""
    entry_id = str(uuid.uuid4())
    entry = {
        "entry_id": entry_id,
        "message_num": int(message_num),
        "changes": cleaned,
        "created_at": _now_iso(),
    }
    now = entry["created_at"]
    await db.agent_changelogs.update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$set": {"user_id": user_id, "session_id": session_id, "updated_at": now},
            "$push": {"entries": entry},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    try:
        await log_memory_event(
            user_id, "changelog_appended",
            {"session_id": session_id, "message_num": message_num, "file_count": len(cleaned)},
            request=None,
        )
    except Exception:  # noqa: BLE001
        pass
    return entry_id


async def get_changelog(db, user_id: str, session_id: str) -> list[dict]:
    """Return entries[] for the user+session, oldest-first. Empty list if none."""
    doc = await db.agent_changelogs.find_one(
        {"user_id": user_id, "session_id": session_id}, {"_id": 0},
    )
    if not doc:
        return []
    entries = doc.get("entries") or []
    entries.sort(key=lambda e: (e.get("message_num", 0), e.get("created_at", "")))
    return entries


async def get_highest_message_num(db, user_id: str, session_id: str) -> Optional[int]:
    """Return the highest `message_num` recorded in the changelog, or None.
    Used by the /undo endpoint to find the most-recent AI-edited turn."""
    entries = await get_changelog(db, user_id, session_id)
    if not entries:
        return None
    return max(int(e.get("message_num", 0)) for e in entries)


__all__ = ["log_change", "get_changelog", "get_highest_message_num", "VALID_ACTIONS"]
