"""
Gmail OAuth Routes — Task Force AI

Extracted from routes/workflow_executor.py. Endpoints:
    POST /api/workflows/credentials/gmail/exchange
    POST /api/workflows/credentials/gmail/refresh
"""
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lib.byok_crypto import encrypt_key, decrypt_key

router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


class GmailExchangeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    redirect_uri: str = Field(min_length=1, max_length=512)


@router.post("/workflows/credentials/gmail/exchange")
async def gmail_exchange(req: GmailExchangeRequest, user=Depends(get_current_user())):
    from lib.gmail_oauth import exchange_code_for_tokens
    try:
        tok = await exchange_code_for_tokens(req.code, req.redirect_uri)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {e.response.text[:200]}")

    if not tok.get("access_token"):
        raise HTTPException(status_code=400, detail="No access_token returned from Google.")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    now = datetime.now(timezone.utc).isoformat()

    await db.byok_credentials.update_one(
        {"user_id": user_id, "service": "gmail"},
        {
            "$set": {
                "api_key": encrypt_key(tok["access_token"]),
                "extra": {
                    "refresh_token": encrypt_key(tok.get("refresh_token") or ""),
                    "expires_at": tok.get("expires_at"),
                    "scope": tok.get("scope"),
                },
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return {"success": True, "service": "gmail", "expires_at": tok.get("expires_at")}


@router.post("/workflows/credentials/gmail/refresh")
async def gmail_refresh(user=Depends(get_current_user())):
    from lib.gmail_oauth import refresh_access_token
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cred = await db.byok_credentials.find_one({"user_id": user_id, "service": "gmail"})
    if not cred:
        raise HTTPException(status_code=404, detail="Gmail credential not found.")

    extra = cred.get("extra", {}) or {}
    enc_refresh = extra.get("refresh_token", "")
    refresh_tok = decrypt_key(enc_refresh) if enc_refresh else ""
    if not refresh_tok:
        raise HTTPException(status_code=400, detail="No refresh_token stored. Re-run /gmail/exchange.")

    try:
        tok = await refresh_access_token(refresh_tok)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"OAuth refresh failed: {e.response.text[:200]}")

    await db.byok_credentials.update_one(
        {"_id": cred["_id"]},
        {"$set": {
            "api_key": encrypt_key(tok["access_token"]),
            "extra.expires_at": tok.get("expires_at"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"success": True, "expires_at": tok.get("expires_at")}
