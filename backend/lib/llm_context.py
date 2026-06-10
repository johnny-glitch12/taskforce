"""
Full LLM context assembler — Task Force AI (Phase 3)

Produces the full "context package" for the next LLM call against a vibe
session. Combines:
  - User-level memory (profile + typed memories)  → memory_injector
  - Session-level rolling summary                 → memory_summarizer
  - Per-turn changelog entries                    → agent_changelog
  - The last N raw messages                       → vibe_sessions
  - The brand-new user message

Returned as a structured dict so the caller can format the system prompt
however it likes. NOT wired into routes/vibe_coding.py in Phase 3 — it lives
here ready to be adopted in Phase 4.

All memory is decrypted before return. Caller must not write any field of the
returned dict back to storage without re-encrypting first.
"""
import logging
from typing import Optional

from lib.memory_crypto import decrypt_text, decrypt_dict
from lib.memory_injector import build_memory_context
from lib.memory_summarizer import get_summary
from lib.agent_changelog import get_changelog

logger = logging.getLogger("llm_context")

MAX_RECENT_MESSAGES = 30
MAX_CHANGELOG_ENTRIES = 50


async def build_chat_context(
    db,
    user_id: str,
    session_id: str,
    new_message: str,
) -> dict:
    """Return the full context package for the next LLM call. See module doc."""
    # 1. Memory context (user-scoped, session-agnostic)
    profile_doc = await db.builder_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if profile_doc:
        profile = {
            "business":    decrypt_dict(profile_doc.get("business") or {}),
            "preferences": decrypt_dict(profile_doc.get("preferences") or {}),
            "integrations": profile_doc.get("integrations") or {"byok_keys": []},
        }
    else:
        profile = None

    correction_rows = await db.builder_memories.find(
        {"user_id": user_id, "active": True, "type": "correction"}, {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(length=50)
    other_rows = await db.builder_memories.find(
        {"user_id": user_id, "active": True, "type": {"$ne": "correction"}}, {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(length=50)
    memories = [{**r, "content": decrypt_text(r.get("content", ""))} for r in (correction_rows + other_rows)]
    memory_context = build_memory_context(profile, memories)

    # 2. Rolling summary (session-scoped)
    summary_doc = await get_summary(db, user_id, session_id)
    summary = summary_doc.get("summary") if summary_doc else None

    # 3. Changelog entries (session-scoped) — cap to most recent N
    all_entries = await get_changelog(db, user_id, session_id)
    if len(all_entries) > MAX_CHANGELOG_ENTRIES:
        all_entries = all_entries[-MAX_CHANGELOG_ENTRIES:]

    # 4. Recent messages from the vibe session
    sess = await db.vibe_sessions.find_one(
        {"id": session_id, "user_id": user_id},
        {"_id": 0, "messages": {"$slice": -MAX_RECENT_MESSAGES}},
    )
    if sess and isinstance(sess.get("messages"), list):
        recent_messages = sess["messages"]
    else:
        recent_messages = []

    return {
        "memory_context": memory_context,
        "summary": summary,
        "changelog_entries": all_entries,
        "recent_messages": recent_messages,
        "new_message": new_message,
    }


__all__ = ["build_chat_context"]
