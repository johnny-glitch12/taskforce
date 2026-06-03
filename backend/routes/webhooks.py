"""
External Webhooks — POST /api/webhooks/{deployment_id}

Lets deployed bots be triggered by external services (Stripe, GitHub, Zapier,
custom integrations). Each deployment auto-gets a stable webhook_key on first
deploy; the URL pattern is:

    POST /api/webhooks/{deployment_id}?key={webhook_key}

Optional HMAC-SHA256 signature verification via the `X-Signature` header (the
caller signs the raw body with `webhook_secret`). Useful for Stripe/GitHub.

The webhook persists an immutable `webhook_events` row, then triggers a
deployment run via the same real-runtime path used by the dashboard.
"""
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter()


def get_db():
    from server import db
    return db


def get_current_user():
    from server import get_current_user as _u
    return _u


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _ensure_webhook_keys(db, deployment: dict) -> dict:
    """Auto-create webhook_key + webhook_secret on first webhook call."""
    if deployment.get("webhook_key") and deployment.get("webhook_secret"):
        return deployment
    webhook_key = secrets.token_urlsafe(16)
    webhook_secret = secrets.token_urlsafe(32)
    await db.user_bot_deployments.update_one(
        {"id": deployment["id"]},
        {"$set": {"webhook_key": webhook_key, "webhook_secret": webhook_secret, "updated_at": _now()}},
    )
    deployment["webhook_key"] = webhook_key
    deployment["webhook_secret"] = webhook_secret
    return deployment


@router.get("/deployments/{deployment_id}/webhook")
async def get_webhook_info(deployment_id: str, user=Depends(get_current_user())):
    """Return the webhook URL + secret for a user's deployment. Auto-creates on first call."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    dep = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id})
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    dep = await _ensure_webhook_keys(db, dep)
    from os import environ
    public_host = environ.get("PUBLIC_BACKEND_URL") or ""
    return {
        "deployment_id": deployment_id,
        "webhook_url": f"{public_host}/api/webhooks/{deployment_id}?key={dep['webhook_key']}",
        "webhook_key": dep["webhook_key"],
        "webhook_secret": dep["webhook_secret"],
        "signature_header": "X-Signature",
        "signature_algorithm": "hmac-sha256",
        "note": "Send POST with raw body. Optional: include X-Signature: hex(hmac_sha256(secret, body)) for verification.",
    }


@router.post("/deployments/{deployment_id}/webhook/rotate")
async def rotate_webhook(deployment_id: str, user=Depends(get_current_user())):
    """Rotate the webhook key + secret (invalidates all in-flight integrations)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    dep = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id})
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    new_key = secrets.token_urlsafe(16)
    new_secret = secrets.token_urlsafe(32)
    await db.user_bot_deployments.update_one(
        {"id": deployment_id},
        {"$set": {"webhook_key": new_key, "webhook_secret": new_secret, "updated_at": _now()}},
    )
    return {"webhook_key": new_key, "webhook_secret": new_secret}


@router.post("/webhooks/{deployment_id}")
async def fire_webhook(deployment_id: str, request: Request):
    """Public webhook receiver. Authenticated by ?key= query param + optional HMAC."""
    db = get_db()
    key = request.query_params.get("key", "")
    dep = await db.user_bot_deployments.find_one({"id": deployment_id})
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if not dep.get("webhook_key") or not hmac.compare_digest(dep["webhook_key"], key):
        raise HTTPException(status_code=401, detail="Invalid webhook key.")

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8", errors="ignore")[:50_000]
    sig_header = request.headers.get("X-Signature") or request.headers.get("x-signature")

    sig_valid = None
    if sig_header and dep.get("webhook_secret"):
        expected = hmac.new(dep["webhook_secret"].encode(), raw_body, hashlib.sha256).hexdigest()
        sig_valid = hmac.compare_digest(expected, sig_header.strip())
        if not sig_valid:
            raise HTTPException(status_code=401, detail="X-Signature mismatch.")

    # Parse JSON body if possible
    try:
        payload = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        payload = {"raw": body_text}

    # Rate-limit by per-deployment monthly cap (same as /run).
    usage = dep.get("usage") or {}
    if usage.get("run_count", 0) >= usage.get("limit_per_month", 1000):
        await db.webhook_events.insert_one({
            "id": uuid.uuid4().hex, "deployment_id": deployment_id,
            "user_id": dep["user_id"], "received_at": _now(),
            "status": "rate_limited", "payload_preview": body_text[:500],
        })
        return {"received": True, "executed": False, "error": "LIMIT_REACHED"}

    # Persist the event
    event_id = uuid.uuid4().hex
    await db.webhook_events.insert_one({
        "id": event_id, "deployment_id": deployment_id, "user_id": dep["user_id"],
        "received_at": _now(), "status": "queued",
        "headers": {k: v for k, v in request.headers.items() if k.lower() not in {"authorization", "cookie"}},
        "payload_preview": body_text[:1500],
        "signature_verified": sig_valid,
    })

    # Trigger real execution (delegates to credits_and_more.run_deployment_now).
    from routes.credits_and_more import run_deployment_real
    result = await run_deployment_real(db, dep, trigger="webhook", input_payload=payload)
    run_id_val = result.get("run_id") or result.get("id")
    await db.webhook_events.update_one(
        {"id": event_id},
        {"$set": {"status": "success" if result.get("success") else "failed",
                  "run_id": run_id_val, "duration_ms": result.get("duration_ms"),
                  "completed_at": _now()}},
    )
    return {
        "received": True, "executed": True, "event_id": event_id,
        "run_id": run_id_val, "duration_ms": result.get("duration_ms"),
        "success": result.get("success"),
        "output_preview": (result.get("output") or "")[:1000] if result.get("output") else None,
    }


@router.get("/deployments/{deployment_id}/webhook/events")
async def list_webhook_events(deployment_id: str, limit: int = 30, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    dep = await db.user_bot_deployments.find_one({"id": deployment_id, "user_id": user_id}, {"id": 1})
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    limit = max(1, min(100, int(limit)))
    cursor = db.webhook_events.find(
        {"deployment_id": deployment_id}, {"_id": 0}
    ).sort("received_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    return {"events": items}
