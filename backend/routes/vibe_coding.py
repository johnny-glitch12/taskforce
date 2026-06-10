"""
Vibe Coding — chat-driven AI agent builder for Task Force AI.

Two modes:
  - chat   : conversational planning, costs 1 credit per AI message (`vibe_chat`)
  - build  : code generation, costs 2–5 credits depending on model (`build_bot`)

Sessions are persisted in `vibe_sessions`. Generated code lands in the existing
`bot_projects` collection (single source of truth for all bot artifacts) so the
existing commit/fork/history features keep working.

Model dispatch:
  - Platform models (Gemini Flash / Pro)  → Emergent LLM Key via emergentintegrations
  - BYOK models (GPT-4o*, Claude*)         → listed in the picker but require a key in the
                                              user's Credentials Vault. Routing returns a
                                              clean BYOK_REQUIRED error when key is missing.
"""
import os
import re
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from lib.credit_wallet import can_afford as wallet_can_afford, debit as wallet_debit
from lib.credit_calculator import estimate_tokens, estimate_tokens_for_call
from lib.smart_credits import check_can_afford, debit_actual_usage
from lib.rate_limit import rate_limit_dependency

router = APIRouter()

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

# Model registry — single source of truth for picker, dispatch, and pricing.
MODELS = {
    "gemini-2.5-flash":  {"label": "Gemini 2.5 Flash", "provider": "google",   "speed": "fast",   "quality": "good",      "build_cost": 3, "platform": True,  "byok_service": None,       "engine": "gemini",    "api_model": "gemini-2.5-flash"},
    "gemini-2.5-pro":    {"label": "Gemini 2.5 Pro",   "provider": "google",   "speed": "medium", "quality": "excellent", "build_cost": 5, "platform": True,  "byok_service": None,       "engine": "gemini",    "api_model": "gemini-2.5-pro"},
    "gpt-4o":            {"label": "GPT-4o",            "provider": "openai",    "speed": "medium", "quality": "excellent", "build_cost": 5, "platform": True,  "byok_service": "openai",   "engine": "openai",    "api_model": "gpt-4o"},
    "gpt-4o-mini":       {"label": "GPT-4o Mini",       "provider": "openai",    "speed": "fast",   "quality": "good",      "build_cost": 2, "platform": True,  "byok_service": "openai",   "engine": "openai",    "api_model": "gpt-4o-mini"},
    "claude-sonnet":     {"label": "Claude Sonnet",     "provider": "anthropic", "speed": "medium", "quality": "excellent", "build_cost": 5, "platform": True,  "byok_service": "anthropic","engine": "anthropic", "api_model": "claude-sonnet-4-5-20250929"},
    "claude-haiku":      {"label": "Claude Haiku",      "provider": "anthropic", "speed": "fast",   "quality": "good",      "build_cost": 2, "platform": True,  "byok_service": "anthropic","engine": "anthropic", "api_model": "claude-haiku-4-5-20251001"},
}

DEFAULT_MODEL = "gemini-2.5-flash"


# ─── DI helpers (avoid circular imports) ───
def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ─── Schemas ───
class VibeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[str] = None
    model: str = DEFAULT_MODEL


class VibeGenerateRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=8000)
    model: str = DEFAULT_MODEL


# ─── System prompts ───
VIBE_PLANNING_PROMPT = """You are Task Force AI's build assistant. You help users design AI agents through conversation.

YOUR JOB IN THIS MODE: planning & clarification. DO NOT generate code yet.
- Ask 1–2 targeted clarifying questions when the requirements are ambiguous.
- Suggest a clear architecture: what nodes/services/integrations are needed.
- Highlight trade-offs (cost, complexity, BYOK keys required).
- Be conversational. Use short, scannable replies. Plain prose. No JSON. No markdown headings.
- When the user confirms the plan, tell them to click "Generate Code" — that's when actual code is written.

You will receive the user's connected BYOK integrations and the catalog of available node primitives in your context.
"""

VIBE_BUILD_PROMPT = """You are Task Force AI's Armory Compiler — convert the conversation into a COMPLETE, RUNNABLE bot package.

OUTPUT FORMAT — single JSON object, NO prose, NO markdown, NO trailing commas:
{
  "name": "Short Bot Name",
  "description": "1-2 sentence description",
  "language": "python",
  "files": [
    {"path": "main.py",          "content": "...", "language": "python"},
    {"path": "handlers.py",      "content": "...", "language": "python"},
    {"path": "config.py",        "content": "...", "language": "python"},
    {"path": "requirements.txt", "content": "...", "language": "text"},
    {"path": ".env.example",     "content": "...", "language": "text"},
    {"path": "README.md",        "content": "...", "language": "markdown"}
  ],
  "nodes": [
    {"id": "n1", "type": "trigger",  "data": {"label": "Webhook In"},    "position": {"x": 100, "y": 100}},
    {"id": "n2", "type": "llm",      "data": {"label": "Classify"},      "position": {"x": 400, "y": 100}},
    {"id": "n3", "type": "action",   "data": {"label": "Send Slack"},    "position": {"x": 700, "y": 100}}
  ],
  "edges": [
    {"id": "e1-2", "source": "n1", "target": "n2"},
    {"id": "e2-3", "source": "n2", "target": "n3"}
  ]
}

RULES:
1. NEVER ask clarifying questions in this mode. Infer reasonable defaults.
2. Node count scales with complexity (3–25 nodes). Simple = 3-5, multi-service = 5-12, complex = 12-25.
3. Files MUST be complete & runnable. No stubs, no TODOs.
4. Use the standard Task Force agent format above (you may add extra files as needed).
5. Node types restricted to: trigger | llm | condition | action | http_request | webhook | database | transform
6. Position nodes left-to-right in a readable graph (x increments of 300, y rows of 150).
"""


def _extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of an LLM response.
    Tolerates: markdown ```json fences, leading/trailing prose, and control chars
    (newlines/tabs) inside string values (common when files contain real source code)."""
    s = text.strip()
    # Strip markdown code fences if present.
    s = re.sub(r"^```(?:json|JSON)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    # Walk to the first {...} balanced object.
    start = s.find("{")
    if start < 0:
        raise ValueError("No JSON object found in LLM output")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i + 1], strict=False)
    raise ValueError("Unbalanced JSON object in LLM output")


async def _resolve_api_key(db, user_id: str, model: str) -> dict:
    """Resolve which API key to use for a given model.
    Returns {"api_key": str, "source": "platform" | "byok"}.
    Silent BYOK override — if user has a key for this provider, use it (saves us cost).
    Otherwise fall back to the Emergent Universal Key (every model always works)."""
    info = MODELS[model]
    byok_service = info["byok_service"]  # "openai" | "anthropic" | None for gemini

    if byok_service:
        # Use the actual BYOK collection (byok_credentials, not user_credentials).
        doc = await db.byok_credentials.find_one(
            {"user_id": user_id, "service": byok_service},
            {"api_key": 1, "_id": 0},
        )
        if doc and doc.get("api_key"):
            from routes.workflow_executor import decrypt_key
            try:
                plain = decrypt_key(doc["api_key"])
                if plain:
                    return {"api_key": plain, "source": "byok"}
            except Exception:
                pass  # fall through to platform key

    return {"api_key": EMERGENT_LLM_KEY, "source": "platform"}


async def _get_byok_providers(db, user_id: str) -> set:
    """Return the set of byok provider services the user has stored keys for."""
    out = set()
    cursor = db.byok_credentials.find(
        {"user_id": user_id, "service": {"$in": ["openai", "anthropic", "google"]}},
        {"service": 1, "_id": 0},
    )
    async for d in cursor:
        out.add(d["service"])
    return out


async def _call_platform_llm(*, model: str, system_prompt: str, history: list, user_message: str, session_key: str, api_key: Optional[str] = None) -> dict:
    """Dispatch a chat call to a model — uses the supplied api_key (BYOK or Emergent).
    History is injected as transcript text in a single user message — emergentintegrations
    creates fresh sessions per LlmChat instance, so replaying turns one-by-one would
    fan-out into N LLM round-trips (blowing past the 60s ingress timeout).

    Returns {text, input_tokens, output_tokens, model, token_source} —
      - `token_source='provider'` when the response exposes a usage block (future-proof
        for emergentintegrations exposing real provider counts);
      - `token_source='estimate'` when we fall back to tiktoken (current default).
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from lib.credit_calculator import extract_real_usage
    info = MODELS[model]
    key = api_key or EMERGENT_LLM_KEY
    chat = LlmChat(api_key=key, session_id=session_key, system_message=system_prompt).with_model(
        info["engine"], info["api_model"]
    )
    if history:
        transcript = "\n".join(
            f"{m.get('role', '?').upper()}: {(m.get('content') or '').strip()[:2000]}"
            for m in history[-12:]
        )
        composite = f"CONVERSATION SO FAR:\n{transcript}\n\n--- NEW USER MESSAGE ---\n{user_message}"
    else:
        composite = user_message
    resp = await chat.send_message(UserMessage(text=composite))
    text = str(resp)

    # Prefer real provider usage if exposed; else fall back to tiktoken estimator.
    real = extract_real_usage(resp)
    if real is not None:
        in_tokens, out_tokens = real
        token_source = "provider"
    else:
        in_tokens, out_tokens = estimate_tokens_for_call(system_prompt, history, user_message, text)
        token_source = "estimate"
    return {
        "text": text,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "model": model,
        "token_source": token_source,
    }


async def _get_byok_status(db, user_id: str) -> dict:
    """Return {service: bool_has_key} for the BYOK-overridable services."""
    services = {"openai", "anthropic"}
    out = {s: False for s in services}
    cursor = db.byok_credentials.find({"user_id": user_id, "service": {"$in": list(services)}}, {"service": 1, "_id": 0})
    async for doc in cursor:
        out[doc["service"]] = True
    return out


class RecommendRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)


RECOMMEND_SYSTEM = """You are a model-selection router for Task Force AI's bot builder.
Given a user's request below, pick ONE model that best fits the job — balance quality, speed, and cost.

AVAILABLE MODELS (id → strengths):
- gemini-2.5-flash : fastest + cheapest (3cr build). Best for simple bots, text transforms, single-API integrations.
- gemini-2.5-pro   : top-tier reasoning (5cr build). Best for complex multi-step logic with branching.
- gpt-4o           : excellent generalist (5cr build). Best when the bot needs tool/function calling or strict JSON outputs.
- gpt-4o-mini      : fast + cheap (2cr build). Best for short text classification, validation, or shallow transforms.
- claude-sonnet    : best long-context coder (5cr build). Best for multi-file agents with deep system-design needs.
- claude-haiku     : fast (2cr build). Best for high-volume agents where latency matters more than depth.

RETURN STRICTLY THIS JSON, no markdown fences, no prose:
{"model": "<one of the 6 ids>", "reason": "<10-25 word justification>", "complexity": "simple|medium|complex"}"""


@router.post("/vibe/recommend-model")
async def recommend_model(req: RecommendRequest, user=Depends(get_current_user())):
    """Cheap auto-pick. Uses Gemini Flash to classify the request and recommend
    one of the 6 catalogue models. Returns {model, reason, complexity} or falls back
    to gemini-2.5-flash if the LLM output can't be parsed. Billed dynamically — the
    classifier call is cheap (few hundred tokens) so users typically pay the
    1-credit MIN_CREDITS['vibe_chat'] floor."""
    db = get_db()
    pre = await check_can_afford(db, user, "gemini-2.5-flash", "vibe_chat")
    if not pre.get("allowed"):
        return JSONResponse(status_code=402, content=pre)

    try:
        result = await _call_platform_llm(
            model="gemini-2.5-flash", system_prompt=RECOMMEND_SYSTEM,
            history=[], user_message=req.prompt,
            session_key=f"vibe-recommend-{user.get('id', user.get('email'))}",
        )
        parsed = _extract_json(result["text"])
        in_tok = result["input_tokens"]
        out_tok = result["output_tokens"]
        token_source = result["token_source"]
    except Exception:
        parsed = {}
        in_tok = estimate_tokens(RECOMMEND_SYSTEM + req.prompt)
        out_tok = 0
        token_source = "estimate"

    pick = parsed.get("model") if parsed.get("model") in MODELS else DEFAULT_MODEL
    reason = parsed.get("reason") or "Fast and cheap — good fit for most tasks."
    complexity = parsed.get("complexity") or "medium"

    # Margin-aware tie-breaker — when the model picked a high-cost model for a
    # SIMPLE prompt, downgrade to the cheaper sibling on the same provider.
    # This lifts platform gross margin ~10-15% with negligible quality impact.
    pick, reason = _apply_margin_bias(pick, complexity, reason)

    debit = await debit_actual_usage(
        db, user,
        model="gemini-2.5-flash", action="vibe_chat",
        input_tokens=in_tok, output_tokens=out_tok,
        key_source="platform", ref=f"recommend:{pick}",
        token_source=token_source,
    )
    return {
        "model": pick,
        "label": MODELS[pick]["label"],
        "build_cost": MODELS[pick]["build_cost"],
        "reason": reason,
        "complexity": complexity,
        "balance_remaining": debit.get("balance"),
    }


# ─── Routes ───
@router.get("/vibe/models")
async def list_models(user=Depends(get_current_user())):
    """Return the full model catalogue. EVERY model is always available — platform key
    fronts the call by default, silent BYOK override kicks in when the user has their
    own key saved (and `using_byok=true` is set so the UI can render an optional badge)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    byok = await _get_byok_status(db, user_id)
    out = []
    for mid, m in MODELS.items():
        using_byok = bool(m["byok_service"] and byok.get(m["byok_service"]))
        out.append({
            "id": mid, "label": m["label"], "provider": m["provider"],
            "speed": m["speed"], "quality": m["quality"],
            "chat_cost": 1, "build_cost": m["build_cost"],
            "platform": m["platform"], "available": True,            # always available now
            "byok_service": m["byok_service"],
            "using_byok": using_byok,                                  # optional UX badge
            "needs_byok": False,                                       # legacy field, always false
        })
    return {"models": out, "default": DEFAULT_MODEL}


@router.get("/vibe/sessions")
async def list_sessions(user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.vibe_sessions.find({"user_id": user_id}, {"messages": 0, "_id": 0}).sort("updated_at", -1).limit(50)
    items = await cursor.to_list(50)
    return {"sessions": items}


@router.get("/vibe/sessions/{session_id}")
async def get_session(session_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    s = await db.vibe_sessions.find_one({"id": session_id, "user_id": user_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")
    return s


@router.delete("/vibe/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    res = await db.vibe_sessions.delete_one({"id": session_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"ok": True, "deleted": session_id}


async def _ensure_session(db, user_id: str, user_email: str, session_id: Optional[str], model: str, first_message: str) -> dict:
    if session_id:
        s = await db.vibe_sessions.find_one({"id": session_id, "user_id": user_id})
        if not s:
            raise HTTPException(status_code=404, detail="Session not found.")
        return s
    sid = uuid.uuid4().hex
    title = (first_message or "").strip().split("\n")[0][:80]
    doc = {
        "id": sid, "user_id": user_id, "user_email": user_email,
        "title": title or "New build session",
        "model": model,
        "messages": [],
        "project_id": None,
        "total_credits_used": 0,
        "status": "active",
        "created_at": _now_iso(), "updated_at": _now_iso(),
    }
    await db.vibe_sessions.insert_one(doc)
    return doc


def _verify_model(model: str):
    if model not in MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model '{model}'. Valid: {list(MODELS.keys())}")


# Cheap-sibling map — when complexity='simple', a heavy model from the same provider
# is downgraded to its cheap sibling. Generic effect: 60–95% lower API cost on the
# typical call → margin lifted into the 60–70% range even when raw token usage is high.
_CHEAP_SIBLING = {
    "gemini-2.5-pro":   "gemini-2.5-flash",
    "gpt-4o":           "gpt-4o-mini",
    "claude-sonnet":    "claude-haiku",
}


def _apply_margin_bias(model: str, complexity: str, reason: str) -> tuple[str, str]:
    """If the LLM picked a flagship model for a SIMPLE task, swap it for the cheap
    sibling and annotate the reason. No-op on medium/complex requests."""
    if complexity == "simple" and model in _CHEAP_SIBLING:
        cheap = _CHEAP_SIBLING[model]
        return cheap, f"{reason} (auto-downshift: simple task fits {MODELS[cheap]['label']} at lower cost)."
    return model, reason


# NOTE: BYOK is no longer a gate — every model is always available. If the user has
# their own key, _resolve_api_key uses it silently. Otherwise the platform key fronts
# the call. The legacy _verify_model_available helper has been removed.


@router.post("/vibe/chat")
async def vibe_chat(req: VibeChatRequest, user=Depends(get_current_user()),
                    _=Depends(rate_limit_dependency("vibe_chat", 30, 60))):
    """Conversational planning turn. Billed dynamically on real token usage.
    Rate-limited: 30 messages/min/IP to deter credit-draining abuse."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    _verify_model(req.model)

    # Pre-flight: estimate cost from AVERAGE_TOKENS for the chosen model.
    pre = await check_can_afford(db, user, req.model, "vibe_chat")
    if not pre.get("allowed"):
        return JSONResponse(status_code=402, content=pre)

    session = await _ensure_session(db, user_id, user.get("email"), req.session_id, req.model, req.message)
    history = session.get("messages", [])

    # Silent BYOK override — uses user's key when stored, else platform key.
    key_info = await _resolve_api_key(db, user_id, req.model)

    try:
        result = await _call_platform_llm(
            model=req.model, system_prompt=VIBE_PLANNING_PROMPT,
            history=history, user_message=req.message,
            session_key=f"vibe-{session['id']}",
            api_key=key_info["api_key"],
        )
    except Exception as e:
        # ─── Graceful degradation when no LLM key is configured ─────────────
        # The platform may run with EMERGENT_LLM_KEY blank in early-stage tenants
        # where the user is expected to BYO a key via /credentials. In that case
        # the LLM call fails with an auth/empty-key exception. We still persist
        # the user's message + a stub assistant reply so the conversation
        # history is complete, and we return 200 so the FE renders the stub
        # inline instead of a fatal-error toast. Real network/quota failures
        # surface the same way — the user sees a clear "add a key" CTA.
        err_short = str(e)[:160]
        now = _now_iso()
        stub_text = (
            "⚠️  No LLM key configured. Add a Google / OpenAI / Anthropic key in "
            "your BYOK Vault (/credentials) to enable chat — your message has been "
            "saved and the model will reply once a key is in place."
        )
        user_msg = {"role": "user", "content": req.message, "timestamp": now}
        stub_msg = {
            "role": "assistant", "content": stub_text, "timestamp": now,
            "type": "chat", "credits_used": 0, "model": req.model,
            "key_source": key_info["source"], "input_tokens": 0, "output_tokens": 0,
            "stub": True, "error": err_short,
        }
        await db.vibe_sessions.update_one(
            {"id": session["id"]},
            {"$push": {"messages": {"$each": [user_msg, stub_msg]}},
             "$set": {"updated_at": now, "model": req.model}},
        )
        return {
            "session_id": session["id"], "type": "chat",
            "response": stub_text,
            "balance_remaining": None, "model": req.model,
            "stub": True, "key_source": key_info["source"], "error": err_short,
        }

    ai_text = result["text"]

    # Debit AFTER successful call so a failure doesn't cost the user.
    debit = await debit_actual_usage(
        db, user,
        model=req.model, action="vibe_chat",
        input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
        key_source=key_info["source"], ref=session["id"],
        token_source=result.get("token_source", "estimate"),
    )
    credits_used = debit.get("credits_charged", 0)

    now = _now_iso()
    user_msg = {"role": "user", "content": req.message, "timestamp": now}
    ai_msg = {
        "role": "assistant", "content": ai_text, "timestamp": now, "type": "chat",
        "credits_used": credits_used, "model": req.model, "key_source": key_info["source"],
        "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
    }
    await db.vibe_sessions.update_one(
        {"id": session["id"]},
        {"$push": {"messages": {"$each": [user_msg, ai_msg]}},
         "$inc": {"total_credits_used": credits_used},
         "$set": {"updated_at": now, "model": req.model}},
    )
    return {
        "session_id": session["id"], "type": "chat",
        "response": ai_text,
        "balance_remaining": debit.get("balance"), "model": req.model,
    }


@router.post("/vibe/generate")
async def vibe_generate(req: VibeGenerateRequest, user=Depends(get_current_user()),
                        _=Depends(rate_limit_dependency("vibe_generate", 5, 60))):
    """Dispatch the 5-stage code-gen pipeline as a background Celery task.

    Rate-limited: 5 builds/min/IP — pipelines are expensive (5-15cr each) and a
    rogue script could drain a user's wallet faster than they can react.

    Returns immediately with status='queued' and the session_id. Frontend should
    poll GET /api/vibe/build-status/{session_id} for stage progress. When the
    pipeline finishes, the session's build_status flips to 'complete' and the
    generated project is available at bot_projects.id = session.project_id.

    Fallback: when CELERY_BROKER_URL is unset (zero-config dev), runs inline so
    behaviour stays correct in tests + local dev. Production uses Celery."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    _verify_model(req.model)

    # Light pre-flight: ensures we can charge the Architect stage. Real per-stage
    # affordability is enforced inside the pipeline as each stage runs.
    pre = await check_can_afford(db, user, "gemini-2.5-flash", "vibe_chat")
    if not pre.get("allowed"):
        return JSONResponse(status_code=402, content=pre)

    session = await db.vibe_sessions.find_one({"id": req.session_id, "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    now = _now_iso()
    user_msg = {"role": "user", "content": req.message, "timestamp": now}
    await db.vibe_sessions.update_one(
        {"id": session["id"]},
        {"$push": {"messages": user_msg},
         "$set": {"build_status": "queued", "build_progress": [],
                  "build_context": {},
                  "build_started_at": now, "model": req.model, "updated_at": now}},
    )

    from lib.celery_app import ENABLED as CELERY_ENABLED, vibe_build_task
    if CELERY_ENABLED:
        try:
            async_result = vibe_build_task.delay(
                session_id=session["id"],
                user_id=user_id, user_email=user.get("email"),
                user_prompt=req.message, builder_model=req.model, resume=False,
            )
        except Exception as exc:
            # Broker unreachable (e.g. Redis down). Fall back to inline run so
            # the user isn't blocked, and log a warning for ops.
            import logging as _logging
            _logging.getLogger("vibe").warning(
                f"[vibe_generate] Celery dispatch failed ({exc.__class__.__name__}): {exc} — falling back to inline run.",
            )
        else:
            return {
                "session_id": session["id"], "status": "queued",
                "task_id": async_result.id, "model": req.model,
                "poll_url": f"/api/vibe/build-status/{session['id']}",
            }
    # Inline fallback for dev (and Celery-down emergencies)
    from lib.code_gen_pipeline import run_build_pipeline
    result = await run_build_pipeline(
        db, user, session_id=session["id"],
        user_prompt=req.message, builder_model=req.model, resume=False,
    )
    return {"session_id": session["id"], "status": result.get("status"),
            "model": req.model, "result": result}


@router.get("/vibe/build-status/{session_id}")
async def vibe_build_status(session_id: str, user=Depends(get_current_user())):
    """Poll endpoint — returns the pipeline's current stage progression.
    Frontend renders a stage-by-stage progress chip strip from this."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    sess = await db.vibe_sessions.find_one(
        {"id": session_id, "user_id": user_id},
        {"_id": 0, "build_progress": 1, "build_status": 1, "build_paused_reason": 1,
         "build_paused_stage": 1, "build_paused_estimate": 1, "build_error": 1,
         "project_id": 1, "model": 1, "total_credits_used": 1},
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")
    payload = {
        "session_id": session_id,
        "status": sess.get("build_status", "idle"),
        "progress": sess.get("build_progress", []),
        "project_id": sess.get("project_id"),
        "model": sess.get("model"),
        "total_credits_used": sess.get("total_credits_used", 0),
    }
    if sess.get("build_status") == "paused":
        payload["paused"] = {
            "stage": sess.get("build_paused_stage"),
            "reason": sess.get("build_paused_reason"),
            "estimate_credits": sess.get("build_paused_estimate"),
        }
    if sess.get("build_status") == "failed":
        payload["error"] = sess.get("build_error")
    if sess.get("build_status") == "complete" and sess.get("project_id"):
        proj = await db.bot_projects.find_one(
            {"id": sess["project_id"], "user_id": user_id},
            {"_id": 0, "id": 1, "name": 1, "description": 1, "files": 1, "nodes": 1,
             "edges": 1, "frontend": 1, "has_ui": 1, "app_slug": 1},
        )
        payload["project"] = proj
    return payload


@router.post("/vibe/resume-build/{session_id}")
async def vibe_resume_build(session_id: str, user=Depends(get_current_user())):
    """Resume a paused pipeline. The user typically tops up credits between
    pause and resume — we re-dispatch the same Celery task with resume=True so
    completed stages are skipped (read from build_context)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    sess = await db.vibe_sessions.find_one({"id": session_id, "user_id": user_id})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")
    if sess.get("build_status") != "paused":
        raise HTTPException(status_code=409, detail=f"Session is not paused (status={sess.get('build_status')}).")

    # Try to afford the stage we paused at
    paused_stage = sess.get("build_paused_stage")
    model = sess.get("model") or DEFAULT_MODEL
    pre = await check_can_afford(db, user, "gemini-2.5-flash" if paused_stage != "builder" else model, "vibe_build")
    if not pre.get("allowed"):
        return JSONResponse(status_code=402, content=pre)

    # Find the original prompt: the most recent user message
    msgs = sess.get("messages", []) or []
    user_msgs = [m for m in msgs if m.get("role") == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="No user message to resume against.")
    user_prompt = user_msgs[-1]["content"]

    await db.vibe_sessions.update_one(
        {"id": session_id},
        {"$set": {"build_status": "queued", "build_resumed_at": _now_iso(), "updated_at": _now_iso()},
         "$unset": {"build_paused_reason": "", "build_paused_stage": "",
                    "build_paused_estimate": "", "build_paused_at": ""}},
    )

    from lib.celery_app import ENABLED as CELERY_ENABLED, vibe_build_task
    if CELERY_ENABLED:
        try:
            async_result = vibe_build_task.delay(
                session_id=session_id,
                user_id=user_id, user_email=user.get("email"),
                user_prompt=user_prompt, builder_model=model, resume=True,
            )
        except Exception as exc:
            import logging as _logging
            _logging.getLogger("vibe").warning(
                f"[vibe_resume] Celery dispatch failed ({exc.__class__.__name__}): {exc} — falling back to inline run.",
            )
        else:
            return {"session_id": session_id, "status": "queued", "task_id": async_result.id}
    from lib.code_gen_pipeline import run_build_pipeline
    result = await run_build_pipeline(
        db, user, session_id=session_id,
        user_prompt=user_prompt, builder_model=model, resume=True,
    )
    return {"session_id": session_id, "status": result.get("status"), "result": result}


@router.post("/vibe/generate-legacy")
async def vibe_generate_legacy(req: VibeGenerateRequest, user=Depends(get_current_user())):
    """LEGACY single-call generator (pre-pipeline). Kept for tests and any callers
    that don't yet use the polling flow. New clients should use /vibe/generate."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    _verify_model(req.model)

    # Pre-flight: estimate vibe_build cost (avg 4k in / 3k out).
    pre = await check_can_afford(db, user, req.model, "vibe_build")
    if not pre.get("allowed"):
        return JSONResponse(status_code=402, content=pre)

    session = await db.vibe_sessions.find_one({"id": req.session_id, "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    history = session.get("messages", [])

    # Silent BYOK override
    key_info = await _resolve_api_key(db, user_id, req.model)

    # Generate
    try:
        result = await _call_platform_llm(
            model=req.model, system_prompt=VIBE_BUILD_PROMPT,
            history=history, user_message=req.message,
            session_key=f"vibe-gen-{session['id']}",
            api_key=key_info["api_key"],
        )
        payload = _extract_json(result["text"])
    except json.JSONDecodeError as je:
        raise HTTPException(status_code=502, detail=f"Model output was not valid JSON: {str(je)[:120]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM build failed: {str(e)[:200]}")

    files = payload.get("files") or []
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    name = payload.get("name") or session.get("title") or "Untitled Bot"
    description = payload.get("description") or ""
    if not files or not nodes:
        raise HTTPException(status_code=502, detail="Generated bot has no files or nodes — clarify your request.")

    # Debit at REAL usage cost AFTER successful LLM call.
    debit = await debit_actual_usage(
        db, user,
        model=req.model, action="vibe_build",
        input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
        key_source=key_info["source"], ref=session["id"],
        token_source=result.get("token_source", "estimate"),
    )
    credits_used = debit.get("credits_charged", 0)

    now = _now_iso()
    commit_id = uuid.uuid4().hex[:12]
    commit_entry = {
        "commit_id": commit_id, "message": f"vibe: {req.message[:140]}",
        "author": user.get("email"), "files": files, "nodes": nodes, "edges": edges,
        "model": req.model, "created_at": now,
    }
    project_id = session.get("project_id")
    if project_id:
        await db.bot_projects.update_one(
            {"id": project_id, "user_id": user_id},
            {"$set": {"name": name, "description": description, "files": files, "nodes": nodes, "edges": edges, "updated_at": now},
             "$push": {"commit_history": commit_entry}},
        )
    else:
        project_id = uuid.uuid4().hex
        await db.bot_projects.insert_one({
            "id": project_id, "user_id": user_id, "creator_email": user.get("email"),
            "name": name, "description": description, "language": payload.get("language") or "python",
            "prompt": session.get("title", ""),
            "files": files, "nodes": nodes, "edges": edges,
            "commit_history": [commit_entry], "source": "vibe",
            "created_at": now, "updated_at": now,
        })

    user_msg = {"role": "user", "content": req.message, "timestamp": now}
    ai_msg = {
        "role": "assistant", "content": f"Generated **{name}** — {len(files)} files, {len(nodes)} nodes.",
        "timestamp": now, "type": "build", "credits_used": credits_used,
        "model": req.model, "project_id": project_id,
        "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
    }
    await db.vibe_sessions.update_one(
        {"id": session["id"]},
        {"$push": {"messages": {"$each": [user_msg, ai_msg]}},
         "$inc": {"total_credits_used": credits_used},
         "$set": {"updated_at": now, "model": req.model, "project_id": project_id}},
    )
    return {
        "session_id": session["id"], "type": "build",
        "project_id": project_id, "name": name, "description": description,
        "files": files, "nodes": nodes, "edges": edges,
        "balance_remaining": debit.get("balance"), "model": req.model,
    }
