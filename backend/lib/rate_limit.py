"""
In-memory sliding-window rate limiter — Task Force AI

Lightweight per-IP rate limiter for sensitive endpoints (auth/login/register).
v1: in-process dict. v2: swap to Redis-backed counter for horizontal scaling.

Usage:
    from lib.rate_limit import rate_limit_dependency
    @router.post("/auth/login")
    async def login(req: LoginRequest, _=Depends(rate_limit_dependency("login", 5, 60))):
        ...
"""
import time
from collections import defaultdict, deque
from typing import Callable
from fastapi import Request, HTTPException

_BUCKETS: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Honor X-Forwarded-For first (k8s ingress); fallback to client.host
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit_dependency(scope: str, max_calls: int, window_seconds: int) -> Callable:
    """
    Returns a FastAPI dependency that enforces max_calls per window_seconds
    per (scope, client_ip) tuple. Raises HTTP 429 on overflow.
    """
    async def _dep(request: Request):
        ip = _client_ip(request)
        key = f"{scope}:{ip}"
        now = time.time()
        cutoff = now - window_seconds
        bucket = _BUCKETS[key]
        # Evict old entries
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_calls:
            retry_after = int(window_seconds - (now - bucket[0]))
            raise HTTPException(
                status_code=429,
                detail=f"Too many '{scope}' attempts. Try again in {max(retry_after, 1)}s.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )
        bucket.append(now)
        # Reasonable safety: cap bucket length
        if len(bucket) > 1000:
            for _ in range(100):
                bucket.popleft()
        return None
    return _dep


def reset_for_tests():
    """Test helper — clears all buckets."""
    _BUCKETS.clear()
