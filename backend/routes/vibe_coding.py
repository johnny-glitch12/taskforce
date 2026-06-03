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


async def _call_platform_llm(*, model: str, system_prompt: str, history: list, user_message: str, session_key: str, api_key: Optional[str] = None) -> str:
    """Dispatch a chat call to a model — uses the supplied api_key (BYOK or Emergent).
    History is injected as transcript text in a single user message — emergentintegrations
    creates fresh sessions per LlmChat instance, so replaying turns one-by-one would
    fan-out into N LLM round-trips (blowing past the 60s ingress timeout)."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
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
    return str(resp)


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
    """Cheap auto-pick. Uses Gemini Flash (1cr) to classify the request and recommend
    one of the 6 catalogue models. Returns {model, reason, complexity} or falls back
    to gemini-2.5-flash if the LLM output can't be parsed."""
    db = get_db()
    check = await wallet_can_afford(db, user, "vibe_chat")
    if not check.get("allowed"):
        return JSONResponse(status_code=402, content=check)

    try:
        raw = await _call_platform_llm(
            model="gemini-2.5-flash", system_prompt=RECOMMEND_SYSTEM,
            history=[], user_message=req.prompt,
            session_key=f"vibe-recommend-{user.get('id', user.get('email'))}",
        )
        parsed = _extract_json(raw)
    except Exception:
        parsed = {}

    pick = parsed.get("model") if parsed.get("model") in MODELS else DEFAULT_MODEL
    reason = parsed.get("reason") or "Fast and cheap — good fit for most tasks."
    complexity = parsed.get("complexity") or "medium"

    debit = await wallet_debit(db, user, "vibe_chat", ref=f"recommend:{pick}")
    return {
        "model": pick,
        "label": MODELS[pick]["label"],
        "build_cost": MODELS[pick]["build_cost"],
        "reason": reason,
        "complexity": complexity,
        "credits_used": debit["cost"],
        "balance_remaining": debit["balance"],
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


# NOTE: BYOK is no longer a gate — every model is always available. If the user has
# their own key, _resolve_api_key uses it silently. Otherwise the platform key fronts
# the call. The legacy _verify_model_available helper has been removed.


@router.post("/vibe/chat")
async def vibe_chat(req: VibeChatRequest, user=Depends(get_current_user())):
    """Conversational planning turn. 1 credit per AI reply."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    _verify_model(req.model)

    # Credit gate
    check = await wallet_can_afford(db, user, "vibe_chat")
    if not check.get("allowed"):
        return JSONResponse(status_code=402, content=check)

    session = await _ensure_session(db, user_id, user.get("email"), req.session_id, req.model, req.message)
    history = session.get("messages", [])

    # Silent BYOK override — uses user's key when stored, else platform key.
    key_info = await _resolve_api_key(db, user_id, req.model)

    try:
        ai_text = await _call_platform_llm(
            model=req.model, system_prompt=VIBE_PLANNING_PROMPT,
            history=history, user_message=req.message,
            session_key=f"vibe-{session['id']}",
            api_key=key_info["api_key"],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {str(e)[:200]}")

    # Debit AFTER successful call so a failure doesn't cost the user.
    debit = await wallet_debit(db, user, "vibe_chat", ref=session["id"])

    now = _now_iso()
    user_msg = {"role": "user", "content": req.message, "timestamp": now}
    ai_msg = {"role": "assistant", "content": ai_text, "timestamp": now, "type": "chat", "credits_used": debit["cost"], "model": req.model, "key_source": key_info["source"]}
    await db.vibe_sessions.update_one(
        {"id": session["id"]},
        {"$push": {"messages": {"$each": [user_msg, ai_msg]}},
         "$inc": {"total_credits_used": debit["cost"]},
         "$set": {"updated_at": now, "model": req.model}},
    )
    return {
        "session_id": session["id"], "type": "chat",
        "response": ai_text, "credits_used": debit["cost"],
        "balance_remaining": debit["balance"], "model": req.model,
        "key_source": key_info["source"],
    }


@router.post("/vibe/generate")
async def vibe_generate(req: VibeGenerateRequest, user=Depends(get_current_user())):
    """Code-generation turn. Cost = MODELS[model].build_cost. Persists files+nodes to bot_projects."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    _verify_model(req.model)

    # Credit gate against per-model build cost (NOT the flat ACTION_COSTS['build_bot']).
    per_model_cost = MODELS[req.model]["build_cost"]
    check = await wallet_can_afford(db, user, "build_bot", cost_override=per_model_cost)
    if not check.get("allowed"):
        return JSONResponse(status_code=402, content=check)

    session = await db.vibe_sessions.find_one({"id": req.session_id, "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    history = session.get("messages", [])

    # Silent BYOK override
    key_info = await _resolve_api_key(db, user_id, req.model)

    # Generate
    try:
        raw = await _call_platform_llm(
            model=req.model, system_prompt=VIBE_BUILD_PROMPT,
            history=history, user_message=req.message,
            session_key=f"vibe-gen-{session['id']}",
            api_key=key_info["api_key"],
        )
        payload = _extract_json(raw)
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

    # Debit at per-model cost AFTER successful LLM call.
    debit = await wallet_debit(db, user, "build_bot", ref=session["id"], cost_override=per_model_cost)
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
        "timestamp": now, "type": "build", "credits_used": debit["cost"],
        "model": req.model, "project_id": project_id,
    }
    await db.vibe_sessions.update_one(
        {"id": session["id"]},
        {"$push": {"messages": {"$each": [user_msg, ai_msg]}},
         "$inc": {"total_credits_used": debit["cost"]},
         "$set": {"updated_at": now, "model": req.model, "project_id": project_id}},
    )
    return {
        "session_id": session["id"], "type": "build",
        "project_id": project_id, "name": name, "description": description,
        "files": files, "nodes": nodes, "edges": edges,
        "credits_used": debit["cost"], "balance_remaining": debit["balance"], "model": req.model,
        "key_source": key_info["source"],
    }
