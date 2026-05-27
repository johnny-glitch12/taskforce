"""
Gmail OAuth helper — Task Force AI

Implements the Google OAuth refresh-token flow used by the gmail BYOK action.
Stores both access_token (api_key field) and refresh_token (extra.refresh_token)
encrypted via lib/byok_crypto, plus extra.expires_at.

Endpoints (mounted by workflow_executor router):
    POST /api/workflows/credentials/gmail/exchange  { code, redirect_uri }
        → exchanges OAuth `code` for access+refresh tokens, stores both.
    POST /api/workflows/credentials/gmail/refresh
        → refreshes a near-expiring access_token using stored refresh_token.

Env:
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
"""
import os
import time
import httpx

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """Exchange an OAuth authorization code for access + refresh tokens."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not configured. "
            "Add them to backend/.env to enable Gmail OAuth."
        )

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        res.raise_for_status()
        tok = res.json()
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token"),
            "expires_in": tok.get("expires_in", 3600),
            "expires_at": int(time.time()) + int(tok.get("expires_in", 3600)) - 60,
            "scope": tok.get("scope"),
        }


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an access token. Returns the new access_token + new expiry."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not configured."
        )

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(GOOGLE_TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })
        res.raise_for_status()
        tok = res.json()
        return {
            "access_token": tok.get("access_token"),
            "expires_in": tok.get("expires_in", 3600),
            "expires_at": int(time.time()) + int(tok.get("expires_in", 3600)) - 60,
        }
