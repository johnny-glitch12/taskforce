"""
agent_notifications — Email dispatch for agent ops events (Prompt 31 Phase 4).

Loads per-agent `agent_settings.notifications` preferences, gates the send,
and dispatches via `utils.email_service.send_email`. Never raises — all
exceptions are swallowed at WARN level so a notification failure can never
break a run or schedule tick.

Wired from:
  - routes/apps.py /run — `notify_on_error` (failure branch),
                          `notify_milestone` (success branch)
  - routes/apps.py /run — `notify_on_pause` (auto-pause trigger)
  - APScheduler daily 09:00 UTC — `send_daily_summary` for every opted-in agent
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("agent_notifications")

# Optional audit hook
try:
    from lib.memory_audit import log_memory_event  # type: ignore
except Exception:  # noqa: BLE001
    log_memory_event = None

PLATFORM_URL = os.environ.get("PLATFORM_URL", "https://taskforce.run")


# ─── Internal helpers ────────────────────────────────────────────────────
def _hub_link(agent_id: str) -> str:
    return f"{PLATFORM_URL}/my-agents/{agent_id}"


def _wrap(title: str, lines, agent_id: str) -> str:
    """Minimal inline-CSS dark-theme wrapper. Matches the existing
    email_service brand. No external resources."""
    body = "".join(f'<p style="margin:6px 0;color:#a1a1aa;font-size:13px;">{ln}</p>' for ln in lines)
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:24px;background:#0a0a0c;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e4e4e7;">
  <div style="max-width:560px;margin:0 auto;background:#18181b;border:1px solid #27272a;padding:24px;">
    <h2 style="margin:0 0 12px;font-size:18px;color:#22d3ee;">{title}</h2>
    {body}
    <p style="margin:16px 0 0;">
      <a href="{_hub_link(agent_id)}"
         style="display:inline-block;padding:8px 14px;background:#22d3ee;color:#0a0a0c;text-decoration:none;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;">
        View in Operations Hub →
      </a>
    </p>
    <p style="margin:24px 0 0;color:#52525b;font-size:11px;">
      You're receiving this because notifications are enabled for this agent.
      Adjust preferences in <em>My Agents → Settings → Notifications</em>.
    </p>
  </div>
</body></html>"""


async def _load_agent_and_owner(db, agent_id: str) -> Optional[tuple]:
    """Return (agent_doc, owner_email) or None. Best-effort — caller bails if None."""
    try:
        agent = await db.bot_projects.find_one(
            {"id": agent_id},
            {"_id": 0, "name": 1, "user_id": 1, "agent_settings": 1, "creator_email": 1},
        )
        if not agent:
            return None
        owner_email = agent.get("creator_email")
        if not owner_email and agent.get("user_id"):
            u = await db.users.find_one(
                {"id": agent["user_id"]}, {"_id": 0, "email": 1},
            )
            owner_email = u.get("email") if u else None
        return (agent, owner_email)
    except Exception as _e:  # noqa: BLE001
        logger.warning(f"[notify] _load_agent_and_owner failed: {_e}")
        return None


async def _dispatch(db, agent_id: str, event: str, recipient: Optional[str], subject: str, html: str) -> None:
    """Final send step. Logs audit + swallows errors."""
    if not recipient:
        logger.info(f"[notify:{event}] no recipient — skipping agent={agent_id[:8]}")
        if log_memory_event:
            try:
                await log_memory_event("", "notification_skipped", {
                    "agent_id": agent_id, "event": event, "reason": "no_recipient",
                })
            except Exception:  # noqa: BLE001
                pass
        return
    try:
        from utils.email_service import send_email
        result = await send_email(recipient, subject, html)
        evt = "notification_sent" if result.get("success") else "notification_skipped"
        if log_memory_event:
            try:
                owner_id = ""  # best-effort audit; the real user_id comes from agent.user_id
                agent = await db.bot_projects.find_one({"id": agent_id}, {"_id": 0, "user_id": 1})
                owner_id = (agent or {}).get("user_id") or ""
                await log_memory_event(owner_id, evt, {
                    "agent_id": agent_id, "event": event,
                    "error": result.get("error"),
                })
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[notify:{event}] dispatch failed: {e}")
        if log_memory_event:
            try:
                await log_memory_event("", "notification_failed", {
                    "agent_id": agent_id, "event": event, "error": str(e)[:200],
                })
            except Exception:  # noqa: BLE001
                pass


# ─── Public API ──────────────────────────────────────────────────────────
async def notify_on_error(db, agent_id: str, run_id: str, error_summary: str) -> None:
    loaded = await _load_agent_and_owner(db, agent_id)
    if not loaded:
        return
    agent, owner_email = loaded
    nots = (agent.get("agent_settings") or {}).get("notifications") or {}
    if not nots.get("on_error"):
        return
    subject = f"[{agent.get('name', 'Agent')}] Run failed"
    html = _wrap(
        f"Run failed — {agent.get('name', 'Agent')}",
        [
            f"Run <code>{run_id[:8]}</code> failed.",
            f"<strong>Error:</strong> {(error_summary or 'unknown')[:200]}",
        ],
        agent_id,
    )
    await _dispatch(db, agent_id, "on_error", owner_email, subject, html)


async def notify_on_pause(db, agent_id: str, reason: str) -> None:
    loaded = await _load_agent_and_owner(db, agent_id)
    if not loaded:
        return
    agent, owner_email = loaded
    nots = (agent.get("agent_settings") or {}).get("notifications") or {}
    if not nots.get("on_pause"):
        return
    subject = f"[{agent.get('name', 'Agent')}] Auto-paused"
    html = _wrap(
        f"Agent auto-paused — {agent.get('name', 'Agent')}",
        [
            "Your agent was automatically paused.",
            f"<strong>Reason:</strong> {reason}",
            "Hit Resume from the Operations Hub when you're ready.",
        ],
        agent_id,
    )
    await _dispatch(db, agent_id, "on_pause", owner_email, subject, html)


async def notify_milestone(db, agent_id: str, milestone_count: int) -> None:
    loaded = await _load_agent_and_owner(db, agent_id)
    if not loaded:
        return
    agent, owner_email = loaded
    nots = (agent.get("agent_settings") or {}).get("notifications") or {}
    step = int(nots.get("milestone_every") or 0)
    if step <= 0 or milestone_count % step != 0:
        return
    subject = f"[{agent.get('name', 'Agent')}] {milestone_count} runs"
    html = _wrap(
        f"Milestone reached — {milestone_count} runs",
        [
            f"<strong>{agent.get('name', 'Agent')}</strong> just hit {milestone_count} total runs.",
            "Open the Hub to see today's success rate and earnings.",
        ],
        agent_id,
    )
    await _dispatch(db, agent_id, "milestone", owner_email, subject, html)


async def send_daily_summary(db, agent_id: Optional[str] = None) -> int:
    """APScheduler job entry point. Iterates every agent with
    `agent_settings.notifications.daily_summary=true` and sends one summary.

    When `agent_id` is provided, send only for that agent (testability).
    Returns the count of emails dispatched.
    """
    sent = 0
    query = {"agent_settings.notifications.daily_summary": True}
    if agent_id:
        query["id"] = agent_id
    try:
        async for agent in db.bot_projects.find(query, {"_id": 0, "id": 1, "name": 1, "user_id": 1, "creator_email": 1}):
            try:
                pid = agent.get("id")
                if not pid:
                    continue
                # 24h aggregate
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                runs = errors = 0
                pipeline = [
                    {"$match": {"app_id": pid, "created_at": {"$gte": cutoff}}},
                    {"$group": {
                        "_id": None,
                        "runs": {"$sum": 1},
                        "errors": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}},
                    }},
                ]
                async for row in db.app_runs.aggregate(pipeline):
                    runs = int(row.get("runs") or 0)
                    errors = int(row.get("errors") or 0)

                # Resolve owner email
                owner_email = agent.get("creator_email")
                if not owner_email and agent.get("user_id"):
                    u = await db.users.find_one(
                        {"id": agent["user_id"]}, {"_id": 0, "email": 1},
                    )
                    owner_email = (u or {}).get("email")

                success_rate = int(round(100 * (runs - errors) / runs)) if runs > 0 else 0
                subject = f"[{agent.get('name', 'Agent')}] Daily summary"
                html = _wrap(
                    f"Yesterday — {agent.get('name', 'Agent')}",
                    [
                        f"<strong>{runs}</strong> runs in the last 24h",
                        f"<strong>{success_rate}%</strong> success rate ({errors} errors)",
                    ],
                    pid,
                )
                await _dispatch(db, pid, "daily_summary", owner_email, subject, html)
                sent += 1
            except Exception as inner:  # noqa: BLE001
                logger.warning(f"[notify:daily] agent={agent.get('id', '?')[:8]} error: {inner}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[notify:daily] outer scan failed: {e}")
    return sent


__all__ = [
    "notify_on_error",
    "notify_on_pause",
    "notify_milestone",
    "send_daily_summary",
]
