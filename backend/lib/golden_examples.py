"""
golden_examples — curated reference plans + builder snippets that we inject
into the Planner / Builder prompts when the user's request matches one of
the patterns. Lifts code-gen quality dramatically vs. cold-start prompting.

Each example is a tightly compressed reference (≤ ~2 KB) showing the
shape of the planner output (files, nodes, edges, env_vars) and a
representative excerpt of the Builder output for that pattern.

Selection: simple keyword overlap on the user_prompt. The top match (by
score) is injected. Threshold: at least 1 keyword must match.

Why hand-curated?  The pipeline is generative; injecting a single high-
quality example as a "shape constraint" steers JSON formatting + node
patterns without the brittleness of few-shot stacks.
"""
from __future__ import annotations

from typing import List, Dict, Any


GOLDEN_EXAMPLES: List[Dict[str, Any]] = [
    # ─────────────── Email / Gmail automation ───────────────
    {
        "id": "gmail_classifier",
        "keywords": [
            "gmail", "email", "inbox", "reply", "classify",
            "lead", "responder", "auto-reply", "qualification",
            "support ticket", "triage",
        ],
        "planner_excerpt": {
            "files": [
                {"path": "main.py",          "purpose": "run(input,env,keys) entry — orchestrates fetch → classify → reply"},
                {"path": "handlers.py",      "purpose": "Gmail fetch, AI classify, reply send helpers"},
                {"path": "config.py",        "purpose": "Env loading, classification labels, tone presets"},
                {"path": "requirements.txt", "purpose": "httpx, google-api-python-client, pydantic"},
                {"path": ".env.example",     "purpose": "GMAIL_TOKEN, OPENAI_API_KEY"},
                {"path": "README.md",        "purpose": "Setup + usage"},
            ],
            "nodes": [
                {"id": "n1", "type": "trigger", "label": "Manual / Cron", "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "action",  "label": "Fetch Inbox",   "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",     "label": "Classify Lead", "position": {"x": 700, "y": 120}},
                {"id": "n4", "type": "condition","label": "Is Hot/Warm?", "position": {"x": 1000, "y": 120}},
                {"id": "n5", "type": "action",  "label": "Send Reply",    "position": {"x": 1300, "y": 60}},
                {"id": "n6", "type": "database","label": "Log Skipped",   "position": {"x": 1300, "y": 200}},
            ],
            "edges": [
                {"id": "e1-2", "source": "n1", "target": "n2"},
                {"id": "e2-3", "source": "n2", "target": "n3"},
                {"id": "e3-4", "source": "n3", "target": "n4"},
                {"id": "e4-5", "source": "n4", "target": "n5"},
                {"id": "e4-6", "source": "n4", "target": "n6"},
            ],
        },
        "builder_excerpt": """
def run(input: dict, env: dict = None, keys: dict = None) -> dict:
    \"\"\"Entry point. Fetch Gmail → classify → reply hot/warm leads.\"\"\"
    env = env or {}; keys = keys or {}
    gmail_token = keys.get("GMAIL_TOKEN") or env.get("GMAIL_TOKEN") or os.environ.get("GMAIL_TOKEN")
    if not gmail_token:
        return {"error": "GMAIL_TOKEN missing — connect Gmail in your BYOK vault."}
    try:
        messages = handlers.fetch_inbox(gmail_token, query=input.get("gmail_query", "is:unread"), limit=input.get("max_emails", 10))
        results = []
        for m in messages:
            q = handlers.classify_lead(m, business_context=input.get("business_context", ""))
            if q in ("hot", "warm"):
                reply = handlers.draft_reply(m, tone=input.get("reply_tone", "friendly"))
                handlers.send_reply(gmail_token, m["thread_id"], reply)
            results.append({"from": m["from"], "subject": m["subject"], "qualification": q})
        return {"emails_processed": len(messages), "details": results}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
""".strip(),
    },

    # ─────────────── Content repurposing / social ───────────────
    {
        "id": "content_repurpose",
        "keywords": [
            "blog", "transcript", "social", "twitter", "thread",
            "linkedin", "instagram", "repurpose", "content",
            "newsletter", "summarize", "summary",
        ],
        "planner_excerpt": {
            "files": [
                {"path": "main.py",          "purpose": "run() — accepts content text, returns 3 platform variants"},
                {"path": "handlers.py",      "purpose": "LLM prompt builders + per-platform formatters"},
                {"path": "config.py",        "purpose": "Char limits, hashtag presets per platform"},
                {"path": "requirements.txt", "purpose": "openai or google-genai, pydantic"},
                {"path": ".env.example",     "purpose": "OPENAI_API_KEY or GEMINI_API_KEY"},
            ],
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Input Content",    "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "transform", "label": "Normalize",        "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",       "label": "Generate Twitter", "position": {"x": 700, "y": 40}},
                {"id": "n4", "type": "llm",       "label": "Generate LinkedIn","position": {"x": 700, "y": 180}},
                {"id": "n5", "type": "llm",       "label": "Generate Instagram","position": {"x": 700, "y": 320}},
                {"id": "n6", "type": "transform", "label": "Bundle Output",    "position": {"x": 1000, "y": 180}},
            ],
            "edges": [
                {"id": "e1-2", "source": "n1", "target": "n2"},
                {"id": "e2-3", "source": "n2", "target": "n3"},
                {"id": "e2-4", "source": "n2", "target": "n4"},
                {"id": "e2-5", "source": "n2", "target": "n5"},
                {"id": "e3-6", "source": "n3", "target": "n6"},
                {"id": "e4-6", "source": "n4", "target": "n6"},
                {"id": "e5-6", "source": "n5", "target": "n6"},
            ],
        },
        "builder_excerpt": """
def run(input: dict, env: dict = None, keys: dict = None) -> dict:
    \"\"\"Accept long-form content and produce platform-specific variants.\"\"\"
    env = env or {}; keys = keys or {}
    content = (input.get("content") or "").strip()
    if not content:
        return {"error": "content is required"}
    voice = input.get("brand_voice", "neutral and informative")
    try:
        thread = handlers.generate_twitter_thread(content, voice=voice, length=input.get("thread_length", 6), keys=keys)
        linkedin = handlers.generate_linkedin_post(content, voice=voice, keys=keys)
        insta = handlers.generate_instagram_caption(content, voice=voice, hashtags=input.get("include_hashtags", True), keys=keys)
        return {"twitter_thread": thread, "linkedin_post": linkedin, "instagram_caption": insta}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
""".strip(),
    },

    # ─────────────── Stripe / billing automation ───────────────
    {
        "id": "stripe_billing",
        "keywords": [
            "invoice", "stripe", "overdue", "payment", "billing",
            "chase", "follow-up", "collections", "receipt",
        ],
        "planner_excerpt": {
            "files": [
                {"path": "main.py",          "purpose": "Orchestrate Stripe pull → filter overdue → draft → optional send"},
                {"path": "handlers.py",      "purpose": "Stripe API wrapper, severity classifier, email drafter"},
                {"path": "config.py",        "purpose": "Severity thresholds, tone presets"},
                {"path": "requirements.txt", "purpose": "stripe, httpx, pydantic"},
                {"path": ".env.example",     "purpose": "STRIPE_API_KEY, GMAIL_TOKEN (optional)"},
            ],
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Manual",         "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "action",    "label": "List Invoices",  "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "transform", "label": "Filter Overdue", "position": {"x": 700, "y": 120}},
                {"id": "n4", "type": "llm",       "label": "Draft Reminder", "position": {"x": 1000, "y": 120}},
                {"id": "n5", "type": "condition", "label": "Auto-send?",     "position": {"x": 1300, "y": 120}},
                {"id": "n6", "type": "action",    "label": "Send Email",     "position": {"x": 1600, "y": 60}},
                {"id": "n7", "type": "database",  "label": "Log Draft",      "position": {"x": 1600, "y": 200}},
            ],
            "edges": [
                {"id": "e1-2", "source": "n1", "target": "n2"},
                {"id": "e2-3", "source": "n2", "target": "n3"},
                {"id": "e3-4", "source": "n3", "target": "n4"},
                {"id": "e4-5", "source": "n4", "target": "n5"},
                {"id": "e5-6", "source": "n5", "target": "n6"},
                {"id": "e5-7", "source": "n5", "target": "n7"},
            ],
        },
        "builder_excerpt": """
def run(input: dict, env: dict = None, keys: dict = None) -> dict:
    env = env or {}; keys = keys or {}
    stripe_key = keys.get("STRIPE_API_KEY") or env.get("STRIPE_API_KEY") or os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        return {"error": "STRIPE_API_KEY missing — set in your environment or BYOK vault."}
    try:
        invoices = handlers.list_invoices(stripe_key, status="open")
        overdue = handlers.filter_overdue(invoices, days_min=input.get("days_overdue_min", 3))
        drafts = [handlers.draft_chase_email(inv, tone=input.get("tone", "polite but firm")) for inv in overdue]
        return {"invoices_found": len(invoices), "overdue": len(overdue), "drafts_generated": len(drafts), "details": drafts}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
""".strip(),
    },

    # ─────────────── Meeting / transcript extraction ───────────────
    {
        "id": "meeting_notes",
        "keywords": [
            "meeting", "notes", "action items", "transcript",
            "summary", "decisions", "follow-up", "standup",
            "tasks", "extract",
        ],
        "planner_excerpt": {
            "files": [
                {"path": "main.py",          "purpose": "run() — accept transcript, return {summary, decisions, action_items, open_questions}"},
                {"path": "handlers.py",      "purpose": "LLM extraction with strict JSON schema"},
                {"path": "config.py",        "purpose": "Prompt templates, priority rules"},
                {"path": "requirements.txt", "purpose": "openai or google-genai, pydantic"},
                {"path": ".env.example",     "purpose": "OPENAI_API_KEY"},
            ],
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Input Transcript", "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "transform", "label": "Chunk",            "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",       "label": "Extract",          "position": {"x": 700, "y": 120}},
                {"id": "n4", "type": "transform", "label": "Format Output",    "position": {"x": 1000, "y": 120}},
                {"id": "n5", "type": "action",    "label": "Send (optional)",  "position": {"x": 1300, "y": 120}},
            ],
            "edges": [
                {"id": "e1-2", "source": "n1", "target": "n2"},
                {"id": "e2-3", "source": "n2", "target": "n3"},
                {"id": "e3-4", "source": "n3", "target": "n4"},
                {"id": "e4-5", "source": "n4", "target": "n5"},
            ],
        },
        "builder_excerpt": """
def run(input: dict, env: dict = None, keys: dict = None) -> dict:
    env = env or {}; keys = keys or {}
    transcript = (input.get("transcript") or "").strip()
    if not transcript:
        return {"error": "transcript is required"}
    try:
        extracted = handlers.extract_notes(transcript, title=input.get("meeting_title", ""), participants=input.get("participants", []), keys=keys)
        return extracted  # {summary, key_decisions, action_items, open_questions}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
""".strip(),
    },

    # ─────────────── Slack / webhook posting ───────────────
    {
        "id": "slack_notifier",
        "keywords": [
            "slack", "notify", "webhook", "channel", "post",
            "alert", "discord", "teams", "broadcast",
        ],
        "planner_excerpt": {
            "files": [
                {"path": "main.py",          "purpose": "run() — POST a formatted message to a Slack webhook URL"},
                {"path": "handlers.py",      "purpose": "Block-Kit formatting, retry-with-backoff"},
                {"path": "config.py",        "purpose": "Channel mapping, message templates"},
                {"path": "requirements.txt", "purpose": "httpx"},
                {"path": ".env.example",     "purpose": "SLACK_WEBHOOK_URL"},
            ],
            "nodes": [
                {"id": "n1", "type": "trigger", "label": "Input",          "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "transform", "label": "Format Blocks","position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "action",  "label": "POST to Slack",  "position": {"x": 700, "y": 120}},
            ],
            "edges": [
                {"id": "e1-2", "source": "n1", "target": "n2"},
                {"id": "e2-3", "source": "n2", "target": "n3"},
            ],
        },
        "builder_excerpt": """
def run(input: dict, env: dict = None, keys: dict = None) -> dict:
    env = env or {}; keys = keys or {}
    url = keys.get("SLACK_WEBHOOK_URL") or env.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return {"error": "SLACK_WEBHOOK_URL missing."}
    try:
        payload = handlers.build_blocks(input.get("title", ""), input.get("body", ""), input.get("color", "good"))
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=payload)
        return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
""".strip(),
    },
]


def _score(example: Dict[str, Any], prompt_lower: str) -> int:
    """Sum of keyword hits in the user prompt."""
    return sum(1 for kw in example["keywords"] if kw in prompt_lower)


def pick_example(user_prompt: str) -> Dict[str, Any] | None:
    """Return the best-matching golden example for this user prompt, or None.

    Threshold: at least 1 keyword must match. Ties broken by the order in
    GOLDEN_EXAMPLES (earlier wins).
    """
    if not user_prompt:
        return None
    prompt_lower = user_prompt.lower()
    best, best_score = None, 0
    for ex in GOLDEN_EXAMPLES:
        s = _score(ex, prompt_lower)
        if s > best_score:
            best_score = s
            best = ex
    return best if best_score >= 1 else None


def planner_hint(user_prompt: str) -> str:
    """Compact reference block to splice into the Planner system/user message.
    Returns "" when no example matches — caller should fall back to a plain prompt.
    """
    import json
    ex = pick_example(user_prompt)
    if not ex:
        return ""
    return (
        f"\n\nREFERENCE EXAMPLE (pattern: {ex['id']}). Use this as a SHAPE GUIDE — "
        "the user's intent may differ; adapt nodes/files to match it, not copy.\n"
        f"```json\n{json.dumps(ex['planner_excerpt'], indent=2)}\n```\n"
    )


def builder_hint(user_prompt: str) -> str:
    """Compact reference block to splice into the Builder system/user message."""
    ex = pick_example(user_prompt)
    if not ex:
        return ""
    return (
        f"\n\nREFERENCE IMPLEMENTATION (pattern: {ex['id']}). Mirror this style for "
        "main.py's `run()` — return dict shape, error handling, key resolution order. "
        "Adapt to the user's actual integrations.\n"
        f"```python\n{ex['builder_excerpt']}\n```\n"
    )


__all__ = ["GOLDEN_EXAMPLES", "pick_example", "planner_hint", "builder_hint"]
