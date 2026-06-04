"""
security_middleware — Consolidated production security hardening for Task Force AI.

Adds:
  • Security headers on every response (X-Content-Type-Options, X-Frame-Options,
    HSTS, Permissions-Policy, Referrer-Policy, X-XSS-Protection)
  • Global exception handler that NEVER leaks stack traces / internals to clients
  • InvalidId handler (bson.errors.InvalidId → clean 400)

Wired in server.py near the CORS middleware.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security_middleware")


# Pages that DELIBERATELY render inside an iframe (e.g. /api/apps/{slug}/render).
# These bypass the global X-Frame-Options: DENY so the AppViewer page can embed them.
_IFRAME_ALLOWED_PREFIXES = ("/api/apps/",)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Stamps OWASP-recommended security headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        # HSTS — only honored over HTTPS. Set conservatively (1 year, include subdomains).
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        # Iframe policy:
        # The mini-app render endpoint must be embeddable from our own site.
        # Everything else gets DENY to defeat clickjacking.
        path = request.url.path
        allow_iframe = any(path.startswith(p) and path.endswith("/render") for p in _IFRAME_ALLOWED_PREFIXES)
        if allow_iframe:
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            # Allow the mini-app to load its CDN deps (React UMD, Babel-standalone, Tailwind CDN)
            response.headers.setdefault(
                "Content-Security-Policy",
                (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.tailwindcss.com; "
                    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                    "img-src 'self' data: https: blob:; "
                    "font-src 'self' data: https:; "
                    "connect-src 'self'; "
                    "frame-ancestors 'self';"
                ),
            )
        else:
            response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def install_security(app: FastAPI) -> None:
    """Mount security middleware + register global exception handler.

    Idempotent — safe to call once on app startup.
    """
    app.add_middleware(SecurityHeadersMiddleware)

    # Global catch-all: never leak stack traces / internal paths to the client.
    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        # Log internally with full trace
        logger.exception("[unhandled] %s", exc)
        # Don't override HTTPException — FastAPI handles those itself; this only
        # fires for unhandled errors that would otherwise dump a 500 stack.
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR",
                     "message": "Something went wrong. Please try again."},
        )

    # bson InvalidId → 400 (otherwise some routes 500 with internal trace)
    try:
        from bson.errors import InvalidId  # type: ignore

        @app.exception_handler(InvalidId)
        async def _invalid_id(_req: Request, _exc: InvalidId):
            return JSONResponse(
                status_code=400,
                content={"error": "INVALID_ID", "message": "Invalid resource id."},
            )
    except Exception:
        pass


def get_cors_origins() -> list[str]:
    """Return the allowed CORS origins list — tightens '*' default to a sane allow-list.

    Reads CORS_ORIGINS env (comma-separated). When unset, defaults to '*' (preview
    deployments need this — k8s ingress proxies arbitrary subdomains). Production
    deployments MUST set CORS_ORIGINS explicitly to lock this down.
    """
    raw = os.environ.get("CORS_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]


__all__ = ["SecurityHeadersMiddleware", "install_security", "get_cors_origins"]
