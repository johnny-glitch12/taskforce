"""
Security Audit Log — Logs firewall verdicts to Supabase security_events table.
Provides GET endpoint for the Security Dashboard.
"""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
_sb = create_client(SUPABASE_URL, SUPABASE_KEY)

router = APIRouter()


def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


def log_security_event(executor_id: str, verdict: str, prompt_snippet: str, blocked: bool, metadata: dict = None):
    """Fire-and-forget logger for security events. Called from agent route."""
    try:
        _sb.table("security_events").insert({
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
        print(f"[SECURITY LOG ERROR] Failed to log event: {e}", flush=True)


@router.get("/security/events")
async def get_security_events(
    limit: int = Query(default=50, le=200),
    verdict: str = Query(default=None),
    user=Depends(get_current_user()),
):
    """Get security audit log events. Admin-only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    query = _sb.table("security_events").select("*").order("created_at", desc=True).limit(limit)

    if verdict:
        query = query.eq("verdict", verdict)

    result = query.execute()
    return {"events": result.data or [], "total": len(result.data or [])}


@router.get("/security/stats")
async def get_security_stats(user=Depends(get_current_user())):
    """Get aggregated security stats. Admin-only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    all_events = _sb.table("security_events").select("verdict,blocked").execute()
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
