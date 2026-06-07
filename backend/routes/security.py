"""
Security Audit Log — Logs firewall verdicts to Supabase security_events table.
Provides GET endpoint for the Security Dashboard.

Supabase is LAZY-initialised: when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are
unset (common on local dev and on Railway until a Supabase project is wired up),
this module imports cleanly and the audit features no-op with a warning instead
of crashing the whole app at startup.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_sb = None
_sb_init_attempted = False


def get_supabase():
    """Return a Supabase client lazily. None when not configured."""
    global _sb, _sb_init_attempted
    if _sb is not None:
        return _sb
    if _sb_init_attempted:
        return None
    _sb_init_attempted = True

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.warning("[security] Supabase not configured — security audit logging disabled")
        return None
    try:
        from supabase import create_client  # noqa: WPS433 — lazy import on purpose
        _sb = create_client(url, key)
        return _sb
    except Exception as exc:
        logger.warning(f"[security] Supabase init failed ({type(exc).__name__}): {exc} — audit logging disabled")
        return None


router = APIRouter()


def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


def log_security_event(executor_id: str, verdict: str, prompt_snippet: str, blocked: bool, metadata: dict = None):
    """Fire-and-forget logger for security events. Called from agent route."""
    sb = get_supabase()
    if sb is None:
        return  # Silently no-op when Supabase isn't configured.
    try:
        sb.table("security_events").insert({
            "event_id": str(uuid.uuid4()),
            "executor_id": executor_id,
            "event_type": "firewall_audit",
            "verdict": verdict,
            "prompt_snippet": prompt_snippet[:200] if prompt_snippet else "",
            "blocked": blocked,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning(f"[security] failed to log event: {e}")


@router.get("/security/events")
async def get_security_events(
    limit: int = Query(default=50, le=200),
    verdict: str = Query(default=None),
    user=Depends(get_current_user()),
):
    """Get security audit log events. Admin-only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="Security audit logging not configured.")

    query = sb.table("security_events").select("*").order("created_at", desc=True).limit(limit)
    if verdict:
        query = query.eq("verdict", verdict)

    result = query.execute()
    return {"events": result.data or [], "total": len(result.data or [])}


@router.get("/security/stats")
async def get_security_stats(user=Depends(get_current_user())):
    """Get aggregated security stats. Admin-only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="Security audit logging not configured.")

    all_events = sb.table("security_events").select("verdict,blocked").execute()
    events = all_events.data or []

    total = len(events)
    blocked = sum(1 for e in events if e.get("blocked"))
    safe = sum(1 for e in events if e.get("verdict") == "SAFE")
    suspicious = sum(1 for e in events if e.get("verdict") == "SUSPICIOUS")
    unsafe = sum(1 for e in events if e.get("verdict") == "UNSAFE")

    return {
        "total_audits": total,
        "blocked": blocked,
        "safe": safe,
        "suspicious": suspicious,
        "unsafe": unsafe,
    }
