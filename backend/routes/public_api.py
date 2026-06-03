"""
Public API — minimal v1 (run + run history).

API-key authenticated. Rate limit: 60 req/min per key, in-memory token bucket.

Endpoints:
    User-facing key management (Bearer-auth via the regular JWT):
        POST   /api/keys                — mint a new key, returns the secret ONCE
        GET    /api/keys                — list keys (NO secrets returned)
        DELETE /api/keys/{key_id}       — revoke

    Public API (X-API-Key header):
        POST   /api/public/v1/deployments/{id}/run     — execute a deployment
        GET    /api/public/v1/deployments/{id}/runs    — list recent runs

Key format: tfai_<32 hex chars> — only the SHA256 hash is stored.

Rate limit: 60 req/min per key — sliding window via in-process collections.deque.
HA fan-out (Redis) is a future ENH; in-process is fine while we're single-replica.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

logger = logging.getLogger("public_api")
router = APIRouter()


# ── Rate limiter (in-process, sliding 60s window) ──────────────────────────
_rl_window_sec = 60
_rl_max_calls = 60
_rl_buckets: dict[str, deque] = defaultdict(deque)


def _rate_limit(key_id: str):
    """Sliding-window check. Raises 429 if exceeded, else records the call."""
    now = time.monotonic()
    bucket = _rl_buckets[key_id]
    cutoff = now - _rl_window_sec
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= _rl_max_calls:
        retry_after = int(_rl_window_sec - (now - bucket[0])) + 1
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Max {_rl_max_calls} requests per minute.",
                    "retry_after_seconds": retry_after},
        )
    bucket.append(now)


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id(u: dict) -> str:
    return str(u.get("id", u.get("email")))


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


# ── Key auth dependency ────────────────────────────────────────────────────
async def auth_via_api_key(x_api_key: Optional[str] = Header(default=None)):
    """FastAPI dep — resolves X-API-Key into the owning user. Raises 401 otherwise."""
    if not x_api_key or not x_api_key.startswith("tfai_"):
        raise HTTPException(status_code=401,
                            detail={"error": "MISSING_API_KEY",
                                    "message": "X-API-Key header is required (format: tfai_...)."})
    db = get_db()
    key_hash = _hash_key(x_api_key)
    key_doc = await db.api_keys.find_one({"key_hash": key_hash, "revoked": False})
    if not key_doc:
        raise HTTPException(status_code=401,
                            detail={"error": "INVALID_API_KEY",
                                    "message": "API key not recognised or revoked."})
    _rate_limit(key_doc["id"])
    # Touch last_used_at (best effort).
    await db.api_keys.update_one(
        {"id": key_doc["id"]},
        {"$set": {"last_used_at": _now()},
         "$inc": {"call_count": 1}},
    )
    user = await db.users.find_one({"id": key_doc["user_id"]})
    if not user:
        raise HTTPException(status_code=401,
                            detail={"error": "USER_NOT_FOUND",
                                    "message": "The key's owner no longer exists."})
    user["_via_api_key"] = key_doc["id"]
    return user


# ── Key management (JWT-protected) ─────────────────────────────────────────
@router.post("/keys")
async def mint_key(payload: Optional[dict] = None, user=Depends(get_current_user())):
    db = get_db()
    name = (payload or {}).get("name") or "Untitled key"
    name = str(name).strip()[:64] or "Untitled key"
    plaintext = f"tfai_{secrets.token_hex(32)}"
    key_id = uuid.uuid4().hex
    doc = {
        "id": key_id,
        "user_id": _user_id(user),
        "user_email": user.get("email"),
        "name": name,
        "key_prefix": plaintext[:12],  # tfai_xxxxxxx — shown for identification
        "key_hash": _hash_key(plaintext),
        "revoked": False,
        "created_at": _now(),
        "last_used_at": None,
        "call_count": 0,
    }
    await db.api_keys.insert_one(doc)
    return {
        "id": key_id,
        "name": name,
        "key": plaintext,  # SHOWN ONCE — never returned again
        "key_prefix": doc["key_prefix"],
        "created_at": doc["created_at"],
        "warning": "Copy this key now. It will not be shown again.",
    }


@router.get("/keys")
async def list_keys(user=Depends(get_current_user())):
    db = get_db()
    cursor = db.api_keys.find(
        {"user_id": _user_id(user), "revoked": False},
        {"_id": 0, "key_hash": 0},
    ).sort("created_at", -1)
    items = await cursor.to_list(length=200)
    return {"items": items}


@router.delete("/keys/{key_id}")
async def revoke_key(key_id: str, user=Depends(get_current_user())):
    db = get_db()
    r = await db.api_keys.update_one(
        {"id": key_id, "user_id": _user_id(user), "revoked": False},
        {"$set": {"revoked": True, "revoked_at": _now()}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Key not found or already revoked.")
    return {"success": True}


# ── Public API (X-API-Key) ─────────────────────────────────────────────────
@router.post("/public/v1/deployments/{deployment_id}/run")
async def public_run_deployment(deployment_id: str,
                                payload: Optional[dict] = None,
                                user=Depends(auth_via_api_key)):
    """Trigger a deployment run. Same logic as the in-app manual run but
    keyed off the API key's owning user. Body may include an optional
    `input` dict that is passed to the bot's main.py as INPUT."""
    from routes.credits_and_more import run_deployment_real
    db = get_db()
    user_id = _user_id(user)
    doc = await db.user_bot_deployments.find_one(
        {"id": deployment_id, "user_id": user_id},
    )
    if not doc:
        raise HTTPException(status_code=404,
                            detail={"error": "DEPLOYMENT_NOT_FOUND",
                                    "message": "Deployment not found or not owned by the key holder."})
    usage = doc.get("usage") or {}
    if usage.get("run_count", 0) >= usage.get("limit_per_month", 1000):
        raise HTTPException(status_code=429,
                            detail={"error": "RUN_LIMIT_REACHED",
                                    "message": f"Monthly run limit reached ({usage['run_count']}/{usage['limit_per_month']}). Upgrade this deployment to continue."})
    input_payload = (payload or {}).get("input") or {}
    if not isinstance(input_payload, dict):
        raise HTTPException(status_code=422,
                            detail={"error": "INVALID_INPUT", "message": "`input` must be a JSON object."})
    run = await run_deployment_real(db, doc, trigger="api", input_payload=input_payload)
    return {
        "run_id": run["id"],
        "success": bool(run.get("success")),
        "duration_ms": run.get("duration_ms"),
        "output": run.get("output"),
        "error": run.get("error"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
    }


@router.get("/public/v1/deployments/{deployment_id}/runs")
async def public_list_runs(deployment_id: str,
                           limit: int = Query(default=25, ge=1, le=100),
                           skip: int = Query(default=0, ge=0, le=5000),
                           user=Depends(auth_via_api_key)):
    db = get_db()
    user_id = _user_id(user)
    owner = await db.user_bot_deployments.find_one(
        {"id": deployment_id, "user_id": user_id}, {"_id": 0, "id": 1},
    )
    if not owner:
        raise HTTPException(status_code=404,
                            detail={"error": "DEPLOYMENT_NOT_FOUND"})
    cursor = db.deployment_runs.find(
        {"deployment_id": deployment_id}, {"_id": 0},
    ).sort("started_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.deployment_runs.count_documents({"deployment_id": deployment_id})
    return {"items": items, "total": total, "limit": limit, "skip": skip}


__all__ = ["router"]
