"""
credits_economics — Dynamic credit pricing introspection endpoints.

Two endpoints:
  - POST /api/credits/estimate         (any auth) — pre-flight cost preview
  - GET  /api/admin/economics          (owner-only) — revenue/cost/margin dashboard

`/credits/estimate` powers the Pricing page model grid and the ModelPicker tooltip:
returns (low, typical, high) credit ranges per model+action, all sourced from the
canonical `lib.credit_calculator` constants so a margin tweak instantly propagates
everywhere.

`/admin/economics` aggregates the `credit_transactions` ledger by metadata.*
fields (written by `smart_credits.debit_actual_usage`) and surfaces total revenue,
real API cost, gross margin, per-model breakdown, top spenders.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lib.credit_calculator import (
    AVERAGE_TOKENS,
    CREDIT_VALUE_USD,
    MIN_CREDITS,
    MODEL_COSTS,
    PLATFORM_MARGIN,
    calculate_credit_cost,
    estimate_range,
)

router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


# ─── /api/credits/estimate ─────────────────────────────
class EstimateRequest(BaseModel):
    model: Optional[str] = None
    action: Optional[str] = None


@router.post("/credits/estimate")
async def estimate_credits(req: EstimateRequest, user=Depends(get_current_user())):
    """Pre-flight credit estimate.

    Body:
      {"model": "<id?>", "action": "<action?>"}

    With no body — returns the full pricing matrix (every model × every action).
    With model+action — returns a single low/typical/high range.

    `low` is always the action's MIN_CREDITS floor; `typical` reflects average
    token usage; `high` reflects 2.5× the average (used to cover power users).
    """
    actions = ["vibe_chat", "vibe_build", "build_bot", "agent_run"]

    def _row(model: str, action: str) -> dict:
        rng = estimate_range(model, action)
        avg = AVERAGE_TOKENS.get(action, {"input": 1500, "output": 500})
        typical_cost = calculate_credit_cost(model, avg["input"], avg["output"], action)
        return {
            "model": model,
            "action": action,
            "low": rng["low"],
            "typical": rng["typical"],
            "high": rng["high"],
            "api_cost_typical_usd": typical_cost["api_cost_usd"],
            "revenue_typical_usd": typical_cost["revenue_usd"],
            "byok_cost": MIN_CREDITS.get(action, 1),
            "avg_input_tokens": avg["input"],
            "avg_output_tokens": avg["output"],
        }

    if req.model and req.action:
        if req.model not in MODEL_COSTS:
            raise HTTPException(status_code=400, detail=f"Unknown model '{req.model}'.")
        if req.action not in AVERAGE_TOKENS:
            raise HTTPException(status_code=400, detail=f"Unknown action '{req.action}'.")
        return {
            "single": _row(req.model, req.action),
            "platform_margin": PLATFORM_MARGIN,
            "credit_value_usd": CREDIT_VALUE_USD,
        }

    matrix = [_row(m, a) for m in MODEL_COSTS for a in actions]
    return {
        "models": list(MODEL_COSTS.keys()),
        "actions": actions,
        "matrix": matrix,
        "platform_margin": PLATFORM_MARGIN,
        "credit_value_usd": CREDIT_VALUE_USD,
        "model_costs": MODEL_COSTS,
        "min_credits": MIN_CREDITS,
    }


# ─── /api/admin/economics ──────────────────────────────
def _require_owner(user):
    """Owner-only gate. Falls through cleanly if missing — 403 with explicit code."""
    if user.get("role") != "admin" or not user.get("is_owner"):
        raise HTTPException(status_code=403, detail={
            "error": "OWNER_ONLY",
            "message": "This endpoint is restricted to platform owners.",
        })


@router.get("/admin/economics")
async def admin_economics(days: int = 30, user=Depends(get_current_user())):
    """Owner-only economics dashboard.

    Aggregates from `credit_transactions.metadata.*` (written by
    smart_credits.debit_actual_usage). Falls back to ledger `delta` counts
    when metadata is absent (legacy rows still count toward credits, but
    api_cost / revenue are 0 for them).
    """
    _require_owner(user)
    days = max(1, min(int(days), 365))
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Window stats — debits only (delta < 0) with dynamic-credit metadata.
    pipeline_window = [
        {"$match": {"created_at": {"$gte": cutoff}, "delta": {"$lt": 0}}},
        {"$group": {
            "_id": None,
            "total_credits_spent": {"$sum": {"$abs": "$delta"}},
            "total_api_cost_usd":  {"$sum": {"$ifNull": ["$metadata.api_cost_usd", 0]}},
            "total_revenue_usd":   {"$sum": {"$ifNull": ["$metadata.revenue_usd", 0]}},
            "calls":               {"$sum": 1},
            "input_tokens":        {"$sum": {"$ifNull": ["$metadata.input_tokens", 0]}},
            "output_tokens":       {"$sum": {"$ifNull": ["$metadata.output_tokens", 0]}},
        }},
    ]
    agg = await db.credit_transactions.aggregate(pipeline_window).to_list(1)
    win = agg[0] if agg else {}
    api_cost = float(win.get("total_api_cost_usd", 0) or 0)
    revenue = float(win.get("total_revenue_usd", 0) or 0)
    gross_margin_usd = revenue - api_cost
    gross_margin_pct = (gross_margin_usd / revenue * 100) if revenue > 0 else 0

    # Per-model breakdown (group on metadata.model).
    pipeline_models = [
        {"$match": {"created_at": {"$gte": cutoff}, "delta": {"$lt": 0},
                    "metadata.model": {"$exists": True}}},
        {"$group": {
            "_id": "$metadata.model",
            "credits":     {"$sum": {"$abs": "$delta"}},
            "api_cost":    {"$sum": {"$ifNull": ["$metadata.api_cost_usd", 0]}},
            "revenue":     {"$sum": {"$ifNull": ["$metadata.revenue_usd", 0]}},
            "calls":       {"$sum": 1},
            "input_tokens":  {"$sum": {"$ifNull": ["$metadata.input_tokens", 0]}},
            "output_tokens": {"$sum": {"$ifNull": ["$metadata.output_tokens", 0]}},
        }},
        {"$sort": {"revenue": -1}},
    ]
    per_model = []
    async for row in db.credit_transactions.aggregate(pipeline_models):
        per_model.append({
            "model": row["_id"],
            "credits": int(row.get("credits") or 0),
            "api_cost_usd": round(float(row.get("api_cost") or 0), 4),
            "revenue_usd": round(float(row.get("revenue") or 0), 4),
            "calls": int(row.get("calls") or 0),
            "input_tokens": int(row.get("input_tokens") or 0),
            "output_tokens": int(row.get("output_tokens") or 0),
        })

    # BYOK vs platform split.
    pipeline_byok = [
        {"$match": {"created_at": {"$gte": cutoff}, "delta": {"$lt": 0},
                    "metadata.key_source": {"$exists": True}}},
        {"$group": {
            "_id": "$metadata.key_source",
            "credits":  {"$sum": {"$abs": "$delta"}},
            "api_cost": {"$sum": {"$ifNull": ["$metadata.api_cost_usd", 0]}},
            "revenue":  {"$sum": {"$ifNull": ["$metadata.revenue_usd", 0]}},
            "calls":    {"$sum": 1},
        }},
    ]
    by_key_source = {}
    async for row in db.credit_transactions.aggregate(pipeline_byok):
        by_key_source[row["_id"]] = {
            "credits": int(row.get("credits") or 0),
            "api_cost_usd": round(float(row.get("api_cost") or 0), 4),
            "revenue_usd": round(float(row.get("revenue") or 0), 4),
            "calls": int(row.get("calls") or 0),
        }

    # Top spenders.
    pipeline_top = [
        {"$match": {"created_at": {"$gte": cutoff}, "delta": {"$lt": 0}}},
        {"$group": {
            "_id": "$email",
            "credits":  {"$sum": {"$abs": "$delta"}},
            "revenue":  {"$sum": {"$ifNull": ["$metadata.revenue_usd", 0]}},
            "api_cost": {"$sum": {"$ifNull": ["$metadata.api_cost_usd", 0]}},
            "calls":    {"$sum": 1},
        }},
        {"$sort": {"credits": -1}},
        {"$limit": 20},
    ]
    top_spenders = []
    async for row in db.credit_transactions.aggregate(pipeline_top):
        top_spenders.append({
            "email": row["_id"] or "unknown",
            "credits": int(row.get("credits") or 0),
            "revenue_usd": round(float(row.get("revenue") or 0), 4),
            "api_cost_usd": round(float(row.get("api_cost") or 0), 4),
            "calls": int(row.get("calls") or 0),
        })

    # Daily revenue series for the chart.
    pipeline_daily = [
        {"$match": {"created_at": {"$gte": cutoff}, "delta": {"$lt": 0}}},
        {"$group": {
            "_id": {"$substr": ["$created_at", 0, 10]},
            "credits":  {"$sum": {"$abs": "$delta"}},
            "revenue":  {"$sum": {"$ifNull": ["$metadata.revenue_usd", 0]}},
            "api_cost": {"$sum": {"$ifNull": ["$metadata.api_cost_usd", 0]}},
            "calls":    {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    daily = []
    async for row in db.credit_transactions.aggregate(pipeline_daily):
        daily.append({
            "date": row["_id"],
            "credits": int(row.get("credits") or 0),
            "revenue_usd": round(float(row.get("revenue") or 0), 4),
            "api_cost_usd": round(float(row.get("api_cost") or 0), 4),
            "calls": int(row.get("calls") or 0),
        })

    # Lifetime totals (no cutoff).
    pipeline_lifetime = [
        {"$match": {"delta": {"$lt": 0}}},
        {"$group": {
            "_id": None,
            "credits":  {"$sum": {"$abs": "$delta"}},
            "revenue":  {"$sum": {"$ifNull": ["$metadata.revenue_usd", 0]}},
            "api_cost": {"$sum": {"$ifNull": ["$metadata.api_cost_usd", 0]}},
            "calls":    {"$sum": 1},
        }},
    ]
    lt = await db.credit_transactions.aggregate(pipeline_lifetime).to_list(1)
    lifetime = lt[0] if lt else {}

    # Active users count (users who spent credits in the window).
    pipeline_users = [
        {"$match": {"created_at": {"$gte": cutoff}, "delta": {"$lt": 0}}},
        {"$group": {"_id": "$user_id"}},
        {"$count": "n"},
    ]
    u = await db.credit_transactions.aggregate(pipeline_users).to_list(1)
    active_users = (u[0].get("n") if u else 0) or 0

    return {
        "window_days": days,
        "platform_margin": PLATFORM_MARGIN,
        "credit_value_usd": CREDIT_VALUE_USD,
        "window": {
            "total_credits_spent": int(win.get("total_credits_spent", 0) or 0),
            "total_api_cost_usd":  round(api_cost, 4),
            "total_revenue_usd":   round(revenue, 4),
            "gross_margin_usd":    round(gross_margin_usd, 4),
            "gross_margin_pct":    round(gross_margin_pct, 2),
            "calls":               int(win.get("calls", 0) or 0),
            "input_tokens":        int(win.get("input_tokens", 0) or 0),
            "output_tokens":       int(win.get("output_tokens", 0) or 0),
            "active_users":        active_users,
        },
        "lifetime": {
            "credits":      int(lifetime.get("credits", 0) or 0),
            "revenue_usd":  round(float(lifetime.get("revenue", 0) or 0), 4),
            "api_cost_usd": round(float(lifetime.get("api_cost", 0) or 0), 4),
            "calls":        int(lifetime.get("calls", 0) or 0),
        },
        "per_model": per_model,
        "by_key_source": by_key_source,
        "top_spenders": top_spenders,
        "daily": daily,
    }
