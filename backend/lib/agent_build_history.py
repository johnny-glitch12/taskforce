"""
Agent build history — Task Force AI (Phase 4)

One `agent_build_history` doc per user, with a `builds[]` array of compact
entries describing every agent the user has created / updated / published.
Feeds the "my agents" lifecycle view + lets the AI answer "what was the
recipe for my last Slack bot?" without re-reading bot_projects.

Integration detection is heuristic — we scan file contents for well-known
import / library tokens. This is best-effort: false negatives are fine, false
positives are acceptable (the user can edit). Patterns are deliberately
lower-cased + word-boundary-bounded to avoid catching them inside other
strings.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("agent_build_history")

VALID_EVENTS = {"created", "updated", "published", "archived"}
VALID_STATUS = {"draft", "published", "archived"}

# (slug, regex). Each pattern is searched case-insensitively against the
# CONCATENATED file contents of the build.
_INTEGRATION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("slack",       re.compile(r"\b(import\s+slack|slack[_\.]webhook|slack_sdk|slack_bolt|slack\.com)\b", re.I)),
    ("gmail",       re.compile(r"\b(import\s+smtplib|smtplib|gmail\.com|gmail_api|googleapiclient\.discovery)\b", re.I)),
    ("stripe",      re.compile(r"\b(import\s+stripe|stripe\.api_key|stripe\.checkout)\b", re.I)),
    ("notion",      re.compile(r"\b(notion-client|notion_client|api\.notion\.com)\b", re.I)),
    ("openai",      re.compile(r"\b(import\s+openai|from\s+openai|openai\.ChatCompletion|openai_api)\b", re.I)),
    ("anthropic",   re.compile(r"\b(import\s+anthropic|from\s+anthropic|claude-)\b", re.I)),
    ("google_genai", re.compile(r"\b(google\.generativeai|google_genai|google-genai|gemini)\b", re.I)),
    ("discord",     re.compile(r"\b(import\s+discord|discord\.py|discord_webhook)\b", re.I)),
    ("twilio",      re.compile(r"\b(import\s+twilio|twilio\.rest)\b", re.I)),
    ("sendgrid",    re.compile(r"\b(import\s+sendgrid|sendgrid_api)\b", re.I)),
    ("github",      re.compile(r"\b(import\s+github|PyGithub|api\.github\.com)\b", re.I)),
    ("telegram",    re.compile(r"\b(python-telegram-bot|api\.telegram\.org)\b", re.I)),
    ("hubspot",     re.compile(r"\b(hubspot|api\.hubapi\.com)\b", re.I)),
    ("airtable",    re.compile(r"\b(import\s+airtable|airtable\.com|api\.airtable\.com)\b", re.I)),
    ("requests",    re.compile(r"\b(import\s+requests|requests\.(get|post|put|delete))\b", re.I)),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_integrations(files: list[dict]) -> list[str]:
    """Return a sorted list of integration slugs detected across the build.
    Skips `requests` if any more-specific integration was detected (it's
    almost certainly there as the transport layer)."""
    if not files:
        return []
    bundle_parts = []
    for f in files:
        if not isinstance(f, dict):
            continue
        content = f.get("content")
        if isinstance(content, str):
            bundle_parts.append(content)
    if not bundle_parts:
        return []
    bundle = "\n".join(bundle_parts)
    found = []
    for slug, pat in _INTEGRATION_PATTERNS:
        if pat.search(bundle):
            found.append(slug)
    # If we got >=2 hits including "requests", drop "requests" — it's noise.
    if "requests" in found and len(found) > 1:
        found = [s for s in found if s != "requests"]
    return sorted(set(found))


def _filenames(files: Optional[list[dict]]) -> list[str]:
    if not files:
        return []
    out = []
    for f in files:
        if isinstance(f, dict):
            p = f.get("path")
            if isinstance(p, str) and p:
                out.append(p)
    return out


async def record_build_event(
    db,
    user_id: str,
    agent_id: str,
    *,
    event: str,                     # created | updated | published | archived
    name: str = "",
    description: str = "",
    integrations_used: Optional[list[str]] = None,
    files: Optional[list[str]] = None,
    status: str = "draft",
) -> None:
    """Upsert one entry in `agent_build_history.builds[]`. Never raises —
    audit + log on failure but keep the caller's flow intact."""
    if event not in VALID_EVENTS:
        logger.debug(f"[build_history] unknown event '{event}', ignored")
        return
    if not user_id or not agent_id:
        return
    if status not in VALID_STATUS:
        status = "draft"

    now = _now_iso()
    integrations = sorted(set(integrations_used or []))
    filenames = list(files or [])

    try:
        # Try to update an existing entry first (matches user_id + agent_id).
        res = await db.agent_build_history.update_one(
            {"user_id": user_id, "builds.agent_id": agent_id},
            {
                "$set": {
                    "builds.$.updated_at": now,
                    "builds.$.name": name or "",
                    "builds.$.description": description or "",
                    "builds.$.integrations_used": integrations,
                    "builds.$.files": filenames,
                    "builds.$.status": status,
                    "updated_at": now,
                },
            },
        )
        if res.matched_count == 0:
            # No existing entry — append a new one (upsert the parent doc if needed).
            entry = {
                "agent_id": agent_id,
                "name": name or "",
                "description": description or "",
                "built_at": now,
                "updated_at": now,
                "integrations_used": integrations,
                "files": filenames,
                "status": status,
            }
            await db.agent_build_history.update_one(
                {"user_id": user_id},
                {
                    "$set": {"user_id": user_id, "updated_at": now},
                    "$push": {"builds": entry},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

        # Audit
        try:
            from lib.memory_audit import log_memory_event
            await log_memory_event(
                user_id, "build_recorded",
                {"agent_id": agent_id, "event": event, "status": status,
                 "file_count": len(filenames),
                 "integration_count": len(integrations)},
                request=None,
            )
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[build_history] record failed: {type(e).__name__}: {str(e)[:120]}")


async def get_build_history(db, user_id: str) -> list[dict]:
    """Return `builds[]` for the user, newest-first. Empty list if no doc."""
    doc = await db.agent_build_history.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        return []
    builds = doc.get("builds") or []
    # Newest-updated first
    builds.sort(key=lambda b: b.get("updated_at") or b.get("built_at") or "", reverse=True)
    return builds


__all__ = ["record_build_event", "get_build_history", "detect_integrations", "VALID_EVENTS"]
