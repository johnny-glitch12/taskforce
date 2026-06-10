"""
Memory-system cleanup jobs — Task Force AI (Phase 4)

Three daily housekeeping jobs registered with the existing AsyncIOScheduler:

  A. memory_hard_delete  — reap soft-deleted memories older than 30 days
  B. conversation_purge  — wipe vibe_sessions.messages older than 90 days
  C. file_versions_orphan_prune — drop file_versions whose session is gone

Each job is wrapped in try/except so a transient mongo hiccup doesn't take
the scheduler down. Each logs a single summary line per run. All operations
are idempotent and safe to re-run.

The jobs are exposed as PUBLIC async coroutines so a dev-only test endpoint
can trigger them on demand (see routes/builder_memory.py:_test_run_cleanup).
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("cleanup_jobs")

SOFT_DELETE_TTL_DAYS = 30
CONVERSATION_TTL_DAYS = 90


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def hard_delete_stale_memories(db) -> int:
    """Job A. Returns number of rows hard-deleted."""
    try:
        cutoff = (_now_utc() - timedelta(days=SOFT_DELETE_TTL_DAYS)).isoformat()
        res = await db.builder_memories.delete_many(
            {"active": False, "deleted_at": {"$lt": cutoff}},
        )
        n = res.deleted_count
        logger.info(f"[cleanup] hard-deleted {n} memory rows older than {SOFT_DELETE_TTL_DAYS} days")
        return n
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[cleanup:memory_hard_delete] {type(e).__name__}: {str(e)[:160]}")
        return 0


async def purge_old_conversations(db) -> int:
    """Job B. Returns number of vibe_sessions whose messages were wiped.

    We KEEP the session shell + project_id so the agent stays linked, but
    blow away `messages[]` (long-form chat history) and the encrypted
    summary blob (since the summary is derived from messages, it has the
    same retention window).
    """
    try:
        cutoff = (_now_utc() - timedelta(days=CONVERSATION_TTL_DAYS)).isoformat()
        # Find candidate session ids first so we can target their summaries too.
        cursor = db.vibe_sessions.find(
            {"updated_at": {"$lt": cutoff}, "messages": {"$exists": True, "$ne": []}},
            {"_id": 0, "id": 1, "user_id": 1},
        )
        candidates = [r async for r in cursor]
        if not candidates:
            logger.info(f"[cleanup] purged 0 vibe_sessions older than {CONVERSATION_TTL_DAYS} days")
            return 0

        session_ids = [c["id"] for c in candidates]
        await db.vibe_sessions.update_many(
            {"id": {"$in": session_ids}},
            {"$set": {"messages": [], "updated_at": _now_utc().isoformat(),
                      "purged_at": _now_utc().isoformat()}},
        )
        # Also wipe the per-session rolling summaries (derived data).
        await db.conversation_summaries.update_many(
            {"session_id": {"$in": session_ids}},
            {"$set": {"summary": "", "message_count": 0,
                      "updated_at": _now_utc().isoformat(),
                      "purged_at": _now_utc().isoformat()}},
        )
        n = len(session_ids)
        logger.info(f"[cleanup] purged {n} vibe_sessions older than {CONVERSATION_TTL_DAYS} days")
        return n
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[cleanup:conversation_purge] {type(e).__name__}: {str(e)[:160]}")
        return 0


async def prune_orphan_file_versions(db) -> int:
    """Job C. Returns number of file_versions rows removed."""
    try:
        # Two-step: collect live session ids, then delete anything not in that set.
        cursor = db.vibe_sessions.find({}, {"_id": 0, "id": 1})
        live_ids = {r["id"] async for r in cursor if r.get("id")}
        res = await db.file_versions.delete_many(
            {"session_id": {"$nin": list(live_ids)}} if live_ids
            else {},  # if literally no sessions exist, everything is orphan
        )
        n = res.deleted_count
        logger.info(f"[cleanup] removed {n} orphan file_versions")
        return n
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[cleanup:file_versions_orphan_prune] {type(e).__name__}: {str(e)[:160]}")
        return 0


async def run_all(db) -> dict:
    """Convenience helper for the dev test endpoint — runs all three back to back."""
    return {
        "hard_deleted_memories": await hard_delete_stale_memories(db),
        "purged_conversations":  await purge_old_conversations(db),
        "orphan_file_versions_removed": await prune_orphan_file_versions(db),
    }


__all__ = [
    "hard_delete_stale_memories",
    "purge_old_conversations",
    "prune_orphan_file_versions",
    "run_all",
    "SOFT_DELETE_TTL_DAYS",
    "CONVERSATION_TTL_DAYS",
]
