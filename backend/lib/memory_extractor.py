"""
Memory extractor — Task Force AI (Phase 2)

Given a small slice of recent chat turns, asks the LLM to pull out durable
*structured* memories (preferences, business context, technical facts,
feedback, corrections) plus profile updates, then persists them encrypted.

Design goals:
  - Pure dependency injection for the LLM caller so tests can stub it
    (no network in test runs).
  - Silently no-op on EVERY failure mode the user could plausibly hit:
    no LLM key, parse failure, trivial turn, network error, missing schema.
  - Defense-in-depth sanitization: redact secrets BEFORE prompting and AGAIN
    after parsing the LLM's output (the model could echo back something we
    missed in the input scan, or could hallucinate a key shape).
  - Cross-user safe: every read and write keys on the authenticated user_id.
    The session_id is stored as `source="vibe:<session_id>"` for traceability
    but is NOT used as an authorization check.
  - Dedup at write time — we compare new content against the user's existing
    active memories of the same type (decrypted). With ≤ 30 candidates per
    type this is fine; if it ever isn't, switch to a content hash field.

Public API: `extract_and_persist(...)`. Anything else is private.
"""
import json
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, Any

from lib.memory_crypto import encrypt_text, decrypt_text, encrypt_dict, decrypt_dict
from lib.sensitive_redactor import redact_messages, redact_secrets, is_fully_redacted
from lib.memory_audit import log_memory_event

logger = logging.getLogger("memory_extractor")

# Lower-cased patterns we treat as a "trivial" assistant message and skip.
_TRIVIAL_ACK_PATTERNS = [
    re.compile(r"^(ok|okay|done|thanks|thank you|got it|cool|sure|noted|alright|sounds good|will do|sweet)[\.\!\?\s]*$", re.I),
    re.compile(r"^(working on it|generating|saving|saved|building|loading|processing)[\.\!\s]*$", re.I),
    re.compile(r"^(yes|no|maybe|perhaps|hmm|huh|right|wait)[\.\!\?\s]*$", re.I),
]
_TRIVIAL_LEN_THRESHOLD = 80
_TRIVIAL_USER_LEN_THRESHOLD = 20

MEMORY_TYPES = {"business_context", "preference", "technical", "feedback", "correction"}
MAX_CONTEXT_MEMORIES = 30   # passed back to the LLM so it doesn't re-extract known stuff
MAX_NEW_MEMORIES_PER_TURN = 8
DEFAULT_MODEL = "gemini-2.5-flash"

# ── Extraction prompt ───────────────────────────────────────────────
EXTRACTION_SYSTEM_PROMPT = """You are a memory-extraction agent for an AI builder platform.
Your job: read the last few turns of a chat between a user and an AI agent builder,
and pull out DURABLE facts about the user / their work / their preferences that
would be useful in FUTURE conversations.

DO extract:
  - business_context : who they are, what they're building, the company, the audience
  - preference       : how they want the AI to respond (style, tone, format, verbosity)
  - technical        : languages, frameworks, infra patterns, services they use
  - feedback         : past answers they liked or disliked (with the *reason* why)
  - correction       : things they explicitly told the AI to stop / start doing

DO NOT extract:
  - One-off questions ("what time is it in Tokyo")
  - Conversational filler ("thanks", "got it")
  - Information already in the EXISTING MEMORIES block below
  - Anything that looks like an API key, password, OAuth token, or PII (emails,
    phone numbers, addresses). The sanitizer will scrub these but you should
    not propagate them.

Return STRICT JSON — no prose, no code fences, just one object:

{
  "memories": [
    {"type": "preference", "content": "Prefers bullet-point replies under 200 words."},
    ...
  ],
  "profile_updates": {
    "business":    { "industry": "...", "description": "...", "target_audience": "..." },
    "preferences": { "reply_style": "...", "tone": "..." },
    "integrations": { "byok_keys": ["openai"], "gmail_oauth": true }
  }
}

Rules:
  - `memories` may be an empty array if nothing new is worth extracting.
  - `profile_updates` may be an empty object {}.
  - Every `content` MUST be a complete sentence, third person, 5–30 words.
  - For `integrations`, ONLY include boolean flags and string-list `byok_keys`.
    NEVER include raw key values. If you see one, ignore it.
  - If a piece of info is already in EXISTING MEMORIES, skip it.
  - Maximum %MAX_NEW% new memories per extraction. Pick the highest-signal items.
"""


# ─── Public API ───────────────────────────────────────────────
async def extract_and_persist(
    db,
    user_id: str,
    session_id: str,
    recent_messages: list[dict],
    *,
    llm_caller: Optional[Callable] = None,
    force: bool = False,
) -> dict:
    """See module docstring. Returns a result dict — never raises."""
    now = _now_iso()
    base = {
        "skipped": False,
        "skipped_reason": None,
        "memories_inserted": [],
        "profile_updated": False,
        "raw_extraction": None,
    }

    try:
        # 1. Triviality skip (unless force=True)
        if not force:
            reason = _maybe_skip_trivial(recent_messages)
            if reason:
                base["skipped"] = True
                base["skipped_reason"] = reason
                await _audit_safe(user_id, reason)
                logger.debug(f"[extractor] user={user_id[:8]} skipped: {reason}")
                return base

        # 2. Sanitize incoming messages (defense in depth #1)
        sanitized = redact_messages(recent_messages)

        # 3. Pull existing memories so the LLM doesn't re-extract known stuff
        existing = await _load_existing(db, user_id, limit=MAX_CONTEXT_MEMORIES)

        # 4. Resolve LLM key or use injected caller
        if llm_caller is None:
            llm_caller = await _build_default_caller(db, user_id)
            if llm_caller is None:
                base["skipped"] = True
                base["skipped_reason"] = "no_llm_key"
                await _audit_safe(user_id, "no_llm_key")
                logger.debug(f"[extractor] user={user_id[:8]} skipped: no_llm_key")
                return base

        # 5. Build prompt + call LLM
        try:
            system_prompt = EXTRACTION_SYSTEM_PROMPT.replace("%MAX_NEW%", str(MAX_NEW_MEMORIES_PER_TURN))
            raw_text = await llm_caller(
                system_prompt=system_prompt,
                user_message=_build_user_message(sanitized, existing),
            )
        except Exception as e:  # noqa: BLE001
            base["skipped"] = True
            base["skipped_reason"] = "llm_call_failed"
            logger.debug(f"[extractor] user={user_id[:8]} llm_call_failed: {type(e).__name__}: {str(e)[:120]}")
            await _audit_safe(user_id, "llm_call_failed")
            return base

        # 6. Parse JSON
        parsed = _parse_json(raw_text)
        if parsed is None:
            base["skipped"] = True
            base["skipped_reason"] = "parse_failure"
            logger.debug(f"[extractor] user={user_id[:8]} parse_failure: raw={str(raw_text)[:160]}")
            await _audit_safe(user_id, "parse_failure")
            return base
        base["raw_extraction"] = parsed

        # 7. Persist memories with redaction + dedup
        new_memories = parsed.get("memories") or []
        if isinstance(new_memories, list):
            inserted = await _persist_memories(
                db, user_id, session_id, new_memories, existing, now,
            )
            base["memories_inserted"] = inserted

        # 8. Merge profile updates
        profile_updates = parsed.get("profile_updates") or {}
        if isinstance(profile_updates, dict) and profile_updates:
            await _merge_profile(db, user_id, profile_updates, now)
            base["profile_updated"] = True

        # 9. Cap enforcement (Phase 4) — soft-delete oldest non-corrections
        # if we exceed the per-user active cap. Fire-and-forget so a slow
        # prune never blocks the extraction return path. Safe to dispatch
        # even when 0 memories were inserted — the pruner is a no-op below
        # cap.
        try:
            import asyncio as _asyncio
            from lib.memory_pruner import prune_user_memories
            _asyncio.create_task(prune_user_memories(db, user_id))
        except Exception as _prune_err:  # noqa: BLE001
            logger.debug(f"[extractor] prune dispatch failed (non-fatal): {_prune_err}")

        await _audit_safe(
            user_id, "completed",
            count=len(base["memories_inserted"]),
            profile_updated=base["profile_updated"],
        )
        return base

    except Exception as e:  # noqa: BLE001 — last-resort guard
        logger.warning(f"[extractor] user={user_id[:8]} unexpected error: {type(e).__name__}: {e}")
        base["skipped"] = True
        base["skipped_reason"] = f"error:{type(e).__name__}"
        return base


# ─── Internal helpers ──────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _maybe_skip_trivial(messages: list[dict]) -> Optional[str]:
    """Return a reason string if the conversation slice is too short/trivial
    to extract from, else None. Cheap-to-evaluate, runs before any LLM call."""
    if not messages:
        return "insufficient_history"

    # Find last assistant + last user message
    last_asst = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if not last_asst or not last_user:
        return "insufficient_history"

    asst_text = (last_asst.get("content") or "").strip()
    user_text = (last_user.get("content") or "").strip()

    if len(asst_text) < _TRIVIAL_LEN_THRESHOLD and any(p.match(asst_text) for p in _TRIVIAL_ACK_PATTERNS):
        return "trivial_response"
    if len(asst_text) < _TRIVIAL_LEN_THRESHOLD and len(user_text) < _TRIVIAL_USER_LEN_THRESHOLD \
            and any(p.match(user_text) for p in _TRIVIAL_ACK_PATTERNS):
        return "trivial_response"
    return None


async def _load_existing(db, user_id: str, limit: int) -> list[dict]:
    """Return decrypted active memories for the user, corrections-first ordering."""
    cursor = db.builder_memories.find(
        {"user_id": user_id, "active": True}, {"_id": 0}
    ).sort([("type", 1), ("created_at", -1)]).limit(limit * 2)  # over-fetch then re-sort
    rows = await cursor.to_list(length=limit * 2)
    # Decrypt & re-order: corrections first
    out = []
    for r in rows:
        out.append({**r, "content": decrypt_text(r.get("content", ""))})
    corrections = [m for m in out if m["type"] == "correction"]
    others = [m for m in out if m["type"] != "correction"]
    return (corrections + others)[:limit]


async def _build_default_caller(db, user_id: str) -> Optional[Callable]:
    """Construct a single-shot LLM caller. Returns None when no key is available
    (the calling extractor then skips with reason='no_llm_key')."""
    try:
        from lib.llm_client import resolve_api_key, call_llm  # noqa: WPS433
    except Exception as e:
        logger.debug(f"[extractor] llm_client import failed: {e}")
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
            session_key=f"memext-{user_id[:8]}",
        )
        return (result or {}).get("text") or ""

    return _call


def _build_user_message(sanitized_history: list[dict], existing: list[dict]) -> str:
    transcript_lines = []
    for m in sanitized_history:
        role = m.get("role", "?")
        text = (m.get("content") or "").strip()
        if not text:
            continue
        transcript_lines.append(f"[{role}] {text}")
    transcript = "\n".join(transcript_lines) or "(empty)"

    existing_lines = []
    for m in existing:
        existing_lines.append(f"- [{m.get('type')}] {m.get('content','').strip()}")
    existing_block = "\n".join(existing_lines) or "(none yet)"

    return (
        "=== RECENT CONVERSATION ===\n"
        f"{transcript}\n\n"
        "=== EXISTING MEMORIES (do not re-extract) ===\n"
        f"{existing_block}\n\n"
        "Now produce the JSON."
    )


_CODE_FENCE = re.compile(r"^```[a-zA-Z0-9_-]*\s*|\s*```$", re.M)


def _parse_json(raw: Any) -> Optional[dict]:
    """Tolerant JSON extraction — strips code fences, finds first {...last}."""
    if not raw:
        return None
    text = raw if isinstance(raw, str) else str(raw)
    text = _CODE_FENCE.sub("", text).strip()
    # If the LLM returned pre-amble like "Here's the JSON:\n{...}", carve it out.
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = text[first:last + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Try a second pass after collapsing trailing-comma issues
        candidate2 = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate2)
        except Exception:
            return None


async def _persist_memories(
    db, user_id: str, session_id: str, new_memories: list, existing: list[dict], now: str,
) -> list[str]:
    """Insert new memories with sanitization + dedup. Returns list of inserted IDs."""
    # Build a fast lookup of existing (type, content) for dedup.
    existing_set = {(m.get("type"), (m.get("content") or "").strip().lower()) for m in existing}
    inserted_ids: list[str] = []

    for item in new_memories[:MAX_NEW_MEMORIES_PER_TURN]:
        if not isinstance(item, dict):
            continue
        mtype = item.get("type")
        if mtype not in MEMORY_TYPES:
            continue
        raw_content = (item.get("content") or "").strip()
        if not raw_content:
            continue

        # Defense in depth #2: redact secrets the LLM might have echoed back.
        clean = redact_secrets(raw_content)
        if is_fully_redacted(clean):
            logger.debug("[extractor] dropped memory — fully redacted after sanitization")
            continue

        key = (mtype, clean.lower())
        if key in existing_set:
            continue  # dedup against existing memories
        existing_set.add(key)  # also dedup within this batch

        mem_id = str(uuid.uuid4())
        await db.builder_memories.insert_one({
            "id": mem_id,
            "user_id": user_id,
            "type": mtype,
            "content": encrypt_text(clean),
            "source": f"vibe:{session_id}",
            "active": True,
            "created_at": now,
            "updated_at": now,
        })
        inserted_ids.append(mem_id)

    return inserted_ids


async def _merge_profile(db, user_id: str, updates: dict, now: str) -> None:
    """Deep-merge new profile updates into the user's existing profile.
    Decrypts existing values, merges, re-encrypts, upserts."""
    existing = await db.builder_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
    decrypted = {
        "business": decrypt_dict(existing.get("business") or {}),
        "preferences": decrypt_dict(existing.get("preferences") or {}),
        "integrations": existing.get("integrations") or {},
    }

    merged = {
        "business":    _deep_merge(decrypted["business"],    _sanitize_profile_section(updates.get("business") or {})),
        "preferences": _deep_merge(decrypted["preferences"], _sanitize_profile_section(updates.get("preferences") or {})),
        "integrations": _merge_integrations(decrypted["integrations"], updates.get("integrations") or {}),
    }

    await db.builder_profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "business": encrypt_dict(merged["business"]),
                "preferences": encrypt_dict(merged["preferences"]),
                "integrations": merged["integrations"],
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def _sanitize_profile_section(section: Any) -> dict:
    """Run string values through `redact_secrets` so no key value sneaks into
    business/preferences via the profile path. Non-dict input collapses to {}."""
    if not isinstance(section, dict):
        return {}
    out = {}
    for k, v in section.items():
        if isinstance(v, str):
            cleaned = redact_secrets(v).strip()
            if cleaned and not is_fully_redacted(cleaned):
                out[k] = cleaned
        elif isinstance(v, (int, float, bool)):
            out[k] = v
        elif isinstance(v, list):
            # Only keep scalar list items, redact strings
            cleaned_list = []
            for it in v:
                if isinstance(it, str):
                    c = redact_secrets(it).strip()
                    if c and not is_fully_redacted(c):
                        cleaned_list.append(c)
                elif isinstance(it, (int, float, bool)):
                    cleaned_list.append(it)
            if cleaned_list:
                out[k] = cleaned_list
        elif isinstance(v, dict):
            sub = _sanitize_profile_section(v)
            if sub:
                out[k] = sub
    return out


def _merge_integrations(existing: Any, updates: Any) -> dict:
    """Integrations stores ONLY booleans + the byok_keys string list.
    Any other field is silently dropped on merge."""
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(updates, dict):
        updates = {}

    out = dict(existing)
    # byok_keys union
    eb = existing.get("byok_keys") if isinstance(existing.get("byok_keys"), list) else []
    ub = updates.get("byok_keys") if isinstance(updates.get("byok_keys"), list) else []
    merged_byok = []
    seen = set()
    for it in (eb + ub):
        if isinstance(it, str):
            cleaned = it.strip().lower()
            if cleaned and cleaned not in seen and not _looks_like_key_value(cleaned):
                merged_byok.append(cleaned)
                seen.add(cleaned)
    out["byok_keys"] = merged_byok

    # Boolean flags: take the update if it's a real bool
    for k, v in updates.items():
        if k == "byok_keys":
            continue
        if isinstance(v, bool):
            out[k] = v
    # Strip any non-bool / non-byok values that slipped in from existing (legacy rows)
    return {
        k: v for k, v in out.items()
        if k == "byok_keys" or isinstance(v, bool)
    }


def _looks_like_key_value(s: str) -> bool:
    """Reject anything in byok_keys that looks like a raw key rather than a service slug."""
    if len(s) > 24:
        return True
    if any(s.startswith(p) for p in ("sk-", "sk_", "ghp_", "aiza", "xox", "akia", "eyj")):
        return True
    return False


def _deep_merge(a: Any, b: Any) -> dict:
    """Merge b INTO a. Strings/scalars: b wins. Lists: union preserving order.
    Dicts: recurse per key. Returns a new dict, does not mutate inputs."""
    if not isinstance(a, dict):
        a = {}
    if not isinstance(b, dict):
        return dict(a)
    out = dict(a)
    for k, vb in b.items():
        va = out.get(k)
        if isinstance(va, dict) and isinstance(vb, dict):
            out[k] = _deep_merge(va, vb)
        elif isinstance(va, list) and isinstance(vb, list):
            seen = set()
            merged = []
            for it in (va + vb):
                if isinstance(it, (str, int, float, bool)):
                    key = (type(it).__name__, it)
                    if key not in seen:
                        seen.add(key)
                        merged.append(it)
                else:
                    merged.append(it)
            out[k] = merged
        else:
            out[k] = vb
    return out


async def _audit_safe(user_id: str, reason: str, **extra) -> None:
    try:
        await log_memory_event(
            user_id, "memory_extracted",
            {"reason": reason, **extra},
            request=None,
        )
    except Exception:  # noqa: BLE001
        pass


__all__ = ["extract_and_persist"]
