"""
Per-service workflow action handlers (real implementations).

Each handler is async, takes (node_data: dict, prev_output: Any, ctx: dict) and
returns {status, output, log, ...}. Mirrors the shape of the older
slack/sendgrid/gmail handlers in workflow_handlers.py.

Credentials are loaded via _load_byok(ctx, service) from workflow_handlers — the
caller passes the same ctx in. Each service expects specific fields in
byok.api_key + byok.extra:

    instagram : api_key=long_lived_access_token, extra={ig_user_id}
    stripe    : api_key=sk_test_or_live
    telegram  : api_key=bot_token, extra={default_chat_id?}
    discord   : api_key=incoming_webhook_url
    notion    : api_key=integration_secret
    gsheets   : api_key=oauth_access_token, extra={refresh_token?, expires_at?}
    twilio    : api_key=auth_token, extra={account_sid, from_number}
    openai    : api_key=sk-...
    anthropic : api_key=sk-ant-...
    postgres  : api_key=postgres dsn (postgres://user:pass@host:port/db)
    mongodb   : api_key=mongo connection string
    github    : api_key=PAT (ghp_...)
"""
import os
import json
import base64
import httpx
from typing import Dict, Any

from lib.executor_security import validate_url

HTTP_TIMEOUT = 20


def _err(log: str):
    return {"status": "error", "output": None, "log": log[:300]}


def _ok(output, log: str, **extra):
    return {"status": "ok", "output": output, "log": log[:300], **extra}


async def _load_byok(ctx: Dict, service: str):
    """Local copy of the byok loader to avoid circular import."""
    db = ctx.get("db")
    user_id = ctx.get("user_id")
    if db is None or not user_id:
        return None
    cred = await db.byok_credentials.find_one({"user_id": user_id, "service": service})
    if cred and cred.get("api_key"):
        from lib.byok_crypto import decrypt_key
        cred["api_key"] = decrypt_key(cred["api_key"])
    return cred


# ── Instagram (Graph API) ────────────────────────────────────────
async def action_instagram(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "instagram")
    if not cred or not cred.get("api_key"):
        return _err("Instagram BYOK missing. Add a long-lived access token in /credentials (extra={ig_user_id}).")
    token = cred["api_key"]
    ig_user_id = (cred.get("extra") or {}).get("ig_user_id") or node_data.get("ig_user_id")
    if not ig_user_id:
        return _err("Missing ig_user_id (set in BYOK extra or node config).")
    op = (node_data.get("op") or "post").lower()
    if op == "post":
        image_url = node_data.get("image_url") or (prev_output.get("image_url") if isinstance(prev_output, dict) else None)
        caption = node_data.get("caption") or (prev_output.get("caption") if isinstance(prev_output, dict) else "")
        if not image_url:
            return _err("Instagram post requires 'image_url'.")
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Step 1: create media container
                r1 = await client.post(
                    f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
                    params={"image_url": image_url, "caption": caption, "access_token": token},
                )
                if r1.status_code >= 400:
                    return _err(f"IG create container {r1.status_code}: {r1.text[:200]}")
                container_id = r1.json().get("id")
                # Step 2: publish
                r2 = await client.post(
                    f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
                    params={"creation_id": container_id, "access_token": token},
                )
                ok = r2.status_code < 400
                return {"status": "ok" if ok else "error",
                        "output": {"ig_post_id": r2.json().get("id") if ok else None, "http_status": r2.status_code},
                        "log": f"Instagram post → {r2.status_code}"}
        except Exception as e:
            return _err(f"Instagram error: {e}")
    if op == "dm":
        recipient_id = node_data.get("recipient_id")
        text = node_data.get("text") or "Hello"
        if not recipient_id:
            return _err("Instagram DM requires 'recipient_id'.")
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                r = await client.post(
                    f"https://graph.facebook.com/v19.0/{ig_user_id}/messages",
                    params={"access_token": token},
                    json={"recipient": {"id": recipient_id}, "message": {"text": text}},
                )
                ok = r.status_code < 400
                return {"status": "ok" if ok else "error",
                        "output": {"http_status": r.status_code, "response": r.text[:300]},
                        "log": f"Instagram DM → {r.status_code}"}
        except Exception as e:
            return _err(f"Instagram DM error: {e}")
    return _err(f"Unknown Instagram op: {op}")


# ── Stripe (charges / refunds / subscriptions) ───────────────────
async def action_stripe(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "stripe")
    api_key = (cred or {}).get("api_key") or os.environ.get("STRIPE_API_KEY")
    if not api_key:
        return _err("Stripe BYOK missing. Add sk_test_... to /credentials (service=stripe).")
    op = (node_data.get("op") or "charge").lower()
    endpoint, form = None, {}
    if op == "charge" or op == "payment_intent":
        amount = int(float(node_data.get("amount") or 100) * 100)  # dollars→cents
        currency = (node_data.get("currency") or "usd").lower()
        customer = node_data.get("customer_id")
        endpoint = "https://api.stripe.com/v1/payment_intents"
        form = {"amount": str(amount), "currency": currency, "automatic_payment_methods[enabled]": "true"}
        if customer:
            form["customer"] = customer
    elif op == "refund":
        pi = node_data.get("payment_intent_id") or (prev_output.get("id") if isinstance(prev_output, dict) else None)
        if not pi:
            return _err("Stripe refund requires payment_intent_id.")
        endpoint = "https://api.stripe.com/v1/refunds"
        form = {"payment_intent": pi}
    elif op == "subscription":
        customer = node_data.get("customer_id")
        price = node_data.get("price_id")
        if not customer or not price:
            return _err("Stripe subscription requires customer_id + price_id.")
        endpoint = "https://api.stripe.com/v1/subscriptions"
        form = {"customer": customer, "items[0][price]": price}
    elif op == "customer":
        endpoint = "https://api.stripe.com/v1/customers"
        form = {"email": node_data.get("email", ""), "name": node_data.get("name", "")}
    else:
        return _err(f"Unknown Stripe op: {op}")
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(endpoint, data=form, auth=(api_key, ""))
            data = r.json() if r.text else {}
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"stripe_op": op, "id": data.get("id"), "data": data, "http_status": r.status_code},
                    "log": f"Stripe {op} → {r.status_code}"}
    except Exception as e:
        return _err(f"Stripe error: {e}")


# ── Telegram bot send message ────────────────────────────────────
async def action_telegram(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "telegram")
    if not cred or not cred.get("api_key"):
        return _err("Telegram BYOK missing. Add bot_token to /credentials (extra={default_chat_id?}).")
    token = cred["api_key"]
    chat_id = node_data.get("chat_id") or (cred.get("extra") or {}).get("default_chat_id")
    if not chat_id:
        return _err("Telegram requires chat_id.")
    text = node_data.get("text") or (json.dumps(prev_output)[:3500] if prev_output else "")
    parse_mode = node_data.get("parse_mode")
    payload = {"chat_id": str(chat_id), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
            data = r.json() if r.text else {}
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"message_id": data.get("result", {}).get("message_id"), "http_status": r.status_code},
                    "log": f"Telegram → {r.status_code}"}
    except Exception as e:
        return _err(f"Telegram error: {e}")


# ── Discord webhook ──────────────────────────────────────────────
async def action_discord(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "discord")
    webhook_url = node_data.get("webhook_url") or (cred or {}).get("api_key")
    if not webhook_url:
        return _err("Discord webhook URL missing. Add to /credentials (api_key=webhook URL).")
    safe = validate_url(webhook_url)
    if not safe["safe"]:
        return _err(f"SSRF blocked Discord webhook: {safe['reason']}")
    content = node_data.get("content") or (json.dumps(prev_output)[:1900] if prev_output else "Workflow notification")
    username = node_data.get("username") or "Task Force AI"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(webhook_url, json={"content": content[:2000], "username": username})
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"http_status": r.status_code},
                    "log": f"Discord → {r.status_code}"}
    except Exception as e:
        return _err(f"Discord error: {e}")


# ── Notion (page CRUD) ───────────────────────────────────────────
async def action_notion(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "notion")
    if not cred or not cred.get("api_key"):
        return _err("Notion BYOK missing. Add integration secret to /credentials (service=notion).")
    token = cred["api_key"]
    op = (node_data.get("op") or "create").lower()
    hdrs = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=hdrs) as client:
            if op == "create":
                parent_db = node_data.get("database_id")
                if not parent_db:
                    return _err("Notion create requires database_id.")
                title = node_data.get("title") or "New entry from Task Force"
                payload = {
                    "parent": {"database_id": parent_db},
                    "properties": {"Name": {"title": [{"text": {"content": title}}]}},
                }
                # Optional extra properties dict (string → string)
                for k, v in (node_data.get("properties") or {}).items():
                    payload["properties"][k] = {"rich_text": [{"text": {"content": str(v)}}]}
                r = await client.post("https://api.notion.com/v1/pages", json=payload)
            elif op == "update":
                page_id = node_data.get("page_id")
                if not page_id:
                    return _err("Notion update requires page_id.")
                r = await client.patch(f"https://api.notion.com/v1/pages/{page_id}",
                                       json={"properties": node_data.get("properties") or {}})
            elif op == "query":
                db_id = node_data.get("database_id")
                if not db_id:
                    return _err("Notion query requires database_id.")
                r = await client.post(f"https://api.notion.com/v1/databases/{db_id}/query", json={})
            else:
                return _err(f"Unknown Notion op: {op}")
            data = r.json() if r.text else {}
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"notion_op": op, "id": data.get("id"), "data": data, "http_status": r.status_code},
                    "log": f"Notion {op} → {r.status_code}"}
    except Exception as e:
        return _err(f"Notion error: {e}")


# ── Google Sheets (append row) ───────────────────────────────────
async def action_gsheets(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "gsheets")
    if not cred or not cred.get("api_key"):
        return _err("Google Sheets BYOK missing. Add OAuth access_token to /credentials (service=gsheets).")
    token = cred["api_key"]
    sheet_id = node_data.get("spreadsheet_id")
    range_ = node_data.get("range") or "Sheet1!A:Z"
    if not sheet_id:
        return _err("Google Sheets requires spreadsheet_id.")
    # Build row from values OR fallback to prev_output dict values
    values = node_data.get("values")
    if values is None:
        if isinstance(prev_output, dict):
            values = [list(prev_output.values())]
        elif isinstance(prev_output, list):
            values = [prev_output]
        else:
            values = [[str(prev_output or "")]]
    if isinstance(values, list) and values and not isinstance(values[0], list):
        values = [values]  # auto-wrap single row
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_}:append",
                params={"valueInputOption": "USER_ENTERED"},
                headers={"Authorization": f"Bearer {token}"},
                json={"values": values},
            )
            data = r.json() if r.text else {}
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"updated_range": data.get("updates", {}).get("updatedRange"), "http_status": r.status_code},
                    "log": f"Google Sheets append → {r.status_code}"}
    except Exception as e:
        return _err(f"Google Sheets error: {e}")


# ── Twilio SMS ───────────────────────────────────────────────────
async def action_twilio(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "twilio")
    if not cred or not cred.get("api_key"):
        return _err("Twilio BYOK missing. Add auth_token to /credentials (extra={account_sid, from_number}).")
    auth_token = cred["api_key"]
    extra = cred.get("extra") or {}
    account_sid = node_data.get("account_sid") or extra.get("account_sid")
    from_number = node_data.get("from") or extra.get("from_number")
    to = node_data.get("to")
    body = node_data.get("body") or (json.dumps(prev_output)[:1500] if prev_output else "")
    if not (account_sid and from_number and to):
        return _err("Twilio requires account_sid, from, and to.")
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                auth=(account_sid, auth_token),
                data={"From": from_number, "To": to, "Body": body},
            )
            data = r.json() if r.text else {}
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"sid": data.get("sid"), "status": data.get("status"), "http_status": r.status_code},
                    "log": f"Twilio SMS → {r.status_code}"}
    except Exception as e:
        return _err(f"Twilio error: {e}")


# ── GitHub (issues / PRs) ────────────────────────────────────────
async def action_github(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "github")
    if not cred or not cred.get("api_key"):
        return _err("GitHub BYOK missing. Add personal access token to /credentials (service=github).")
    token = cred["api_key"]
    op = (node_data.get("op") or "create_issue").lower()
    repo = node_data.get("repo")  # "owner/name"
    if not repo:
        return _err("GitHub requires repo='owner/name'.")
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=hdrs) as client:
            if op == "create_issue":
                r = await client.post(f"https://api.github.com/repos/{repo}/issues",
                                      json={"title": node_data.get("title", "Issue from Task Force"),
                                            "body": node_data.get("body", ""),
                                            "labels": node_data.get("labels") or []})
            elif op == "comment_issue":
                num = node_data.get("issue_number")
                if not num:
                    return _err("comment_issue requires issue_number.")
                r = await client.post(f"https://api.github.com/repos/{repo}/issues/{num}/comments",
                                      json={"body": node_data.get("body", "")})
            elif op == "create_pr":
                r = await client.post(f"https://api.github.com/repos/{repo}/pulls",
                                      json={"title": node_data.get("title", "PR from Task Force"),
                                            "head": node_data.get("head"),
                                            "base": node_data.get("base", "main"),
                                            "body": node_data.get("body", "")})
            elif op == "list_issues":
                r = await client.get(f"https://api.github.com/repos/{repo}/issues",
                                     params={"state": node_data.get("state", "open"), "per_page": 30})
            else:
                return _err(f"Unknown GitHub op: {op}")
            data = r.json() if r.text else {}
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"github_op": op, "data": data, "http_status": r.status_code},
                    "log": f"GitHub {op} → {r.status_code}"}
    except Exception as e:
        return _err(f"GitHub error: {e}")


# ── OpenAI BYOK chat ─────────────────────────────────────────────
async def llm_openai(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "openai")
    if not cred or not cred.get("api_key"):
        return _err("OpenAI BYOK missing. Add sk-... to /credentials (service=openai).")
    api_key = cred["api_key"]
    model = node_data.get("model") or "gpt-5.4"
    prompt = node_data.get("prompt") or "Summarize the input."
    sys = node_data.get("system") or "You are a workflow node. Respond concisely."
    inp = json.dumps(prev_output)[:4000] if isinstance(prev_output, (dict, list)) else str(prev_output or "")[:4000]
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "system", "content": sys},
                                   {"role": "user", "content": f"{prompt}\n\nINPUT:\n{inp}"}],
                      "temperature": float(node_data.get("temperature", 0.5))},
            )
            data = r.json() if r.text else {}
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"llm_response": text, "model": model, "usage": data.get("usage")},
                    "log": f"OpenAI {model} → {r.status_code} ({len(text)} chars)"}
    except Exception as e:
        return _err(f"OpenAI error: {e}")


# ── Anthropic Claude BYOK chat ───────────────────────────────────
async def llm_anthropic(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "anthropic")
    if not cred or not cred.get("api_key"):
        return _err("Anthropic BYOK missing. Add sk-ant-... to /credentials (service=anthropic).")
    api_key = cred["api_key"]
    model = node_data.get("model") or "claude-sonnet-4-6"
    prompt = node_data.get("prompt") or "Summarize the input."
    sys = node_data.get("system") or "You are a workflow node. Respond concisely."
    inp = json.dumps(prev_output)[:4000] if isinstance(prev_output, (dict, list)) else str(prev_output or "")[:4000]
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 1024, "system": sys,
                      "messages": [{"role": "user", "content": f"{prompt}\n\nINPUT:\n{inp}"}]},
            )
            data = r.json() if r.text else {}
            text = "".join(b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text")
            return {"status": "ok" if r.status_code < 400 else "error",
                    "output": {"llm_response": text, "model": model, "usage": data.get("usage")},
                    "log": f"Anthropic {model} → {r.status_code} ({len(text)} chars)"}
    except Exception as e:
        return _err(f"Anthropic error: {e}")


# ── Postgres (read-only SELECT in v1) ────────────────────────────
async def db_postgres(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "postgres")
    dsn = (cred or {}).get("api_key") or node_data.get("dsn")
    if not dsn:
        return _err("Postgres DSN missing. Add to /credentials (service=postgres).")
    query = node_data.get("query") or "SELECT 1"
    # Safety: only allow SELECT in v1 unless user explicitly opts in
    allow_write = bool(node_data.get("allow_write"))
    if not allow_write and not query.strip().lower().startswith("select"):
        return _err("Only SELECT queries allowed unless allow_write=true on node.")
    try:
        import asyncpg
        conn = await asyncpg.connect(dsn, timeout=10)
        try:
            if query.strip().lower().startswith("select"):
                rows = await conn.fetch(query)
                out = [dict(r) for r in rows][:500]
            else:
                result = await conn.execute(query)
                out = {"executed": result}
            return _ok({"rows": out, "count": len(out) if isinstance(out, list) else 1}, f"Postgres → {len(out) if isinstance(out, list) else 1} rows")
        finally:
            await conn.close()
    except ImportError:
        return _err("asyncpg not installed; pip install asyncpg.")
    except Exception as e:
        return _err(f"Postgres error: {e}")


# ── MongoDB (find / insert) ──────────────────────────────────────
async def db_mongodb(node_data: Dict, prev_output: Any, ctx: Dict):
    cred = await _load_byok(ctx, "mongodb")
    uri = (cred or {}).get("api_key") or node_data.get("uri")
    db_name = node_data.get("db") or (cred or {}).get("extra", {}).get("db")
    coll = node_data.get("collection")
    if not uri or not db_name or not coll:
        return _err("MongoDB requires uri (BYOK or node), db, collection.")
    op = (node_data.get("op") or "find").lower()
    query = node_data.get("query") or {}
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        try:
            c = client[db_name][coll]
            if op == "find":
                cursor = c.find(query, {"_id": 0}).limit(int(node_data.get("limit") or 50))
                out = await cursor.to_list(50)
                return _ok({"rows": out, "count": len(out)}, f"MongoDB find → {len(out)} docs")
            if op == "insert":
                doc = node_data.get("doc") or (prev_output if isinstance(prev_output, dict) else {"data": prev_output})
                r = await c.insert_one(doc)
                return _ok({"inserted_id": str(r.inserted_id)}, "MongoDB insert ok")
            if op == "update":
                r = await c.update_many(query, {"$set": node_data.get("set") or {}})
                return _ok({"matched": r.matched_count, "modified": r.modified_count}, "MongoDB update ok")
            return _err(f"Unknown MongoDB op: {op}")
        finally:
            client.close()
    except Exception as e:
        return _err(f"MongoDB error: {e}")
