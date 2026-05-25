"""
Rate Limiter + Concurrent Execution Cap

- Per-user rate limit: max N requests per minute to /api/run-agent
- Concurrent cap: only 1 active (queued/processing) execution per user
  Uses in-memory tracking (instant) + Supabase check (durable)
"""
import time
from collections import defaultdict

# ── In-memory rate limiter (per-user, per-minute) ──
_user_requests: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 5          # max requests per window
RATE_WINDOW = 60        # window in seconds

# ── In-memory active execution tracker ──
_active_executions: dict[str, str] = {}  # executor_id -> log_id


def check_rate_limit(user_id: str) -> dict:
    """
    Returns {"allowed": True} or {"allowed": False, "retry_after": seconds}.
    """
    now = time.time()
    _user_requests[user_id] = [t for t in _user_requests[user_id] if now - t < RATE_WINDOW]

    if len(_user_requests[user_id]) >= RATE_LIMIT:
        oldest = _user_requests[user_id][0]
        retry_after = int(RATE_WINDOW - (now - oldest)) + 1
        return {"allowed": False, "retry_after": retry_after}

    _user_requests[user_id].append(now)
    return {"allowed": True}


def check_concurrent_cap(supabase_client, executor_id: str) -> dict:
    """
    Check if user already has a running execution.
    Uses in-memory lock first (instant), then Supabase (durable).
    """
    # Fast path: in-memory check
    if executor_id in _active_executions:
        print(f"[CONCURRENT CAP] BLOCKED {executor_id} — active: {_active_executions[executor_id][:8]}", flush=True)
        return {"allowed": False, "active_log_id": _active_executions[executor_id]}

    # Slow path: Supabase check (catches leaked state from crashes)
    result = (
        supabase_client.table("agent_logs")
        .select("log_id")
        .eq("executor_id", executor_id)
        .in_("status", ["queued", "processing"])
        .limit(1)
        .execute()
    )
    if result.data:
        active_id = result.data[0]["log_id"]
        _active_executions[executor_id] = active_id
        print(f"[CONCURRENT CAP] BLOCKED {executor_id} — found in Supabase: {active_id[:8]}", flush=True)
        return {"allowed": False, "active_log_id": active_id}

    return {"allowed": True}


def mark_execution_active(executor_id: str, log_id: str):
    """Called when execution starts."""
    _active_executions[executor_id] = log_id


def mark_execution_done(executor_id: str):
    """Called when execution finishes (success or fail)."""
    _active_executions.pop(executor_id, None)
