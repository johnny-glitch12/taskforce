"""
Native Workflow Node Handlers — Task Force AI

Extracted from routes/workflow_executor.py to keep route files thin.
Each handler is async, accepts (node, prev_output, ctx) and returns a result dict:
    {status: "ok"|"error"|"skipped", output: Any, log: str, ...extra}

`ctx` carries per-execution state:
    - db: AsyncIOMotor database
    - user_id: str
    - byok: dict mapping credential name -> {type, data}
"""
import os
import json
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, Any

from lib.executor_security import validate_url
from lib.workflow_sandbox import execute_sandboxed

HTTP_TIMEOUT = 15
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


# ─────────────────────────────────────────────────────────────
# Trigger
# ─────────────────────────────────────────────────────────────
async def handle_trigger(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    data = node.get("data", {}) or {}
    payload = data.get("payload") or prev_output or {"triggered_at": datetime.now(timezone.utc).isoformat()}
    return {"status": "ok", "output": payload, "log": f"Trigger fired ({data.get('source', 'manual')})"}


# ─────────────────────────────────────────────────────────────
# HTTP Request (SSRF-protected)
# ─────────────────────────────────────────────────────────────
async def handle_http_request(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    data = node.get("data", {}) or {}
    url = data.get("url", "")
    method = (data.get("method") or "GET").upper()
    headers = data.get("headers", {}) or {}
    body = data.get("body") or prev_output

    if not url:
        return {"status": "error", "output": None, "log": "No URL configured."}

    validation = validate_url(url)
    if not validation["safe"]:
        return {"status": "error", "output": None, "log": f"SSRF blocked: {validation['reason']}"}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            req_kwargs = {"headers": headers}
            if method in ("POST", "PUT", "PATCH") and body:
                if isinstance(body, (dict, list)):
                    req_kwargs["json"] = body
                else:
                    req_kwargs["content"] = str(body)
            res = await client.request(method, url, **req_kwargs)
            text_preview = res.text[:5000]
            try:
                parsed = res.json()
            except Exception:
                parsed = text_preview
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": parsed,
                "log": f"{method} {url} → {res.status_code}",
                "http_status": res.status_code,
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"HTTP error: {str(e)[:200]}"}


# ─────────────────────────────────────────────────────────────
# Condition (safe expression eval)
# ─────────────────────────────────────────────────────────────
def _safe_eval_condition(expr: str, context: Dict) -> bool:
    if not expr or expr in ("true", "True", "1"):
        return True
    if expr in ("false", "False", "0"):
        return False
    code = f"RESULT = bool({expr})"
    result = execute_sandboxed(code, input_data=context, timeout=5)
    if result.get("success"):
        return bool(result.get("result"))
    return False


async def handle_condition(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    data = node.get("data", {}) or {}
    expr = data.get("condition", "true")
    context = prev_output if isinstance(prev_output, dict) else {"INPUT": prev_output}
    branch = _safe_eval_condition(expr, context)
    return {
        "status": "ok",
        "output": prev_output,
        "branch": "true" if branch else "false",
        "log": f"Condition '{expr}' → {branch}",
    }


# ─────────────────────────────────────────────────────────────
# Transform (RestrictedPython sandbox)
# ─────────────────────────────────────────────────────────────
async def handle_transform(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    data = node.get("data", {}) or {}
    code = data.get("code", "RESULT = INPUT")
    result = execute_sandboxed(code, input_data=prev_output, timeout=10)
    if result.get("success"):
        return {
            "status": "ok",
            "output": result.get("result") if result.get("result") is not None else prev_output,
            "log": f"Transform executed in {result.get('duration_ms', 0)}ms",
        }
    return {"status": "error", "output": None, "log": f"Transform failed: {result.get('error', 'unknown')}"}


# ─────────────────────────────────────────────────────────────
# LLM (platform Gemini 2.5 Flash, no BYOK in v1)
# ─────────────────────────────────────────────────────────────
async def handle_llm(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    if not EMERGENT_LLM_KEY:
        return {"status": "error", "output": None, "log": "Emergent LLM Key not configured."}

    data = node.get("data", {}) or {}
    prompt_template = data.get("prompt", "Summarize the input.")
    if isinstance(prev_output, (dict, list)):
        input_str = json.dumps(prev_output)[:3000]
    else:
        input_str = str(prev_output or "")[:3000]

    user_message = f"{prompt_template}\n\nINPUT DATA:\n{input_str}"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"workflow-{node.get('id', uuid.uuid4().hex[:8])}",
            system_message="You are a workflow node. Respond concisely with structured output.",
        )
        chat.with_model("gemini", "gemini-2.5-flash")
        msg = UserMessage(text=user_message)
        response = await chat.send_message(msg)
        return {
            "status": "ok",
            "output": {"llm_response": response, "model": "gemini-2.5-flash"},
            "log": f"LLM responded ({len(response)} chars)",
        }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"LLM error: {str(e)[:200]}"}


# ─────────────────────────────────────────────────────────────
# Webhook outbound
# ─────────────────────────────────────────────────────────────
async def handle_webhook(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    data = node.get("data", {}) or {}
    url = data.get("url", "")
    if not url:
        return {"status": "ok", "output": prev_output, "log": "Webhook (inbound stub)"}

    validation = validate_url(url)
    if not validation["safe"]:
        return {"status": "error", "output": None, "log": f"SSRF blocked: {validation['reason']}"}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            res = await client.post(url, json=prev_output if isinstance(prev_output, (dict, list)) else {"data": prev_output})
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": {"webhook_delivered": True, "http_status": res.status_code},
                "log": f"Webhook POST {url} → {res.status_code}",
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"Webhook error: {str(e)[:200]}"}


# ─────────────────────────────────────────────────────────────
# BYOK Action handlers — gmail / slack / sendgrid
# Stored creds: db.byok_credentials { user_id, service, api_key, extra }
# ─────────────────────────────────────────────────────────────
async def _load_byok(ctx: Dict, service: str) -> Dict | None:
    db = ctx.get("db")
    user_id = ctx.get("user_id")
    if db is None or not user_id:
        return None
    cred = await db.byok_credentials.find_one({"user_id": user_id, "service": service})
    if cred and cred.get("api_key"):
        # Decrypt stored credential (handles both encrypted and legacy plaintext)
        from lib.byok_crypto import decrypt_key
        cred["api_key"] = decrypt_key(cred["api_key"])
    return cred


async def _action_slack(node_data: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    """Post to Slack via incoming webhook URL stored in BYOK."""
    cred = await _load_byok(ctx, "slack")
    if not cred or not cred.get("api_key"):
        return {"status": "error", "output": None, "log": "Slack BYOK not configured. Add a Slack webhook URL in /credentials."}
    webhook_url = cred["api_key"]
    validation = validate_url(webhook_url)
    if not validation["safe"]:
        return {"status": "error", "output": None, "log": f"SSRF blocked Slack webhook: {validation['reason']}"}

    text = node_data.get("text") or (json.dumps(prev_output)[:2000] if prev_output else "Workflow notification")
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            res = await client.post(webhook_url, json={"text": text})
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": {"slack_delivered": res.status_code < 400, "http_status": res.status_code},
                "log": f"Slack post → {res.status_code}",
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"Slack error: {str(e)[:200]}"}


async def _action_sendgrid(node_data: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    """Send email via SendGrid API."""
    cred = await _load_byok(ctx, "sendgrid")
    if not cred or not cred.get("api_key"):
        return {"status": "error", "output": None, "log": "SendGrid BYOK not configured. Add an API key in /credentials."}
    api_key = cred["api_key"]
    from_email = (cred.get("extra") or {}).get("from_email") or node_data.get("from_email")
    if not from_email:
        return {"status": "error", "output": None, "log": "Missing 'from_email' in credentials.extra or node config."}

    to = node_data.get("to")
    subject = node_data.get("subject", "Workflow notification")
    body_text = node_data.get("body") or (json.dumps(prev_output)[:5000] if prev_output else "")

    if not to:
        return {"status": "error", "output": None, "log": "Missing 'to' in node config."}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": from_email},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body_text}],
                },
            )
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": {"email_sent": res.status_code < 400, "http_status": res.status_code, "to": to},
                "log": f"SendGrid → {res.status_code}",
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"SendGrid error: {str(e)[:200]}"}


async def _action_gmail(node_data: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    """
    Gmail action — sends email via Gmail API. Auto-refreshes access_token if expired
    when a refresh_token + GOOGLE_CLIENT_ID/SECRET are available.
    """
    cred = await _load_byok(ctx, "gmail")
    if not cred or not cred.get("api_key"):
        return {"status": "error", "output": None, "log": "Gmail BYOK not configured. POST /api/workflows/credentials/gmail/exchange to authorize."}

    access_token = cred["api_key"]  # already decrypted by _load_byok

    # Try a proactive refresh if expires_at is in the past
    extra = cred.get("extra") or {}
    import time as _t
    if extra.get("expires_at") and int(extra["expires_at"]) < int(_t.time()):
        enc_refresh = extra.get("refresh_token", "")
        if enc_refresh and os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"):
            try:
                from lib.byok_crypto import decrypt_key, encrypt_key
                from lib.gmail_oauth import refresh_access_token
                refresh_tok = decrypt_key(enc_refresh)
                if refresh_tok:
                    tok = await refresh_access_token(refresh_tok)
                    access_token = tok["access_token"]
                    db = ctx.get("db")
                    user_id = ctx.get("user_id")
                    if db is not None and user_id:
                        await db.byok_credentials.update_one(
                            {"user_id": user_id, "service": "gmail"},
                            {"$set": {
                                "api_key": encrypt_key(access_token),
                                "extra.expires_at": tok.get("expires_at"),
                            }},
                        )
            except Exception:
                # Fall through with the (likely expired) token; Gmail will 401
                pass

    to = node_data.get("to")
    subject = node_data.get("subject", "Workflow notification")
    body_text = node_data.get("body") or (json.dumps(prev_output)[:5000] if prev_output else "")

    if not to:
        return {"status": "error", "output": None, "log": "Missing 'to' in node config."}

    import base64
    raw_msg = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body_text}".encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw_msg).decode().rstrip("=")

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"raw": encoded},
            )
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": {"email_sent": res.status_code < 400, "http_status": res.status_code, "to": to},
                "log": f"Gmail → {res.status_code}",
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"Gmail error: {str(e)[:200]}"}


async def handle_action(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    """
    Dispatcher for action nodes. data.service controls behaviour:
        - "slack"     → post to Slack incoming webhook (BYOK)
        - "sendgrid"  → send email (BYOK)
        - "gmail"     → send email via Gmail API token (BYOK)
        - other       → v1 stub (logged pass-through)
    """
    data = node.get("data", {}) or {}
    service = (data.get("service") or "").lower()
    if "slack" in service:
        return await _action_slack(data, prev_output, ctx)
    if "sendgrid" in service or service == "email":
        return await _action_sendgrid(data, prev_output, ctx)
    if "gmail" in service:
        return await _action_gmail(data, prev_output, ctx)

    return {
        "status": "skipped",
        "output": prev_output,
        "log": f"[action:{service or 'unknown'}] not executed in v1 — pass-through",
        "not_executed_v1": True,
    }


async def handle_database(node: Dict, prev_output: Any, ctx: Dict) -> Dict[str, Any]:
    return {
        "status": "skipped",
        "output": prev_output,
        "log": "[database] not executed in v1 — pass-through",
        "not_executed_v1": True,
    }


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────
HANDLERS = {
    "trigger": handle_trigger,
    "http_request": handle_http_request,
    "condition": handle_condition,
    "transform": handle_transform,
    "llm": handle_llm,
    "webhook": handle_webhook,
    "action": handle_action,
    "database": handle_database,
}


SUPPORTED_BYOK_SERVICES = ["slack", "sendgrid", "gmail"]
