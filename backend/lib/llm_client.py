"""
llm_client — Unified shared LLM call helper for Task Force AI.

Wraps emergentintegrations.LlmChat with a single `call_llm()` function that
returns the same shape used everywhere on the platform:
    {text, input_tokens, output_tokens, model, key_source, token_source}

This is the canonical entry point for the multi-stage code-gen pipeline,
margin-aware auto-pick, and any future LLM-driven feature. Centralised so
provider upgrades (real token usage, streaming, retries) happen in one place.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from lib.credit_calculator import estimate_tokens_for_call, extract_real_usage

logger = logging.getLogger("llm_client")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")


# Model registry mirrored from routes/vibe_coding.py — single source of truth.
MODELS = {
    "gemini-2.5-flash":  {"engine": "gemini",    "api_model": "gemini-2.5-flash",            "byok_service": None},
    "gemini-2.5-pro":    {"engine": "gemini",    "api_model": "gemini-2.5-pro",              "byok_service": None},
    "gpt-4o":            {"engine": "openai",    "api_model": "gpt-4o",                       "byok_service": "openai"},
    "gpt-4o-mini":       {"engine": "openai",    "api_model": "gpt-4o-mini",                  "byok_service": "openai"},
    "claude-sonnet":     {"engine": "anthropic", "api_model": "claude-sonnet-4-5-20250929",   "byok_service": "anthropic"},
    "claude-haiku":      {"engine": "anthropic", "api_model": "claude-haiku-4-5-20251001",    "byok_service": "anthropic"},
}


async def resolve_api_key(db, user_id: str, model: str) -> dict:
    """Resolve which API key to use — silent BYOK override or platform key.
    Returns {api_key, source: 'platform'|'byok'}."""
    info = MODELS.get(model) or MODELS["gemini-2.5-flash"]
    byok_service = info["byok_service"]
    if byok_service:
        doc = await db.byok_credentials.find_one(
            {"user_id": user_id, "service": byok_service}, {"api_key": 1, "_id": 0}
        )
        if doc and doc.get("api_key"):
            from lib.byok_crypto import decrypt_key
            try:
                plain = decrypt_key(doc["api_key"])
                if plain:
                    return {"api_key": plain, "source": "byok"}
            except Exception as e:
                logger.warning(f"[llm_client] BYOK decrypt failed for {user_id}/{byok_service}: {e}")
    return {"api_key": EMERGENT_LLM_KEY, "source": "platform"}


async def call_llm(
    *,
    model: str,
    system_prompt: str,
    messages: list,
    api_key: Optional[str] = None,
    session_key: Optional[str] = None,
    db=None,
    user_id: Optional[str] = None,
) -> dict:
    """Single canonical LLM call. Returns dict with text + token info.

    Args:
        model: model id from MODELS (gemini-2.5-flash, gpt-4o, etc.)
        system_prompt: system message for the LLM
        messages: list of {role, content} chat turns — the LAST message must be
                  role='user' (we send it as the active turn; prior turns are
                  collapsed into a transcript header to avoid N round-trips).
        api_key:  optional override — if None, resolves via BYOK or platform.
        session_key: stable session id for emergentintegrations; auto-generated
                    if omitted.
        db, user_id: only needed if api_key is None (for BYOK lookup).

    Returns:
        {text, input_tokens, output_tokens, model, key_source, token_source}
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    info = MODELS.get(model)
    if not info:
        raise ValueError(f"Unknown model: {model}")

    # Resolve key
    if api_key is None:
        if db is None or user_id is None:
            api_key = EMERGENT_LLM_KEY
            key_source = "platform"
        else:
            key_info = await resolve_api_key(db, user_id, model)
            api_key = key_info["api_key"]
            key_source = key_info["source"]
    else:
        key_source = "explicit"

    session_key = session_key or f"call-llm-{uuid.uuid4().hex[:8]}"

    # Build the composite user message — collapse prior turns into a transcript
    # so emergentintegrations sees a single round-trip.
    if not messages:
        raise ValueError("messages must contain at least one user message")
    last = messages[-1]
    if last.get("role") != "user":
        raise ValueError("last message must be role=user")
    user_content = last.get("content") or ""

    history = messages[:-1]
    if history:
        transcript = "\n".join(
            f"{m.get('role', '?').upper()}: {(m.get('content') or '').strip()[:2000]}"
            for m in history[-12:]
        )
        composite = f"CONVERSATION SO FAR:\n{transcript}\n\n--- NEW USER MESSAGE ---\n{user_content}"
    else:
        composite = user_content

    chat = LlmChat(api_key=api_key, session_id=session_key, system_message=system_prompt).with_model(
        info["engine"], info["api_model"]
    )
    resp = await chat.send_message(UserMessage(text=composite))
    text = str(resp)

    real = extract_real_usage(resp)
    if real is not None:
        in_tok, out_tok = real
        token_source = "provider"
    else:
        in_tok, out_tok = estimate_tokens_for_call(system_prompt, history, user_content, text)
        token_source = "estimate"

    return {
        "text": text,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "model": model,
        "key_source": key_source,
        "token_source": token_source,
    }


__all__ = ["call_llm", "resolve_api_key", "MODELS"]
