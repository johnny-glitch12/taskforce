"""
credit_calculator — Token-based dynamic credit pricing.

LAST UPDATED: 2026-06-04
Re-check quarterly:
  https://ai.google.dev/gemini-api/docs/pricing
  https://openai.com/api/pricing/
  https://docs.anthropic.com/en/docs/about-claude/pricing

Edit MODEL_COSTS below if a provider changes pricing — users automatically pay
less when API prices drop. The economics dashboard reads these dollar costs
straight from the credit_transactions ledger metadata, so old data stays
accurate even after MODEL_COSTS is updated.
"""
from __future__ import annotations

import math
from typing import Optional

# Real API costs per million tokens (USD).
MODEL_COSTS: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro":   {"input": 1.00, "output": 10.00},
    "gpt-4o":           {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":      {"input": 0.15, "output": 0.60},
    "claude-sonnet":    {"input": 3.00, "output": 15.00},
    "claude-haiku":     {"input": 1.00, "output": 5.00},
}

# 1 credit = $0.01 of compute (users buy credits at $0.012–$0.025 each → margin baked in).
CREDIT_VALUE_USD = 0.01

# Minimum credit charge per action — even tiny messages cost something.
MIN_CREDITS: dict[str, int] = {
    "vibe_chat":          1,
    "vibe_build":         2,
    "operative_chat":     1,
    "agent_run":          1,
    "external_agent_run": 1,
    "workflow_run":       1,
    "build_bot":          2,
}

# Margin multiplier — we charge users 3x the raw API cost.
PLATFORM_MARGIN: float = 3.0

# Average input/output tokens per action — used by estimate_credit_cost for
# pre-flight UI display. Tuned from real production data; revisit quarterly.
AVERAGE_TOKENS = {
    "vibe_chat":          {"input": 2000, "output": 500},
    "vibe_build":         {"input": 4000, "output": 3000},
    "operative_chat":     {"input": 3000, "output": 800},
    "agent_run":          {"input": 1000, "output": 500},
    "external_agent_run": {"input": 500,  "output": 200},
    "workflow_run":       {"input": 800,  "output": 300},
    "build_bot":          {"input": 3500, "output": 2500},
}


def calculate_credit_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    action: str,
) -> dict:
    """Calculate dynamic credit cost based on actual token usage.

    Returns:
        credits      — credits charged to the user (always >= MIN_CREDITS[action])
        api_cost_usd — what we actually paid the provider
        revenue_usd  — what we charged (credits * $0.01)
        input_tokens / output_tokens / model — echo for the ledger
    """
    costs = MODEL_COSTS.get(model)
    if not costs:
        # Unknown model — fall back to the action's flat minimum so we never
        # silently lose money on a typo.
        return {
            "credits": MIN_CREDITS.get(action, 1),
            "api_cost_usd": 0.0,
            "revenue_usd": MIN_CREDITS.get(action, 1) * CREDIT_VALUE_USD,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
            "fallback": True,
        }

    input_cost  = (input_tokens  / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    api_cost    = input_cost + output_cost

    charged_usd = api_cost * PLATFORM_MARGIN
    credits = max(
        MIN_CREDITS.get(action, 1),
        int(math.ceil(charged_usd / CREDIT_VALUE_USD)),
    )

    return {
        "credits": credits,
        "api_cost_usd": round(api_cost, 6),
        "revenue_usd": round(credits * CREDIT_VALUE_USD, 4),
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "model": model,
        "fallback": False,
    }


def estimate_credit_cost(model: str, action: str) -> dict:
    """Estimate credit cost BEFORE making the LLM call — used for UI display
    + pre-flight balance check. Based on `AVERAGE_TOKENS` per action."""
    avg = AVERAGE_TOKENS.get(action, {"input": 1500, "output": 500})
    result = calculate_credit_cost(model, avg["input"], avg["output"], action)
    return {
        "estimated_credits": result["credits"],
        "min_credits": MIN_CREDITS.get(action, 1),
        "note": "Actual cost depends on message length and complexity.",
        "model": model,
        "action": action,
    }


def estimate_range(model: str, action: str) -> dict:
    """Return a (low, typical, high) range — used by the public pricing page
    + the ModelPicker tooltips. Low = MIN_CREDITS, typical = avg, high = 2.5×avg."""
    avg = AVERAGE_TOKENS.get(action, {"input": 1500, "output": 500})
    typical = calculate_credit_cost(model, avg["input"], avg["output"], action)["credits"]
    high    = calculate_credit_cost(model, int(avg["input"] * 2.5), int(avg["output"] * 2.5), action)["credits"]
    return {
        "low":     MIN_CREDITS.get(action, 1),
        "typical": typical,
        "high":    max(typical, high),
    }


# ── Token estimation (no provider SDK token data available via emergentintegrations) ──

_TIKTOKEN_ENCODER = None


def _get_encoder():
    """Lazy-load a cl100k_base encoder — a strong approximation for OpenAI +
    Claude tokens, and a reasonable proxy for Gemini (within ~10%)."""
    global _TIKTOKEN_ENCODER
    if _TIKTOKEN_ENCODER is None:
        try:
            import tiktoken
            _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _TIKTOKEN_ENCODER = "heuristic"
    return _TIKTOKEN_ENCODER


def estimate_tokens(text: str) -> int:
    """Best-effort token count. Uses tiktoken when available, falls back to
    chars/4 heuristic (within ~15% for English prose). Always returns >= 1."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc == "heuristic":
        return max(1, len(text) // 4)
    return max(1, len(enc.encode(text)))


def estimate_tokens_for_call(
    system_prompt: str,
    history: list,
    user_message: str,
    response_text: str,
) -> tuple[int, int]:
    """Estimate input/output tokens for a full LLM call.

    Input = system + history (last 12 turns) + user_message.
    Output = response_text.
    Mirrors the trim policy used by `_call_platform_llm` in vibe_coding.py so
    counts align with what we actually sent on the wire.
    """
    in_text = (system_prompt or "") + "\n"
    for m in (history or [])[-12:]:
        content = (m.get("content") or "")[:2000]
        in_text += f"{m.get('role', '?')}: {content}\n"
    in_text += user_message or ""
    return estimate_tokens(in_text), estimate_tokens(response_text or "")


__all__ = [
    "MODEL_COSTS", "MIN_CREDITS", "PLATFORM_MARGIN", "CREDIT_VALUE_USD",
    "AVERAGE_TOKENS",
    "calculate_credit_cost", "estimate_credit_cost", "estimate_range",
    "estimate_tokens", "estimate_tokens_for_call",
]
