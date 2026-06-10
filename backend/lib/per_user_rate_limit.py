"""
Per-user sliding-window rate limiter — Task Force AI

Companion to lib/rate_limit.py (which is per-IP). Some routes — like the
builder memory CRUD — are user-scoped, so an IP-level bucket is wrong (mobile
tethering, NAT, kubernetes ingress). This module reuses the same in-process
deque pattern keyed on (scope, user_id).

Usage:
    from lib.per_user_rate_limit import user_rate_limit
    @router.get("/builder/memory")
    async def list_memory(user=Depends(get_current_user()), _=Depends(user_rate_limit("memory_read", 30, 60))):
        ...

The dependency requires the route to ALSO depend on get_current_user — the
limiter pulls user_id off the resolved user via the request scope (we use
request.state to communicate it). Cleanest pattern is to grab user from a
separate Depends and have the route pass user_id through state, but to keep
things ergonomic we read the JWT directly inside the dependency.
"""
import time
import logging
from collections import defaultdict, deque
from typing import Callable
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

logger = logging.getLogger("per_user_rate_limit")

_BUCKETS: dict[str, deque] = defaultdict(deque)
_security = HTTPBearer(auto_error=False)


def _user_id_from_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    """Best-effort user_id extraction from the Bearer token. If decoding
    fails, fall back to the literal token string so the bucket still scopes
    per-caller — auth check will reject downstream anyway."""
    if not credentials:
        return "anon"
    try:
        from server import decode_token  # noqa: WPS433 — avoid circular
        payload = decode_token(credentials.credentials)
        return str(payload.get("sub") or "anon")
    except Exception:
        # Truncate so we don't blow memory if token is huge.
        return credentials.credentials[:32]


def user_rate_limit(scope: str, max_calls: int, window_seconds: int) -> Callable:
    """Return a FastAPI dependency that enforces max_calls per window per (scope, user).
    Raises HTTP 429 with a Retry-After header on overflow."""
    async def _dep(request: Request, credentials: HTTPAuthorizationCredentials = Depends(_security)):
        uid = _user_id_from_token(credentials)
        key = f"{scope}:{uid}"
        now = time.time()
        cutoff = now - window_seconds
        bucket = _BUCKETS[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_calls:
            retry_after = int(window_seconds - (now - bucket[0]))
            raise HTTPException(
                status_code=429,
                detail=f"Too many '{scope}' requests. Try again in {max(retry_after, 1)}s.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )
        bucket.append(now)
        if len(bucket) > 1000:
            for _ in range(100):
                bucket.popleft()
        return None
    return _dep


def reset_for_tests():
    _BUCKETS.clear()


__all__ = ["user_rate_limit", "reset_for_tests"]
