"""
Ownership guard — Task Force AI

Single-function module so any route handler can ensure a freshly fetched Mongo
doc belongs to the calling user. Returns the doc on success; raises 404 on
miss OR on cross-user attempt (NOT 403 — the 404 prevents information leak
about the existence of other users' records).
"""
from typing import Optional
from fastapi import HTTPException


def ensure_ownership(doc: Optional[dict], user_id: str) -> dict:
    """Raise 404 if doc is missing OR not owned by user_id. Returns doc otherwise.

    IMPORTANT: error message is identical for "not found" and "wrong owner" —
    do NOT branch on the cause in callers, do NOT log different messages for
    the two cases at INFO level. The audit log records the access-denied event
    separately at the route layer.
    """
    if doc is None or doc.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


__all__ = ["ensure_ownership"]
