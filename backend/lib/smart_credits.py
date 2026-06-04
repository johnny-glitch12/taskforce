"""
smart_credits — Dynamic credit gating + post-call atomic debit.

The flow per LLM endpoint is now:
    1) check_can_afford(...)   — pre-flight estimate, no debit
    2) <make the LLM call>
    3) debit_actual_usage(...) — race-safe debit using credit_wallet.debit
                                 with a `cost_override` and a rich metadata
                                 payload (tokens, USD cost, revenue, model,
                                 key_source) for the economics dashboard.

BYOK calls are charged ONLY the action's minimum credits (platform fee) —
we didn't pay the API cost, so we don't keep the margin either.
"""
from __future__ import annotations

import logging
from typing import Optional

from .credit_calculator import (
    MIN_CREDITS,
    calculate_credit_cost,
    estimate_credit_cost,
)
from .credit_wallet import can_afford as _wallet_can_afford
from .credit_wallet import debit as _wallet_debit

logger = logging.getLogger("smart_credits")


async def check_can_afford(db, user: dict, model: str, action: str) -> dict:
    """Pre-flight check. Returns `{allowed: bool, ...}`.

    Uses the AVERAGE_TOKENS estimate so users can comfortably afford a typical
    call before they start typing. The actual debit happens after the call
    completes with real token counts.

    Admin/owner bypass returns `{allowed: True, unlimited: True}`.
    """
    estimate = estimate_credit_cost(model, action)
    # Reuse the credit-wallet's can_afford for admin bypass + dual-pool maths.
    wallet_check = await _wallet_can_afford(
        db, user, action, cost_override=estimate["estimated_credits"],
    )
    wallet_check["estimated_credits"] = estimate["estimated_credits"]
    wallet_check["min_credits"] = estimate["min_credits"]
    wallet_check["model"] = model
    return wallet_check


async def debit_actual_usage(
    db,
    user: dict,
    *,
    model: str,
    action: str,
    input_tokens: int,
    output_tokens: int,
    key_source: str,
    ref: Optional[str] = None,
    extra_metadata: Optional[dict] = None,
) -> dict:
    """Debit the ACTUAL credit cost after an LLM call returned.

    Returns the credit_wallet debit response + a `cost_breakdown` block. The
    debit is atomic via credit_wallet.debit's find_one_and_update.

    On BYOK calls (key_source == 'byok'), we charge only `MIN_CREDITS[action]`
    and record `api_cost_usd: 0` so the economics dashboard reflects that we
    paid nothing for that call. This is the explicit BYOK discount lever.
    """
    cost = calculate_credit_cost(model, input_tokens, output_tokens, action)
    credits = cost["credits"]
    api_cost_usd = cost["api_cost_usd"]

    if key_source == "byok":
        credits = MIN_CREDITS.get(action, 1)
        api_cost_usd = 0.0  # we didn't pay the provider
        revenue_usd = round(credits * 0.01, 4)
    else:
        revenue_usd = cost["revenue_usd"]

    metadata = {
        "credit_calculation": "dynamic",
        "model": model,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "api_cost_usd": api_cost_usd,
        "revenue_usd": revenue_usd,
        "key_source": key_source,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    try:
        debit_info = await _wallet_debit(
            db, user, action,
            ref=ref,
            cost_override=credits,
        )
    except ValueError as exc:
        # Lost the credit race between pre-flight and post-call debit.
        logger.warning(f"[smart_credits] debit race for {user.get('email')}: {exc}")
        return {
            "allowed": False,
            "error": "INSUFFICIENT_CREDITS",
            "credits_charged": 0,
            "cost_breakdown": {**cost, "key_source": key_source},
            "metadata": metadata,
        }

    # Persist the rich metadata into the same transaction row that credit_wallet
    # just wrote. credit_wallet stores a row in credit_transactions; we patch
    # the most-recent matching row with our breakdown so the economics dashboard
    # can aggregate on metadata.* fields. find_one_and_update with sort guarantees
    # we patch the row we just inserted, not an older one with the same ref.
    try:
        user_id = str(user.get("id", user.get("email")))
        match = {"user_id": user_id, "kind": action}
        if ref:
            match["ref"] = ref
        await db.credit_transactions.find_one_and_update(
            match,
            {"$set": {"metadata": metadata}},
            sort=[("created_at", -1)],
        )
    except Exception as e:
        logger.warning(f"[smart_credits] metadata patch failed: {e}")

    return {
        "allowed": True,
        "credits_charged": credits,
        "cost_breakdown": {
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "api_cost_usd": api_cost_usd,
            "revenue_usd": revenue_usd,
            "model": model,
            "key_source": key_source,
        },
        "balance": debit_info.get("balance"),
        "metadata": metadata,
    }


__all__ = ["check_can_afford", "debit_actual_usage"]
