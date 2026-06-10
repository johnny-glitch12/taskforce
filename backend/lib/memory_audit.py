"""
Memory-system audit logger — Task Force AI

Writes builder-memory access / mutation events to the existing Supabase
`security_events` table with `event_kind="builder_memory"` so the events sit
alongside the firewall verdicts and security dashboard tooling already in
place. We deliberately reuse the existing table instead of introducing a
separate `audit_log` collection.

Graceful no-op when Supabase isn't configured (common in local dev). NEVER
logs raw memory content — only IDs, counts, and action metadata.

All action names are lower_snake_case constants — keep these stable, the
security dashboard groups events by `verdict`.
"""
import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

logger = logging.getLogger("memory_audit")

# ── Action vocabulary (whitelist) ───────────────────────────
ACTIONS = {
    "memory_read",
    "memory_updated",
    "memory_deleted",
    "memory_cleared",
    "memory_exported",
    "memory_access_denied",
    "memory_seeded",  # dev/test seed endpoint
}


def _client_ip(request: Optional[Request]) -> str:
    if request is None:
        return "unknown"
    fwd = request.headers.get("x-forwarded-for", "") if request.headers else ""
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _redact_details(details: dict) -> dict:
    """Defensive last-mile filter — drop any key that smells like raw content.
    Audit details should be metadata only (IDs, counts, types)."""
    if not isinstance(details, dict):
        return {}
    out = {}
    for k, v in details.items():
        kl = k.lower()
        if kl in {"content", "plaintext", "text", "raw", "value", "profile", "profile_data"}:
            continue
        out[k] = v
    return out


async def log_memory_event(
    user_id: str,
    action: str,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Fire-and-forget audit logger.

    Safe to await — never raises. When Supabase is not configured (the common
    case in local dev), this is a silent no-op. When Supabase is configured
    but the insert fails (network, schema mismatch, etc.) we log a warning
    and swallow the exception so the caller never sees a crash.

    Args:
        user_id:  caller's UUID — required, indexes the event.
        action:   one of ACTIONS above (gracefully accepted otherwise).
        details:  metadata dict — IDs, counts, types only. Content is stripped.
        request:  FastAPI Request for IP capture (optional).
    """
    if action not in ACTIONS:
        logger.debug(f"[memory_audit] unknown action '{action}' (still logged)")

    try:
        from routes.security import get_supabase  # noqa: WPS433 — lazy on purpose
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[memory_audit] supabase shim unavailable: {e}")
        return

    sb = get_supabase()
    if sb is None:
        # Supabase not configured (preview / local dev) — this is the expected,
        # silent path. Emit a debug line so operators can confirm calls are
        # reaching us when investigating.
        logger.debug(f"[memory_audit] noop (no Supabase) — action={action} user={user_id[:8]}")
        return

    payload = {
        "event_id": str(uuid.uuid4()),
        "executor_id": user_id,
        "event_type": "builder_memory",
        "event_kind": "builder_memory",  # discriminator field
        "verdict": action,
        "prompt_snippet": "",  # NEVER capture memory content
        "blocked": action == "memory_access_denied",
        "metadata": {
            **_redact_details(details or {}),
            "ip": _client_ip(request),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    def _do_insert():
        try:
            sb.table("security_events").insert(payload).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[memory_audit] insert failed: {type(e).__name__}: {e}")

    # Run the (blocking) Supabase HTTP call off the event loop so we don't
    # stall request handling.
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _do_insert)
    except RuntimeError:
        # Not in an event loop (e.g. called from a sync helper) — best effort.
        _do_insert()


__all__ = ["log_memory_event", "ACTIONS"]
