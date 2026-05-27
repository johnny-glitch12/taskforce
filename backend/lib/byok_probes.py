"""
BYOK Connection Probes

Each probe does ONE lightweight, idempotent API call to verify a stored
credential is alive — Telegram /getMe, Discord GET webhook, Stripe /balance,
etc. Probes never write data, never charge, never send messages.
Returns {ok: bool, status_code, detail, latency_ms}.
"""
import time
import httpx
from typing import Dict, Any

from lib.executor_security import validate_url

PROBE_TIMEOUT = 10


def _probe_result(ok: bool, status_code: int | None, detail: str, started: float) -> Dict[str, Any]:
    return {
        "ok": ok,
        "status_code": status_code,
        "detail": detail[:300],
        "latency_ms": int((time.time() - started) * 1000),
    }


async def probe_slack(api_key: str, extra: Dict) -> Dict[str, Any]:
    """Probe a Slack incoming webhook with an invalid payload — Slack will 400
    with 'invalid_payload' if the URL is valid, 404 if dead. Either confirms
    the webhook exists without delivering a real message."""
    started = time.time()
    if not api_key.startswith("https://"):
        return _probe_result(False, None, "Slack credential must be the full https:// webhook URL.", started)
    safe = validate_url(api_key)
    if not safe["safe"]:
        return _probe_result(False, None, f"SSRF: {safe['reason']}", started)
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT, follow_redirects=False) as c:
            # Empty body → Slack responds 'no_text' (400) for valid hooks,
            # 'no_service' (404) for dead ones.
            r = await c.post(api_key, content="")
            body = (r.text or "")[:120].lower()
            ok = r.status_code == 400 and "text" in body  # valid hook signature
            detail = "Webhook reachable" if ok else f"Slack: {body or r.status_code}"
            return _probe_result(ok, r.status_code, detail, started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_sendgrid(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return _probe_result(r.status_code == 200, r.status_code,
                                 "Profile fetched" if r.status_code == 200 else r.text[:200], started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_gmail(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return _probe_result(r.status_code == 200, r.status_code,
                                 "Profile fetched" if r.status_code == 200 else "Token rejected or expired",
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_telegram(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(f"https://api.telegram.org/bot{api_key}/getMe")
            j = r.json() if r.text else {}
            ok = bool(j.get("ok"))
            uname = (j.get("result") or {}).get("username")
            return _probe_result(ok, r.status_code,
                                 f"@{uname}" if uname else j.get("description", "unknown"), started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_discord(api_key: str, extra: Dict) -> Dict[str, Any]:
    """GET the webhook URL — Discord returns the webhook metadata for valid hooks."""
    started = time.time()
    if not api_key.startswith("https://"):
        return _probe_result(False, None, "Discord credential must be the full https:// webhook URL.", started)
    safe = validate_url(api_key)
    if not safe["safe"]:
        return _probe_result(False, None, f"SSRF: {safe['reason']}", started)
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT, follow_redirects=False) as c:
            r = await c.get(api_key)
            j = r.json() if r.text else {}
            ok = r.status_code == 200 and bool(j.get("id"))
            return _probe_result(ok, r.status_code,
                                 f"webhook '{j.get('name','?')}'" if ok else "Invalid webhook URL",
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_stripe(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get("https://api.stripe.com/v1/balance", auth=(api_key, ""))
            j = r.json() if r.text else {}
            ok = r.status_code == 200
            mode = "TEST" if api_key.startswith("sk_test_") else "LIVE"
            return _probe_result(ok, r.status_code,
                                 f"{mode} mode authenticated" if ok else j.get("error", {}).get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_notion(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://api.notion.com/v1/users/me",
                headers={"Authorization": f"Bearer {api_key}", "Notion-Version": "2022-06-28"},
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200
            return _probe_result(ok, r.status_code,
                                 j.get("name") or j.get("bot", {}).get("owner", {}).get("type") or "Authenticated"
                                 if ok else j.get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_gsheets(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://www.googleapis.com/oauth2/v1/tokeninfo",
                params={"access_token": api_key},
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200 and not j.get("error")
            return _probe_result(ok, r.status_code,
                                 f"scope: {j.get('scope', '')[:80]}" if ok else j.get("error_description", "Token rejected"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_twilio(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    sid = (extra or {}).get("account_sid")
    if not sid:
        return _probe_result(False, None, "Missing account_sid in extra.", started)
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
                auth=(sid, api_key),
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200
            return _probe_result(ok, r.status_code,
                                 f"account: {j.get('friendly_name', sid)}" if ok else j.get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_github(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/vnd.github+json"},
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200
            return _probe_result(ok, r.status_code,
                                 f"@{j.get('login','?')}" if ok else j.get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_openai(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200
            count = len(j.get("data") or [])
            return _probe_result(ok, r.status_code,
                                 f"{count} models available" if ok else j.get("error", {}).get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_anthropic(api_key: str, extra: Dict) -> Dict[str, Any]:
    """Anthropic has no /me — fire a 1-token messages call to verify auth."""
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-haiku-4-5", "max_tokens": 1, "messages": [{"role": "user", "content": "."}]},
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200
            return _probe_result(ok, r.status_code,
                                 "Authenticated" if ok else j.get("error", {}).get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_instagram(api_key: str, extra: Dict) -> Dict[str, Any]:
    """Probe the Instagram Graph access token by fetching /me."""
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as c:
            r = await c.get(
                "https://graph.facebook.com/v19.0/me",
                params={"fields": "id,username", "access_token": api_key},
            )
            j = r.json() if r.text else {}
            ok = r.status_code == 200 and not j.get("error")
            uname = j.get("username") or j.get("id")
            return _probe_result(ok, r.status_code,
                                 f"@{uname}" if uname else j.get("error", {}).get("message", "Auth failed"),
                                 started)
    except Exception as e:
        return _probe_result(False, None, f"Network: {e}", started)


async def probe_postgres(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        import asyncpg
        conn = await asyncpg.connect(api_key, timeout=8)
        try:
            v = await conn.fetchval("SELECT version()")
            return _probe_result(True, 200, str(v)[:120], started)
        finally:
            await conn.close()
    except ImportError:
        return _probe_result(False, None, "asyncpg not installed", started)
    except Exception as e:
        return _probe_result(False, None, f"Connection failed: {e}", started)


async def probe_mongodb(api_key: str, extra: Dict) -> Dict[str, Any]:
    started = time.time()
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(api_key, serverSelectionTimeoutMS=5000)
        try:
            info = await client.server_info()
            return _probe_result(True, 200, f"MongoDB {info.get('version', '?')}", started)
        finally:
            client.close()
    except Exception as e:
        return _probe_result(False, None, f"Connection failed: {e}", started)


PROBES = {
    "slack":     probe_slack,
    "sendgrid":  probe_sendgrid,
    "gmail":     probe_gmail,
    "telegram":  probe_telegram,
    "discord":   probe_discord,
    "stripe":    probe_stripe,
    "notion":    probe_notion,
    "gsheets":   probe_gsheets,
    "twilio":    probe_twilio,
    "github":    probe_github,
    "openai":    probe_openai,
    "anthropic": probe_anthropic,
    "instagram": probe_instagram,
    "postgres":  probe_postgres,
    "mongodb":   probe_mongodb,
}
