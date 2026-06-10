"""
Rolling conversation summary — Task Force AI (Phase 3)

Every 20 messages of a vibe session we condense the running conversation into
a single ~800-word summary. The summary is stored encrypted (one row per
(user_id, session_id) in `conversation_summaries`) and is intended to be
prepended to the LLM system prompt for long sessions so context doesn't decay.

Mirror of Phase 2 patterns:
  - DI llm_caller so tests can stub.
  - Silent skip on no LLM key / cadence not reached / parse error.
  - Encrypt at rest via memory_crypto.
  - Audit via memory_audit.
"""
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from lib.memory_crypto import encrypt_text, decrypt_text
from lib.sensitive_redactor import redact_messages
from lib.memory_audit import log_memory_event

logger = logging.getLogger("memory_summarizer")

CADENCE = 20             # how many new messages between summary refreshes
DEFAULT_MODEL = "gemini-2.5-flash"
MAX_RECENT_FOR_SUMMARY = 20  # only the last N messages get full text in the prompt

SUMMARIZATION_PROMPT = """You are a conversation-summarisation agent for a long-running AI builder session.
You will be given:
  1. The PREVIOUS summary of this session (if any).
  2. The MOST RECENT messages of the session.

Produce a single condensed summary covering the ENTIRE conversation from the
beginning (not just the new messages). Keep it under 800 words.

The summary must:
  - Open with one sentence stating what the user is trying to build.
  - List the key DECISIONS made so far (architecture, integrations, file names,
    naming conventions, technology choices).
  - List the specific FILE NAMES that have been created or modified.
  - Capture user PREFERENCES that the AI should keep applying.
  - Note any CORRECTIONS the user issued ("stop calling them apps", etc.).
  - End with a one-line "Where we left off" pointer to the most recent topic.

Return the summary as PLAIN TEXT — no JSON, no code fences, no preamble.
If you have nothing meaningful to say (e.g. the conversation is empty),
return the literal string `(no content yet)`.
"""


async def update_rolling_summary(
    db,
    user_id: str,
    session_id: str,
    *,
    llm_caller: Optional[Callable] = None,
    force: bool = False,
) -> dict:
    """See module docstring. Never raises — errors come back as skipped=True."""
    base = {
        "skipped": False,
        "skipped_reason": None,
        "summary": None,
        "message_count": 0,
    }
    try:
        # 1. Determine cadence — read existing summary doc & session length.
        existing = await db.conversation_summaries.find_one(
            {"user_id": user_id, "session_id": session_id}, {"_id": 0},
        )
        last_summarized_at = int(existing.get("message_count", 0)) if existing else 0

        sess = await db.vibe_sessions.find_one(
            {"id": session_id, "user_id": user_id}, {"_id": 0, "messages": 1},
        )
        if not sess:
            base["skipped"] = True
            base["skipped_reason"] = "session_not_found"
            return base

        messages = sess.get("messages") or []
        total = len(messages)
        base["message_count"] = total

        if not force and (total - last_summarized_at) < CADENCE:
            base["skipped"] = True
            base["skipped_reason"] = "cadence_not_reached"
            return base

        # 2. Build caller (LLM key check)
        if llm_caller is None:
            llm_caller = await _build_default_caller(db, user_id)
            if llm_caller is None:
                base["skipped"] = True
                base["skipped_reason"] = "no_llm_key"
                return base

        # 3. Compose prompt with previous summary + last 20 messages (sanitized).
        previous_summary = decrypt_text(existing.get("summary", "")) if existing else ""
        recent = messages[-MAX_RECENT_FOR_SUMMARY:]
        recent_sanitized = redact_messages(recent)
        user_message = _build_user_payload(previous_summary, recent_sanitized, total)

        try:
            raw_text = await llm_caller(
                system_prompt=SUMMARIZATION_PROMPT,
                user_message=user_message,
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[summarizer] llm_call_failed: {type(e).__name__}: {str(e)[:140]}")
            base["skipped"] = True
            base["skipped_reason"] = "llm_call_failed"
            return base

        summary_text = (raw_text or "").strip()
        if not summary_text or summary_text.lower() == "(no content yet)":
            base["skipped"] = True
            base["skipped_reason"] = "empty_summary"
            return base

        # Hard cap on size to keep the summary table sane.
        if len(summary_text) > 8000:
            summary_text = summary_text[:8000]

        now = _now_iso()
        await db.conversation_summaries.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$set": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "summary": encrypt_text(summary_text),
                    "message_count": total,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        await _audit_safe(user_id, "summary_updated", {
            "session_id": session_id, "message_count": total,
        })
        base["summary"] = summary_text
        return base

    except Exception as e:  # noqa: BLE001 — last-resort guard
        logger.warning(f"[summarizer] unexpected error: {type(e).__name__}: {e}")
        base["skipped"] = True
        base["skipped_reason"] = f"error:{type(e).__name__}"
        return base


async def get_summary(db, user_id: str, session_id: str) -> Optional[dict]:
    """Read-and-decrypt helper used by the GET endpoint."""
    doc = await db.conversation_summaries.find_one(
        {"user_id": user_id, "session_id": session_id}, {"_id": 0},
    )
    if not doc:
        return None
    return {
        "summary": decrypt_text(doc.get("summary", "")),
        "message_count": doc.get("message_count", 0),
        "updated_at": doc.get("updated_at"),
        "created_at": doc.get("created_at"),
    }


# ─── Internals ────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _build_default_caller(db, user_id: str) -> Optional[Callable]:
    try:
        from lib.llm_client import resolve_api_key, call_llm  # noqa: WPS433
    except Exception as e:
        logger.debug(f"[summarizer] llm_client import failed: {e}")
        return None
    key_info = await resolve_api_key(db, user_id, DEFAULT_MODEL)
    api_key = key_info.get("api_key") or ""
    if not api_key:
        return None

    async def _call(system_prompt: str, user_message: str) -> str:
        result = await call_llm(
            model=DEFAULT_MODEL,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            api_key=api_key,
            session_key=f"memsum-{user_id[:8]}",
        )
        return (result or {}).get("text") or ""
    return _call


def _build_user_payload(previous_summary: str, recent_messages: list, total_count: int) -> str:
    lines = [
        "=== PREVIOUS SUMMARY ===",
        previous_summary if previous_summary else "(none yet — first summary for this session)",
        "",
        f"=== MOST RECENT {len(recent_messages)} MESSAGES of {total_count} total ===",
    ]
    for m in recent_messages:
        role = m.get("role", "?")
        text = (m.get("content") or "").strip()
        if not text:
            continue
        lines.append(f"[{role}] {text}")
    lines.extend([
        "",
        "Now produce the updated summary covering the ENTIRE conversation.",
    ])
    return "\n".join(lines)


async def _audit_safe(user_id: str, action: str, details: dict) -> None:
    try:
        await log_memory_event(user_id, action, details, request=None)
    except Exception:  # noqa: BLE001
        pass


__all__ = ["update_rolling_summary", "get_summary", "CADENCE"]
