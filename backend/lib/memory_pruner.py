"""
Memory cap enforcement — Task Force AI (Phase 4)

Keeps the per-user `builder_memories` active set under a hard cap. Corrections
are NEVER pruned (highest-priority signal). When over cap, soft-deletes the
oldest non-correction memories (sets active=False + deleted_at=now). The
daily hard-delete job (server.py APScheduler) will reap them 30 days later.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("memory_pruner")

DEFAULT_CAP = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def prune_user_memories(db, user_id: str, *, cap: int = DEFAULT_CAP) -> dict:
    """Enforce the per-user active-memory cap.

    Algorithm:
      1. Count active memories. If <= cap, no-op.
      2. Count corrections (always preserved).
      3. Take the oldest non-correction active memories until count <= cap.
      4. Bulk-update them to active=False + deleted_at=now (soft-delete).

    Returns: {
        "pruned_count":          int,
        "remaining_count":      int,   # active count after prune
        "corrections_preserved": int,
    }
    Never raises — errors come back as pruned_count=0.
    """
    try:
        total_active = await db.builder_memories.count_documents(
            {"user_id": user_id, "active": True},
        )
        if total_active <= cap:
            return {
                "pruned_count": 0,
                "remaining_count": total_active,
                "corrections_preserved":
                    await db.builder_memories.count_documents(
                        {"user_id": user_id, "active": True, "type": "correction"},
                    ),
            }

        corrections = await db.builder_memories.count_documents(
            {"user_id": user_id, "active": True, "type": "correction"},
        )
        # We can only prune non-corrections.
        non_correction_active = total_active - corrections
        # How many to drop = total_active - cap. If corrections alone exceed
        # cap, we cannot prune them — just return the truth.
        drop_count = total_active - cap
        if non_correction_active <= 0 or drop_count <= 0:
            return {
                "pruned_count": 0,
                "remaining_count": total_active,
                "corrections_preserved": corrections,
            }
        drop_count = min(drop_count, non_correction_active)

        # Pick oldest non-correction active memories
        oldest_cursor = db.builder_memories.find(
            {"user_id": user_id, "active": True, "type": {"$ne": "correction"}},
            {"_id": 0, "id": 1},
        ).sort("created_at", 1).limit(drop_count)
        ids = [r["id"] async for r in oldest_cursor]

        if not ids:
            return {
                "pruned_count": 0,
                "remaining_count": total_active,
                "corrections_preserved": corrections,
            }

        now = _now_iso()
        res = await db.builder_memories.update_many(
            {"id": {"$in": ids}},
            {"$set": {"active": False, "deleted_at": now, "updated_at": now}},
        )
        pruned = res.modified_count

        # Best-effort audit (only when we actually pruned)
        if pruned > 0:
            try:
                from lib.memory_audit import log_memory_event
                await log_memory_event(
                    user_id, "memory_pruned",
                    {"count": pruned, "cap": cap, "remaining": total_active - pruned},
                    request=None,
                )
            except Exception:  # noqa: BLE001
                pass

        return {
            "pruned_count": pruned,
            "remaining_count": total_active - pruned,
            "corrections_preserved": corrections,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[memory_pruner] {type(e).__name__}: {str(e)[:120]}")
        return {"pruned_count": 0, "remaining_count": -1, "corrections_preserved": 0}


__all__ = ["prune_user_memories", "DEFAULT_CAP"]
