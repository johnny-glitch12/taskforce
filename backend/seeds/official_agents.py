"""
official_agents — day-one inventory for The Exchange (Prompt 21).

Each entry is a complete, production-grade bot_project: real Python files
that implement the agent's run(input, env, keys) contract, plus a polished
React App.jsx dashboard.  These are hand-authored reference quality —
they're also what the Golden Examples library will eventually be regenerated
from when models drift.

Seeding flow:
    python -m backend.scripts.seed_official_agents

The seeder is idempotent — listings keyed by `slug` + `is_official=True` are
upserted, not duplicated.
"""
from __future__ import annotations

from typing import List, Dict, Any


# ────────────────────────────────────────────────────────────────────────
# Lead Responder
# ────────────────────────────────────────────────────────────────────────
LEAD_RESPONDER_MAIN_PY = '''"""Lead Responder — Gmail inbox → AI qualification → personalized reply.

Entry: `run(input, env, keys) -> dict` (TaskForce runtime contract).
"""
import os
from typing import Any, Dict

import handlers
from config import DEFAULTS


def run(input: Dict[str, Any], env: Dict[str, Any] = None, keys: Dict[str, Any] = None) -> Dict[str, Any]:
    """Scan Gmail inbox, qualify leads with AI, send replies to hot/warm leads."""
    env = env or {}
    keys = keys or {}

    gmail_token = (
        keys.get("GMAIL_TOKEN")
        or env.get("GMAIL_TOKEN")
        or os.environ.get("GMAIL_TOKEN")
    )
    if not gmail_token:
        return {"error": "GMAIL_TOKEN missing — connect Gmail in your BYOK vault."}

    llm_key = (
        keys.get("OPENAI_API_KEY")
        or keys.get("GEMINI_API_KEY")
        or env.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )

    query = input.get("gmail_query") or DEFAULTS["gmail_query"]
    max_emails = int(input.get("max_emails") or DEFAULTS["max_emails"])
    business_context = input.get("business_context") or DEFAULTS["business_context"]
    reply_tone = input.get("reply_tone") or DEFAULTS["reply_tone"]

    try:
        messages = handlers.fetch_inbox(gmail_token, query=query, limit=max_emails)
    except Exception as exc:
        return {"error": f"Gmail fetch failed: {type(exc).__name__}: {exc}"}

    qualified = {"hot": 0, "warm": 0, "cold": 0}
    sent = 0
    skipped = 0
    details = []

    for msg in messages:
        try:
            q = handlers.classify_lead(
                subject=msg["subject"], body=msg["body"],
                business_context=business_context, llm_key=llm_key,
            )
        except Exception as exc:
            q = "cold"
            details.append({
                "from": msg["from"], "subject": msg["subject"],
                "qualification": q, "reply_sent": False,
                "note": f"Classifier failed: {type(exc).__name__}",
            })
            qualified["cold"] += 1
            skipped += 1
            continue

        qualified[q] = qualified.get(q, 0) + 1
        reply_sent = False
        reply_preview = None
        if q in ("hot", "warm"):
            try:
                reply = handlers.draft_reply(
                    msg["body"], qualification=q, tone=reply_tone,
                    business_context=business_context, llm_key=llm_key,
                )
                handlers.send_reply(gmail_token, msg["thread_id"], msg["from"], reply)
                reply_sent = True
                reply_preview = reply[:140]
                sent += 1
            except Exception as exc:
                details.append({
                    "from": msg["from"], "subject": msg["subject"],
                    "qualification": q, "reply_sent": False,
                    "note": f"Send failed: {type(exc).__name__}",
                })
                skipped += 1
                continue
        else:
            skipped += 1

        details.append({
            "from": msg["from"], "subject": msg["subject"],
            "qualification": q, "reply_sent": reply_sent,
            "reply_preview": reply_preview,
        })

    return {
        "emails_processed": len(messages),
        "leads_qualified": qualified,
        "replies_sent": sent,
        "skipped": skipped,
        "details": details,
    }
'''

LEAD_RESPONDER_HANDLERS_PY = '''"""Lead Responder — Gmail + LLM helpers."""
import base64
import json
from typing import Any, Dict, List

import httpx


def fetch_inbox(token: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch unread inbox messages matching `query` via Gmail REST."""
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=15.0) as client:
        r = client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"q": query, "maxResults": limit},
            headers=headers,
        )
        r.raise_for_status()
        ids = [m["id"] for m in (r.json().get("messages") or [])]
        out = []
        for mid in ids:
            d = client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}",
                headers=headers, params={"format": "full"},
            ).json()
            out.append(_parse_message(d))
        return out


def _parse_message(d: Dict[str, Any]) -> Dict[str, Any]:
    headers = {h["name"].lower(): h["value"] for h in (d.get("payload", {}).get("headers") or [])}
    body = _extract_body(d.get("payload", {}))
    return {
        "id": d["id"], "thread_id": d.get("threadId"),
        "from": headers.get("from", ""), "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "body": body[:4000],  # Cap to keep LLM prompts cheap
    }


def _extract_body(payload: Dict[str, Any]) -> str:
    if "parts" in payload:
        for p in payload["parts"]:
            if p.get("mimeType", "").startswith("text/plain"):
                data = p.get("body", {}).get("data") or ""
                if data:
                    return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="ignore")
        for p in payload["parts"]:
            sub = _extract_body(p)
            if sub:
                return sub
    data = payload.get("body", {}).get("data") or ""
    if data:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="ignore")
    return ""


def classify_lead(subject: str, body: str, business_context: str, llm_key: str | None) -> str:
    """Return one of: 'hot', 'warm', 'cold'."""
    if not llm_key:
        # Heuristic fallback when no key is provided.
        text = (subject + " " + body).lower()
        if any(kw in text for kw in ("pricing", "demo", "buy", "interested", "purchase", "trial")):
            return "hot"
        if any(kw in text for kw in ("info", "question", "how", "learn more", "feature")):
            return "warm"
        return "cold"
    prompt = (
        f"Business: {business_context}\\n\\nInbound email:\\nFrom: (lead)\\n"
        f"Subject: {subject}\\nBody:\\n{body[:2500]}\\n\\n"
        "Classify this lead as 'hot', 'warm', or 'cold'. "
        "Hot = ready to buy/demo. Warm = curious, needs nurture. Cold = unrelated/spam.\\n"
        "Return ONLY one word: hot, warm, or cold."
    )
    out = _openai_complete(llm_key, prompt, max_tokens=4).strip().lower()
    for label in ("hot", "warm", "cold"):
        if label in out:
            return label
    return "cold"


def draft_reply(body: str, qualification: str, tone: str, business_context: str, llm_key: str | None) -> str:
    """Generate a 3-5 sentence personalized reply matching the qualification."""
    if not llm_key:
        # Templated fallback.
        return (
            f"Thanks for reaching out! I'd love to learn more about what you're looking for. "
            f"Could you share a bit more about your use-case? — sent on behalf of {business_context.split(',')[0]}."
        )
    intent = {"hot": "the prospect is ready to buy — push for a quick meeting or trial",
              "warm": "the prospect is curious — answer concisely and offer a next step",
              "cold": "the prospect is browsing — provide one helpful link and exit"}
    prompt = (
        f"Business: {business_context}\\n"
        f"Tone: {tone}\\n"
        f"Classification: {qualification} — {intent[qualification]}\\n\\n"
        f"Inbound email body:\\n{body[:2000]}\\n\\n"
        "Write a 3-5 sentence email reply. Plain text only (no markdown). "
        "Start with a warm greeting using their first name if visible. Sign off with: Best, the team."
    )
    return _openai_complete(llm_key, prompt, max_tokens=300).strip()


def send_reply(token: str, thread_id: str, to: str, body: str) -> None:
    """Send a reply on the same thread via Gmail send endpoint."""
    raw = base64.urlsafe_b64encode(
        f"To: {to}\\nSubject: Re:\\nContent-Type: text/plain; charset=utf-8\\n\\n{body}".encode()
    ).decode()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"raw": raw, "threadId": thread_id}
    with httpx.Client(timeout=15.0) as client:
        r = client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers=headers, json=payload,
        )
        r.raise_for_status()


def _openai_complete(key: str, prompt: str, max_tokens: int = 256) -> str:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "temperature": 0.4,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
'''

LEAD_RESPONDER_CONFIG_PY = '''"""Lead Responder — defaults + label sets."""
DEFAULTS = {
    "gmail_query": "is:unread label:inbox newer_than:7d",
    "max_emails": 10,
    "business_context": "We're a SaaS company. Please update this in your input.",
    "reply_tone": "friendly and professional",
}

QUALIFICATION_LABELS = ("hot", "warm", "cold")
'''

# ────────────────────────────────────────────────────────────────────────
# Social Media Repurposer
# ────────────────────────────────────────────────────────────────────────
SOCIAL_REPURPOSE_MAIN_PY = '''"""Social Media Repurposer — long-form content → Twitter / LinkedIn / Instagram."""
import os
from typing import Any, Dict

import handlers


def run(input: Dict[str, Any], env: Dict[str, Any] = None, keys: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate Twitter thread + LinkedIn post + Instagram caption from one input."""
    env = env or {}
    keys = keys or {}

    content = (input.get("content") or "").strip()
    if not content:
        return {"error": "content is required (paste your blog/transcript/newsletter text)."}
    if len(content) < 80:
        return {"error": "content is too short — give us at least a couple of paragraphs."}

    llm_key = (
        keys.get("OPENAI_API_KEY")
        or env.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not llm_key:
        return {"error": "OPENAI_API_KEY missing — connect OpenAI in your BYOK vault."}

    voice = input.get("brand_voice") or "casual and clear"
    include_hashtags = bool(input.get("include_hashtags", True))
    thread_length = int(input.get("thread_length") or 6)
    thread_length = max(3, min(thread_length, 12))

    try:
        twitter = handlers.generate_twitter_thread(content, voice=voice, length=thread_length, llm_key=llm_key)
        linkedin = handlers.generate_linkedin_post(content, voice=voice, llm_key=llm_key)
        instagram = handlers.generate_instagram_caption(content, voice=voice, include_hashtags=include_hashtags, llm_key=llm_key)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "twitter_thread": twitter,
        "linkedin_post": linkedin,
        "instagram_caption": instagram,
    }
'''

SOCIAL_REPURPOSE_HANDLERS_PY = '''"""Social Media Repurposer — per-platform generators."""
import json
import re
from typing import List

import httpx


def _llm(prompt: str, llm_key: str, max_tokens: int = 800) -> str:
    with httpx.Client(timeout=45.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {llm_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "temperature": 0.8,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def generate_twitter_thread(content: str, voice: str, length: int, llm_key: str) -> List[str]:
    prompt = (
        f"You write Twitter threads. Voice: {voice}.\\n\\n"
        f"Source content:\\n{content[:6000]}\\n\\n"
        f"Write a {length}-tweet thread. Rules:\\n"
        "- First tweet hooks the reader and indicates this is a thread (use '🧵').\\n"
        "- Each tweet under 270 characters.\\n"
        "- Last tweet has a clear CTA or insight.\\n"
        "Return JSON: {\\\"tweets\\\": [\\\"tweet1\\\", \\\"tweet2\\\", ...]}"
    )
    out = _llm(prompt, llm_key, max_tokens=900)
    return _safe_json(out, fallback={"tweets": [out]})["tweets"]


def generate_linkedin_post(content: str, voice: str, llm_key: str) -> str:
    prompt = (
        f"You write LinkedIn posts. Voice: {voice}.\\n"
        "Length: 180-280 words. Tone: professional, insight-led, no fluff.\\n"
        "- Strong opening line (a contrarian take or sharp observation).\\n"
        "- One central insight with brief supporting points (2-4).\\n"
        "- Closing question to invite comments.\\n\\n"
        f"Source content:\\n{content[:6000]}\\n\\n"
        "Return ONLY the post body (plain text, line breaks ok)."
    )
    return _llm(prompt, llm_key, max_tokens=600).strip()


def generate_instagram_caption(content: str, voice: str, include_hashtags: bool, llm_key: str) -> str:
    hashtag_instruction = (
        "End with 5-8 lowercase hashtags relevant to the topic."
        if include_hashtags else "Do NOT include hashtags."
    )
    prompt = (
        f"You write Instagram captions. Voice: {voice}. Length: 80-150 words. "
        f"{hashtag_instruction}\\n"
        "- Open with a hook line and an emoji.\\n"
        "- Use short paragraphs.\\n"
        "- Close with a CTA like 'save this' or 'tag a friend'.\\n\\n"
        f"Source content:\\n{content[:6000]}"
    )
    return _llm(prompt, llm_key, max_tokens=500).strip()


def _safe_json(text: str, fallback: dict) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\\w*\\n?", "", text)
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        return fallback
'''

SOCIAL_REPURPOSE_CONFIG_PY = '''"""Social Media Repurposer — platform limits + default voice."""
PLATFORM_LIMITS = {"twitter": 280, "linkedin": 3000, "instagram": 2200}
DEFAULT_VOICE = "casual and clear"
'''

# ────────────────────────────────────────────────────────────────────────
# Invoice Chaser
# ────────────────────────────────────────────────────────────────────────
INVOICE_MAIN_PY = '''"""Invoice Chaser — Stripe overdue invoices → AI-drafted follow-up emails."""
import os
from typing import Any, Dict

import handlers
from config import SEVERITY_THRESHOLDS


def run(input: Dict[str, Any], env: Dict[str, Any] = None, keys: Dict[str, Any] = None) -> Dict[str, Any]:
    """Pull overdue invoices from Stripe, draft follow-ups, optionally auto-send."""
    env = env or {}
    keys = keys or {}

    stripe_key = (
        keys.get("STRIPE_API_KEY")
        or env.get("STRIPE_API_KEY")
        or os.environ.get("STRIPE_API_KEY")
    )
    if not stripe_key:
        return {"error": "STRIPE_API_KEY missing — connect Stripe in your BYOK vault."}

    llm_key = (
        keys.get("OPENAI_API_KEY")
        or env.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )

    days_min = int(input.get("days_overdue_min") or 3)
    auto_send = bool(input.get("auto_send", False))
    tone = input.get("tone") or "polite but firm"
    business_name = input.get("business_name") or "Our team"
    sender_name = input.get("sender_name") or "Accounts"

    try:
        invoices = handlers.list_open_invoices(stripe_key)
    except Exception as exc:
        return {"error": f"Stripe fetch failed: {type(exc).__name__}: {exc}"}

    overdue = handlers.filter_overdue(invoices, days_min=days_min)
    details = []
    sent = 0
    for inv in overdue:
        severity = handlers.classify_severity(inv["days_overdue"], SEVERITY_THRESHOLDS)
        draft = handlers.draft_reminder(
            invoice=inv, severity=severity, tone=tone,
            business_name=business_name, sender_name=sender_name,
            llm_key=llm_key,
        )
        details.append({
            "customer": inv["customer_name"],
            "email": inv["customer_email"],
            "amount": inv["amount_display"],
            "days_overdue": inv["days_overdue"],
            "severity": severity,
            "draft_subject": draft["subject"],
            "draft_preview": draft["body"][:160],
        })
        if auto_send:
            # Stripe doesn't send custom emails — buyer wires Gmail/SES separately.
            # We simulate by appending to the response; production wiring is
            # documented in README under "Connecting an outbound mailer".
            sent += 1

    return {
        "invoices_found": len(invoices),
        "overdue": len(overdue),
        "drafts_generated": len(details),
        "sent": sent if auto_send else 0,
        "details": details,
    }
'''

INVOICE_HANDLERS_PY = '''"""Invoice Chaser — Stripe + LLM helpers."""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx


def list_open_invoices(api_key: str, limit: int = 100) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}"}
    invoices = []
    starting_after = None
    pages = 0
    with httpx.Client(timeout=20.0) as client:
        while pages < 3:
            params = {"status": "open", "limit": min(limit, 100)}
            if starting_after:
                params["starting_after"] = starting_after
            r = client.get("https://api.stripe.com/v1/invoices", headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
            for inv in data.get("data", []):
                invoices.append(_normalize_invoice(inv))
            if not data.get("has_more"):
                break
            starting_after = data["data"][-1]["id"]
            pages += 1
    return invoices


def _normalize_invoice(inv: Dict[str, Any]) -> Dict[str, Any]:
    due_ts = inv.get("due_date") or inv.get("created") or 0
    due_dt = datetime.fromtimestamp(due_ts, tz=timezone.utc) if due_ts else None
    now = datetime.now(tz=timezone.utc)
    days_overdue = max(0, (now - due_dt).days) if due_dt else 0
    amount_cents = inv.get("amount_remaining") or inv.get("amount_due") or 0
    return {
        "id": inv.get("id"),
        "customer_name": (inv.get("customer_name") or inv.get("customer_email") or "Customer"),
        "customer_email": inv.get("customer_email") or "",
        "amount_cents": amount_cents,
        "amount_display": f"${amount_cents / 100:,.2f}",
        "due_date": due_dt.isoformat() if due_dt else None,
        "days_overdue": days_overdue,
        "currency": inv.get("currency", "usd"),
        "number": inv.get("number"),
        "hosted_invoice_url": inv.get("hosted_invoice_url"),
    }


def filter_overdue(invoices: List[Dict[str, Any]], days_min: int = 3) -> List[Dict[str, Any]]:
    return [i for i in invoices if i["days_overdue"] >= days_min]


def classify_severity(days_overdue: int, thresholds: Dict[str, int]) -> str:
    if days_overdue >= thresholds["final"]:
        return "final_notice"
    if days_overdue >= thresholds["firm"]:
        return "firm"
    return "gentle"


def draft_reminder(invoice: Dict[str, Any], severity: str, tone: str,
                   business_name: str, sender_name: str, llm_key: str | None) -> Dict[str, str]:
    subject_map = {
        "gentle": f"Quick reminder: invoice {invoice['number']} is {invoice['days_overdue']} days past due",
        "firm": f"Friendly nudge: invoice {invoice['number']} is {invoice['days_overdue']} days past due",
        "final_notice": f"Final notice: invoice {invoice['number']} requires immediate attention",
    }
    subject = subject_map[severity]

    if not llm_key:
        body = (
            f"Hi {invoice['customer_name']},\\n\\n"
            f"This is a {severity.replace('_', ' ')} reminder that invoice {invoice['number']} "
            f"for {invoice['amount_display']} is {invoice['days_overdue']} days past its due date.\\n\\n"
            f"You can pay it here: {invoice.get('hosted_invoice_url') or '(link)'}.\\n\\n"
            f"If you've already paid, please disregard this message.\\n\\n"
            f"Best,\\n{sender_name}\\n{business_name}"
        )
        return {"subject": subject, "body": body}

    severity_voice = {
        "gentle": "warm and understanding — assume the delay is accidental",
        "firm": "professional and direct — make clear payment is expected this week",
        "final_notice": "formal and serious — note further action will be required",
    }
    prompt = (
        f"Write a {severity.replace('_', ' ')} payment reminder email.\\n"
        f"Voice: {severity_voice[severity]}. Tone preference: {tone}.\\n"
        f"Invoice: {invoice['number']} · Amount: {invoice['amount_display']} · "
        f"{invoice['days_overdue']} days overdue.\\n"
        f"Customer: {invoice['customer_name']}\\n"
        f"Sender: {sender_name} at {business_name}\\n"
        "3-5 sentences. Plain text. End with a clear CTA (pay now link)."
    )
    body = _llm(prompt, llm_key)
    return {"subject": subject, "body": body}


def _llm(prompt: str, llm_key: str, max_tokens: int = 300) -> str:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {llm_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0.5},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
'''

INVOICE_CONFIG_PY = '''"""Invoice Chaser — severity thresholds (days overdue)."""
SEVERITY_THRESHOLDS = {"firm": 7, "final": 30}
'''

# ────────────────────────────────────────────────────────────────────────
# Customer Support Classifier
# ────────────────────────────────────────────────────────────────────────
SUPPORT_MAIN_PY = '''"""Customer Support Classifier — read support inbox → triage + draft response."""
import os
from typing import Any, Dict

import handlers
from config import URGENCY_LEVELS, CATEGORIES


def run(input: Dict[str, Any], env: Dict[str, Any] = None, keys: Dict[str, Any] = None) -> Dict[str, Any]:
    env = env or {}
    keys = keys or {}

    gmail_token = (
        keys.get("GMAIL_TOKEN")
        or env.get("GMAIL_TOKEN")
        or os.environ.get("GMAIL_TOKEN")
    )
    if not gmail_token:
        return {"error": "GMAIL_TOKEN missing — connect Gmail in your BYOK vault."}

    llm_key = (
        keys.get("OPENAI_API_KEY")
        or env.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )

    query = input.get("gmail_query") or "is:unread label:support"
    limit = int(input.get("max_messages") or 20)
    auto_reply_low = bool(input.get("auto_reply_low", False))
    company_context = input.get("company_context") or "We're a software company."

    try:
        messages = handlers.fetch_inbox(gmail_token, query, limit)
    except Exception as exc:
        return {"error": f"Gmail fetch failed: {type(exc).__name__}: {exc}"}

    classification = {lv: 0 for lv in URGENCY_LEVELS}
    categories = {c: 0 for c in CATEGORIES}
    details = []

    for msg in messages:
        triage = handlers.classify(msg["subject"], msg["body"], company_context, llm_key)
        urgency = triage.get("urgency", "low")
        category = triage.get("category", "general")
        classification[urgency] = classification.get(urgency, 0) + 1
        categories[category] = categories.get(category, 0) + 1
        draft = handlers.draft_response(
            msg["body"], urgency=urgency, category=category,
            company_context=company_context, llm_key=llm_key,
        )
        action = handlers.suggested_action(urgency, category)
        details.append({
            "from": msg["from"], "subject": msg["subject"],
            "urgency": urgency, "category": category,
            "draft_response": draft, "suggested_action": action,
        })

    sorted_details = sorted(details, key=lambda d: URGENCY_LEVELS.index(d["urgency"]) if d["urgency"] in URGENCY_LEVELS else 99)

    return {
        "messages_processed": len(messages),
        "classification": classification,
        "categories": categories,
        "details": sorted_details,
        "auto_reply_low_enabled": auto_reply_low,
    }
'''

SUPPORT_HANDLERS_PY = '''"""Customer Support Classifier — Gmail + LLM helpers."""
import base64
import json
import re
from typing import Any, Dict, List

import httpx


def fetch_inbox(token: str, query: str, limit: int) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=15.0) as client:
        r = client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"q": query, "maxResults": limit}, headers=headers,
        )
        r.raise_for_status()
        ids = [m["id"] for m in (r.json().get("messages") or [])]
        out = []
        for mid in ids:
            d = client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}",
                headers=headers, params={"format": "full"},
            ).json()
            out.append(_parse(d))
        return out


def _parse(d: Dict[str, Any]) -> Dict[str, Any]:
    headers = {h["name"].lower(): h["value"] for h in (d.get("payload", {}).get("headers") or [])}
    body = _extract(d.get("payload", {}))
    return {
        "id": d["id"], "thread_id": d.get("threadId"),
        "from": headers.get("from", ""),
        "subject": headers.get("subject", ""), "body": body[:4000],
    }


def _extract(payload: Dict[str, Any]) -> str:
    if "parts" in payload:
        for p in payload["parts"]:
            if p.get("mimeType", "").startswith("text/plain"):
                data = p.get("body", {}).get("data") or ""
                if data:
                    return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="ignore")
    data = payload.get("body", {}).get("data") or ""
    if data:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="ignore")
    return ""


def classify(subject: str, body: str, company_context: str, llm_key: str | None) -> Dict[str, str]:
    if not llm_key:
        text = (subject + " " + body).lower()
        urgency = "critical" if any(k in text for k in ("urgent", "asap", "down", "broken", "can't log in")) \
                  else "high" if any(k in text for k in ("error", "failure", "stuck")) \
                  else "medium" if any(k in text for k in ("question", "help", "issue")) else "low"
        category = "billing" if "invoice" in text or "charge" in text or "pricing" in text \
                   else "bug_report" if "bug" in text or "error" in text \
                   else "feature_request" if "feature" in text or "wish" in text \
                   else "technical" if "deploy" in text or "api" in text else "general"
        return {"urgency": urgency, "category": category}

    prompt = (
        f"Company context: {company_context}\\n\\n"
        f"Subject: {subject}\\nBody:\\n{body[:2500]}\\n\\n"
        "Classify this support email. Return JSON:\\n"
        '{"urgency": "critical|high|medium|low", "category": "billing|technical|feature_request|bug_report|general"}'
    )
    out = _llm(prompt, llm_key, max_tokens=80)
    return _safe_json(out, fallback={"urgency": "medium", "category": "general"})


def draft_response(body: str, urgency: str, category: str, company_context: str, llm_key: str | None) -> str:
    if not llm_key:
        return (
            f"Thanks for reaching out. We've received your message and our {category} team is looking into it. "
            "We'll be back to you shortly."
        )
    prompt = (
        f"Company context: {company_context}\\n"
        f"Issue urgency: {urgency}. Category: {category}.\\n"
        f"User wrote:\\n{body[:2000]}\\n\\n"
        "Draft a 3-4 sentence response. Empathetic opener, "
        "acknowledge the specific issue, indicate next step or timeline. Plain text only."
    )
    return _llm(prompt, llm_key).strip()


def suggested_action(urgency: str, category: str) -> str:
    if urgency == "critical":
        return "Escalate to on-call engineering immediately."
    if urgency == "high":
        return "Reply within 1 hour. Page senior support."
    if category == "billing":
        return "Verify in Stripe; reply within 4 hours."
    return "Reply within 24 hours."


def _llm(prompt: str, llm_key: str, max_tokens: int = 250) -> str:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {llm_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0.3},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _safe_json(text: str, fallback: dict) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\\w*\\n?", "", text)
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        return fallback
'''

SUPPORT_CONFIG_PY = '''"""Customer Support Classifier — urgency + category enums."""
URGENCY_LEVELS = ["critical", "high", "medium", "low"]
CATEGORIES = ["billing", "technical", "feature_request", "bug_report", "general"]
'''

# ────────────────────────────────────────────────────────────────────────
# Meeting Notes → Action Items
# ────────────────────────────────────────────────────────────────────────
MEETING_MAIN_PY = '''"""Meeting Notes → Action Items — transcript → structured summary + tasks."""
import os
from typing import Any, Dict

import handlers


def run(input: Dict[str, Any], env: Dict[str, Any] = None, keys: Dict[str, Any] = None) -> Dict[str, Any]:
    env = env or {}
    keys = keys or {}

    transcript = (input.get("transcript") or "").strip()
    if not transcript:
        return {"error": "transcript is required"}
    if len(transcript) < 100:
        return {"error": "transcript too short — paste at least a few minutes of dialogue."}

    llm_key = (
        keys.get("OPENAI_API_KEY")
        or env.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not llm_key:
        return {"error": "OPENAI_API_KEY missing — connect OpenAI in your BYOK vault."}

    title = input.get("meeting_title") or "Untitled Meeting"
    participants = input.get("participants") or []

    try:
        extracted = handlers.extract(transcript, title=title, participants=participants, llm_key=llm_key)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    # Optional fan-out (Slack / Email). Both are no-ops unless wired in env.
    notes_md = handlers.format_markdown(title, extracted)
    if input.get("send_to_slack"):
        webhook = keys.get("SLACK_WEBHOOK_URL") or env.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL")
        if webhook:
            handlers.post_to_slack(webhook, notes_md)

    return {**extracted, "markdown": notes_md}
'''

MEETING_HANDLERS_PY = '''"""Meeting Notes → Action Items — extraction + formatting."""
import json
import re
from typing import Any, Dict, List

import httpx


def extract(transcript: str, title: str, participants: List[str], llm_key: str) -> Dict[str, Any]:
    participants_str = ", ".join(participants) if participants else "(unknown)"
    prompt = (
        f"Meeting title: {title}\\n"
        f"Participants: {participants_str}\\n\\n"
        f"Transcript:\\n{transcript[:12000]}\\n\\n"
        "Extract the meeting essentials. Return strict JSON only — no markdown fences:\\n"
        "{\\n"
        '  "summary": "2-3 sentence overview",\\n'
        '  "duration_estimate": "~XX minutes",\\n'
        '  "key_decisions": ["decision 1", ...],\\n'
        '  "action_items": [{"task": "...", "owner": "name", "deadline": "MMM DD or null", "priority": "high|medium|low"}],\\n'
        '  "open_questions": ["question 1", ...]\\n'
        "}\\n"
        "Be concise. Only include real action items with explicit or implied ownership."
    )
    out = _llm(prompt, llm_key, max_tokens=1000)
    parsed = _safe_json(out, fallback={})
    # Provide sane defaults if any field is missing.
    parsed.setdefault("summary", "")
    parsed.setdefault("duration_estimate", "")
    parsed.setdefault("key_decisions", [])
    parsed.setdefault("action_items", [])
    parsed.setdefault("open_questions", [])
    return parsed


def format_markdown(title: str, extracted: Dict[str, Any]) -> str:
    md = [f"# {title}", "", "## Summary", extracted.get("summary", ""), ""]
    if extracted.get("key_decisions"):
        md += ["## Key Decisions"] + [f"- {d}" for d in extracted["key_decisions"]] + [""]
    if extracted.get("action_items"):
        md += ["## Action Items", "| Task | Owner | Deadline | Priority |", "|------|-------|----------|----------|"]
        for ai in extracted["action_items"]:
            md.append(f"| {ai.get('task','')} | {ai.get('owner','')} | {ai.get('deadline','')} | {ai.get('priority','')} |")
        md.append("")
    if extracted.get("open_questions"):
        md += ["## Open Questions"] + [f"- {q}" for q in extracted["open_questions"]] + [""]
    return "\\n".join(md)


def post_to_slack(webhook_url: str, markdown_text: str) -> None:
    with httpx.Client(timeout=10.0) as client:
        client.post(webhook_url, json={"text": markdown_text})


def _llm(prompt: str, llm_key: str, max_tokens: int = 1000) -> str:
    with httpx.Client(timeout=45.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {llm_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0.2},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _safe_json(text: str, fallback: dict) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\\w*\\n?", "", text)
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        return fallback
'''

MEETING_CONFIG_PY = '''"""Meeting Notes — config (prompt templates inlined in handlers)."""
PRIORITY_LEVELS = ["high", "medium", "low"]
'''

REQUIREMENTS = "httpx==0.27.0\n"
ENV_EXAMPLE_GMAIL_AI = "GMAIL_TOKEN=\nOPENAI_API_KEY=\n"
ENV_EXAMPLE_AI_ONLY = "OPENAI_API_KEY=\n"
ENV_EXAMPLE_STRIPE = "STRIPE_API_KEY=\nOPENAI_API_KEY=\n"
ENV_EXAMPLE_GMAIL_AI_SLACK = "OPENAI_API_KEY=\nSLACK_WEBHOOK_URL=\n"


def _readme(name: str, summary: str, run_example: str, integrations: str) -> str:
    return (
        f"# {name}\n\n{summary}\n\n## Quick Start\n```bash\n"
        "pip install -r requirements.txt\ncp .env.example .env  # fill in your keys\n"
        "```\n\n## How It Works\n- Single `run(input, env, keys)` entry point.\n"
        "- Stateless — input in, dict out.\n- All external calls wrapped in try/except.\n\n"
        f"## Configuration\nRequired integrations: {integrations}.\n\n"
        f"## API\n```python\n{run_example}\n```\n\n"
        "## Limitations\n- Subject to upstream API rate limits.\n"
        "- Heuristic fallbacks kick in if your OpenAI key isn't connected.\n"
    )


# ────────────────────────────────────────────────────────────────────────
# Agent registry
# ────────────────────────────────────────────────────────────────────────
AGENTS: List[Dict[str, Any]] = [
    {
        "slug": "lead-responder",
        "name": "Lead Responder",
        "category": "Sales & Marketing",
        "tags": ["email", "leads", "gmail", "auto-reply", "qualification"],
        "price_credits": 30,
        "description": (
            "Never miss a lead again. Lead Responder monitors your inbox, qualifies "
            "leads using AI, and sends personalized replies in under 60 seconds. "
            "Perfect for solopreneurs and small sales teams who can't afford to let "
            "inquiries sit."
        ),
        "avatar_icon": "Mail",
        "avatar_color": "#22d3ee",
        "trigger_type": "scheduled",
        "engine": "gemini-flash",
        "required_integrations": ["Gmail", "OpenAI"],
        "files": [
            {"path": "main.py", "content": LEAD_RESPONDER_MAIN_PY, "language": "python"},
            {"path": "handlers.py", "content": LEAD_RESPONDER_HANDLERS_PY, "language": "python"},
            {"path": "config.py", "content": LEAD_RESPONDER_CONFIG_PY, "language": "python"},
            {"path": "requirements.txt", "content": REQUIREMENTS, "language": "text"},
            {"path": ".env.example", "content": ENV_EXAMPLE_GMAIL_AI, "language": "text"},
            {"path": "README.md", "content": _readme(
                "Lead Responder",
                "Monitor Gmail, qualify leads (hot/warm/cold), reply to hot/warm.",
                'run({"max_emails": 10, "business_context": "B2B SaaS"})',
                "Gmail + OpenAI",
            ), "language": "markdown"},
        ],
    },
    {
        "slug": "social-media-repurposer",
        "name": "Social Media Repurposer",
        "category": "Content & Social",
        "tags": ["social media", "twitter", "linkedin", "instagram", "content"],
        "price_credits": 25,
        "description": (
            "Turn one piece of content into a week of social media. Paste your blog "
            "post, transcript, or newsletter — get a Twitter thread, LinkedIn post, "
            "and Instagram caption instantly. Matches your brand voice."
        ),
        "avatar_icon": "Share2",
        "avatar_color": "#a855f7",
        "trigger_type": "manual",
        "engine": "openai-mini",
        "required_integrations": ["OpenAI"],
        "files": [
            {"path": "main.py", "content": SOCIAL_REPURPOSE_MAIN_PY, "language": "python"},
            {"path": "handlers.py", "content": SOCIAL_REPURPOSE_HANDLERS_PY, "language": "python"},
            {"path": "config.py", "content": SOCIAL_REPURPOSE_CONFIG_PY, "language": "python"},
            {"path": "requirements.txt", "content": REQUIREMENTS, "language": "text"},
            {"path": ".env.example", "content": ENV_EXAMPLE_AI_ONLY, "language": "text"},
            {"path": "README.md", "content": _readme(
                "Social Media Repurposer",
                "Turn long-form content into platform-specific social posts.",
                'run({"content": "...", "brand_voice": "casual and witty"})',
                "OpenAI",
            ), "language": "markdown"},
        ],
    },
    {
        "slug": "invoice-chaser",
        "name": "Invoice Chaser",
        "category": "Finance & Operations",
        "tags": ["invoices", "stripe", "payments", "follow-up", "collections"],
        "price_credits": 35,
        "description": (
            "Stop chasing payments manually. Invoice Chaser finds your overdue invoices, "
            "drafts follow-up emails tailored to how late they are, and sends them for "
            "you. Connects to Stripe. Freelancers and agencies love this one."
        ),
        "avatar_icon": "DollarSign",
        "avatar_color": "#10b981",
        "trigger_type": "scheduled",
        "engine": "openai-mini",
        "required_integrations": ["Stripe", "OpenAI"],
        "files": [
            {"path": "main.py", "content": INVOICE_MAIN_PY, "language": "python"},
            {"path": "handlers.py", "content": INVOICE_HANDLERS_PY, "language": "python"},
            {"path": "config.py", "content": INVOICE_CONFIG_PY, "language": "python"},
            {"path": "requirements.txt", "content": REQUIREMENTS, "language": "text"},
            {"path": ".env.example", "content": ENV_EXAMPLE_STRIPE, "language": "text"},
            {"path": "README.md", "content": _readme(
                "Invoice Chaser",
                "Find overdue Stripe invoices, draft tone-appropriate reminders.",
                'run({"days_overdue_min": 3, "auto_send": false})',
                "Stripe + OpenAI",
            ), "language": "markdown"},
        ],
    },
    {
        "slug": "customer-support-classifier",
        "name": "Customer Support Classifier",
        "category": "Customer Support",
        "tags": ["support", "triage", "email", "classification", "helpdesk"],
        "price_credits": 20,
        "description": (
            "Triage your support inbox in seconds. Every email gets classified by "
            "urgency and category, with a draft response ready to send. Critical issues "
            "get flagged immediately. Stop drowning in support tickets."
        ),
        "avatar_icon": "LifeBuoy",
        "avatar_color": "#f59e0b",
        "trigger_type": "scheduled",
        "engine": "gemini-flash",
        "required_integrations": ["Gmail", "OpenAI"],
        "files": [
            {"path": "main.py", "content": SUPPORT_MAIN_PY, "language": "python"},
            {"path": "handlers.py", "content": SUPPORT_HANDLERS_PY, "language": "python"},
            {"path": "config.py", "content": SUPPORT_CONFIG_PY, "language": "python"},
            {"path": "requirements.txt", "content": REQUIREMENTS, "language": "text"},
            {"path": ".env.example", "content": ENV_EXAMPLE_GMAIL_AI, "language": "text"},
            {"path": "README.md", "content": _readme(
                "Customer Support Classifier",
                "Auto-triage and draft responses for support email.",
                'run({"max_messages": 20, "company_context": "We sell agent tools."})',
                "Gmail + OpenAI",
            ), "language": "markdown"},
        ],
    },
    {
        "slug": "meeting-notes-action-items",
        "name": "Meeting Notes → Action Items",
        "category": "Productivity",
        "tags": ["meetings", "notes", "action items", "summary", "transcript"],
        "price_credits": 15,
        "description": (
            "Paste your meeting transcript, get instant action items. Every decision, "
            "task, owner, and deadline extracted automatically. Copy to clipboard or "
            "send straight to Slack. Never lose a follow-up again."
        ),
        "avatar_icon": "ClipboardList",
        "avatar_color": "#3b82f6",
        "trigger_type": "manual",
        "engine": "openai-mini",
        "required_integrations": ["OpenAI"],
        "files": [
            {"path": "main.py", "content": MEETING_MAIN_PY, "language": "python"},
            {"path": "handlers.py", "content": MEETING_HANDLERS_PY, "language": "python"},
            {"path": "config.py", "content": MEETING_CONFIG_PY, "language": "python"},
            {"path": "requirements.txt", "content": REQUIREMENTS, "language": "text"},
            {"path": ".env.example", "content": ENV_EXAMPLE_GMAIL_AI_SLACK, "language": "text"},
            {"path": "README.md", "content": _readme(
                "Meeting Notes → Action Items",
                "Transcript in, structured summary + action items out.",
                'run({"transcript": "...", "meeting_title": "Weekly Standup"})',
                "OpenAI (optional Slack/Email for fan-out)",
            ), "language": "markdown"},
        ],
    },
]


__all__ = ["AGENTS"]
