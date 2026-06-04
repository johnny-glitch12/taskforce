"""
sanitize — Input sanitization helpers for user-generated content.

Use these on free-text fields BEFORE storing to MongoDB so we never trust
what came off the wire. React auto-escapes JSX output, so XSS risk on read
is low, but we still strip HTML on write for defence-in-depth + cleaner
search indices.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    import bleach  # type: ignore
    _HAS_BLEACH = True
except ImportError:
    _HAS_BLEACH = False


_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: Optional[str], max_length: int = 10_000) -> str:
    """Strip HTML, control chars, and trim.

    - Removes HTML tags (no rich text allowed in plain text fields).
    - Strips control chars (NUL, etc.) that could corrupt downstream display.
    - Truncates to max_length.
    - Returns "" for None / non-str.
    """
    if not isinstance(value, str):
        return ""
    if _HAS_BLEACH:
        cleaned = bleach.clean(value, tags=[], attributes={}, strip=True)
    else:
        cleaned = _TAG_RE.sub("", value)
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    return cleaned.strip()[:max_length]


_SAFE_HTML_TAGS = ["p", "br", "strong", "em", "u", "ul", "ol", "li", "a", "code", "pre", "h1", "h2", "h3", "h4", "h5", "blockquote"]
_SAFE_HTML_ATTRS = {"a": ["href", "title", "target", "rel"]}


def sanitize_html(value: Optional[str], max_length: int = 50_000) -> str:
    """Allow a tightly-scoped HTML subset (markdown-y output).

    No <script>, no event handlers, no <iframe>, no <object>, no data: URLs.
    """
    if not isinstance(value, str):
        return ""
    if _HAS_BLEACH:
        cleaned = bleach.clean(
            value,
            tags=_SAFE_HTML_TAGS,
            attributes=_SAFE_HTML_ATTRS,
            protocols=["http", "https", "mailto"],
            strip=True,
        )
    else:
        # Conservative fallback if bleach isn't installed — strip ALL tags.
        cleaned = _TAG_RE.sub("", value)
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    return cleaned[:max_length]


def sanitize_url(value: Optional[str]) -> str:
    """Accept only http(s) URLs. Rejects javascript: / data: / file: protocols.

    Returns "" if the URL is unsafe — caller can validate and 400 the request.
    """
    if not isinstance(value, str):
        return ""
    v = value.strip()
    if not v:
        return ""
    low = v.lower()
    if low.startswith(("http://", "https://")):
        return v[:2000]
    return ""


def sanitize_user_response(user: dict) -> dict:
    """Strip sensitive fields before returning a user object to the client.

    The auth.py endpoints already return a curated `UserResponse` Pydantic model,
    but other code paths may surface raw user docs (e.g. admin endpoints listing
    users). Use this everywhere a raw dict is returned.
    """
    SAFE_FIELDS = {
        "id", "email", "name", "role", "is_owner", "tier", "avatar_url",
        "subscription_credits", "subscription_credits_max", "topup_credits",
        "credit_reset_date", "credits_used_total", "bounty_wins",
        "credits_won_total", "bounties_posted", "credits_paid_out_total",
        "created_at", "updated_at", "flagged_for_abuse", "banned",
    }
    return {k: v for k, v in (user or {}).items() if k in SAFE_FIELDS}


__all__ = ["sanitize_text", "sanitize_html", "sanitize_url", "sanitize_user_response"]
