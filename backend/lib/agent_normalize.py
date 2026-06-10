"""
Agent normalization helpers — Task Force AI (Prompt 31, Phase 1).

Pure helper module used by `routes/agents.py` to:
  1. Default Phase-1 fields on legacy `bot_projects` / `agent_packages` docs.
  2. Aggregate per-agent run stats (24h window) from `app_runs` in ONE Mongo
     pipeline (avoids N+1 fan-out).

No DB writes. No side effects. Safe to call from anywhere.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


# ── Phase-1 default values (applied on read for legacy docs) ──────────────
_DEFAULT_AGENT_STATE = "draft"
_DEFAULT_MINI_APP_SETTINGS = {
    "visibility": "public",
    "cover_url": None,
    "input_mode": "json",
    "show_branding": True,
    "allow_sharing": True,
}
_DEFAULT_AGENT_SETTINGS = {
    "max_runs_per_hour": 0,
    "max_runs_per_day": 0,
    "auto_pause_on_errors": True,
    "auto_pause_threshold": 5,
    "notifications": {
        "on_error": True,
        "on_pause": True,
        "milestone_every": 0,
        "daily_summary": False,
    },
}

# Sort order: paused first, then active by updated_at desc, then draft, then archived
_STATE_ORDER = {"paused": 0, "active": 1, "draft": 2, "archived": 3}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def default_phase1_fields() -> dict:
    """Return a fresh dict of Phase-1 defaults. Used when seeding new agents."""
    return {
        "agent_state": _DEFAULT_AGENT_STATE,
        "paused_at": None,
        "auto_pause_reason": None,
        "consecutive_errors": 0,
        "input_template": None,
        "mini_app_settings": dict(_DEFAULT_MINI_APP_SETTINGS),
        "agent_settings": {
            **_DEFAULT_AGENT_SETTINGS,
            "notifications": dict(_DEFAULT_AGENT_SETTINGS["notifications"]),
        },
    }


def _merged(default: dict, override) -> dict:
    """Shallow-merge: keep all default keys; overlay override values only when
    override is a dict. Nested dicts (notifications) get a second shallow merge."""
    if not isinstance(override, dict):
        return dict(default)
    out = dict(default)
    for k, v in override.items():
        if isinstance(default.get(k), dict) and isinstance(v, dict):
            out[k] = {**default[k], **v}
        else:
            out[k] = v
    return out


def normalize_agent(
    doc: dict,
    kind: str = "bot_project",
    runs_stats: Optional[dict] = None,
    exchange_status: Optional[str] = None,
) -> dict:
    """Return the unified Hub list/detail shape for one agent.

    `doc` is the raw Mongo document from either `bot_projects` or
    `agent_packages`. `runs_stats` is the per-agent dict produced by
    `aggregate_runs_24h()` keyed by agent id (may be None or missing).
    `exchange_status` is the marketplace status (looked up separately).
    """
    if doc is None:
        return {}

    agent_id = doc.get("id") or doc.get("_id") or ""
    name = doc.get("name") or doc.get("display_name") or "Untitled Agent"
    description = doc.get("description") or ""
    category = doc.get("category") or (doc.get("manifest") or {}).get("category") or None
    slug = doc.get("app_slug") or doc.get("slug") or agent_id

    state = doc.get("agent_state") or _DEFAULT_AGENT_STATE
    mini_app = _merged(_DEFAULT_MINI_APP_SETTINGS, doc.get("mini_app_settings"))
    agent_settings = _merged(_DEFAULT_AGENT_SETTINGS, doc.get("agent_settings"))
    # Re-merge nested notifications (shallow merge above is one level only)
    agent_settings["notifications"] = {
        **_DEFAULT_AGENT_SETTINGS["notifications"],
        **((doc.get("agent_settings") or {}).get("notifications") or {}),
    }

    stats = runs_stats or {}
    return {
        "kind": kind,
        "id": agent_id,
        "slug": slug,
        "name": name,
        "description": description,
        "category": category,
        "agent_state": state,
        "paused_at": doc.get("paused_at"),
        "auto_pause_reason": doc.get("auto_pause_reason"),
        "consecutive_errors": int(doc.get("consecutive_errors") or 0),
        "exchange_status": exchange_status,  # None when not listed
        "input_template": doc.get("input_template"),
        "mini_app_settings": mini_app,
        "agent_settings": agent_settings,
        "has_ui": bool(doc.get("has_ui")),
        "runs_24h": int(stats.get("runs") or 0),
        "errors_24h": int(stats.get("errors") or 0),
        "credits_24h": int(stats.get("credits") or 0),
        "last_run_at": stats.get("last_run_at"),
        "credits_per_run": 1,  # current platform default for agent_run
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def sort_key(normalized_doc: dict):
    """Sort: paused → active (by updated_at desc) → draft → archived."""
    state = normalized_doc.get("agent_state") or _DEFAULT_AGENT_STATE
    order = _STATE_ORDER.get(state, 4)
    # Negate updated_at so newer rows come first within a state bucket
    return (order, -(_iso_to_epoch(normalized_doc.get("updated_at"))))


def _iso_to_epoch(iso: Optional[str]) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


async def aggregate_runs_24h(db, agent_ids: Iterable[str]) -> dict:
    """Single $match + $group pipeline over `app_runs` for all the given ids.

    Returns: {agent_id: {runs, errors, credits, last_run_at}}.
    Agents with zero runs in the window are simply absent from the dict.
    """
    ids = [a for a in agent_ids if a]
    if not ids:
        return {}
    cutoff = (_now_dt() - timedelta(hours=24)).isoformat()
    pipeline = [
        {"$match": {"app_id": {"$in": ids}, "created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$app_id",
            "runs": {"$sum": 1},
            "errors": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}},
            "credits": {"$sum": {"$ifNull": ["$credits_used", 0]}},
            "last_run_at": {"$max": "$created_at"},
        }},
    ]
    out: dict = {}
    async for row in db.app_runs.aggregate(pipeline):
        out[row["_id"]] = {
            "runs": row.get("runs", 0),
            "errors": row.get("errors", 0),
            "credits": row.get("credits", 0),
            "last_run_at": row.get("last_run_at"),
        }
    return out


async def fetch_exchange_status_map(db, source_project_ids: Iterable[str]) -> dict:
    """For each bot_project id, look up its marketplace status (if listed).

    The link field on `exchange_listings` is `source_project_id` (the publish
    flow sets it). Returns {project_id: status_string}. Absent IDs mean
    the agent has never been published.
    """
    ids = [a for a in source_project_ids if a]
    if not ids:
        return {}
    out: dict = {}
    cursor = db.exchange_listings.find(
        {"source_project_id": {"$in": ids}},
        {"_id": 0, "source_project_id": 1, "status": 1},
    )
    async for row in cursor:
        pid = row.get("source_project_id")
        if pid:
            out[pid] = row.get("status")
    return out


__all__ = [
    "default_phase1_fields",
    "normalize_agent",
    "sort_key",
    "aggregate_runs_24h",
    "fetch_exchange_status_map",
]
