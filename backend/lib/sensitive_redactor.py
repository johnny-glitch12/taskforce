"""
Sensitive-value redaction helpers — Task Force AI

Built in Phase 1 so the Phase 2 memory extractor can import it without a
touch-up. Strips API-key-shaped tokens and obvious password / secret / token
assignments from text before it crosses any boundary where it could be
logged or learned.

Not called anywhere yet — Phase 2 extractor will hook it into the
builder_memory extraction pipeline.
"""
import re
from typing import List

# ─── Patterns ───────────────────────────────────────────────
# Each pattern matches a full secret-shaped token (case-sensitive on prefix).
# Patterns are tuned conservatively — they target the obvious leak shapes
# without breaking ordinary prose.
_SECRET_PATTERNS: List[tuple[re.Pattern, str]] = [
    # OpenAI: sk-... (legacy), sk-proj-... (project keys), sk-svcacct-... etc.
    (re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}\b"), "[REDACTED_API_KEY]"),
    # Anthropic: sk-ant-...
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), "[REDACTED_API_KEY]"),
    # Google API keys: AIza...
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "[REDACTED_API_KEY]"),
    # GitHub: ghp_ / gho_ / ghu_ / ghs_ / ghr_
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"), "[REDACTED_API_KEY]"),
    # Slack: xoxb-, xoxp-, xoxa-, xoxr-
    (re.compile(r"\bxox[bparso]-[A-Za-z0-9\-]{10,}\b"), "[REDACTED_API_KEY]"),
    # Stripe live + test secret keys (separate from sk- so we catch sk_live_/sk_test_)
    (re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b"), "[REDACTED_API_KEY]"),
    # AWS access key ids (AKIA / ASIA prefix)
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED_API_KEY]"),
    # Generic JWTs (header.payload.signature — base64url segments)
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "[REDACTED_JWT]"),
]

# Generic "password=..." / "api_key: ..." / "secret = ..." form.
# Matches the assigned value greedily up to whitespace, quote, or end-of-line.
_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?P<key>password|passwd|secret|api[_\-]?key|apikey|access[_\-]?token|auth[_\-]?token|bearer|token)\b"
    r"\s*[:=]\s*"
    r"(?P<value>[\"']?[^\s\"'`,;]{6,}[\"']?)",
    flags=re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


def redact_secrets(text: str) -> str:
    """Strip secret-shaped substrings from a single text blob.

    Order of operations:
      1. Apply each high-confidence prefix pattern → replace match with [REDACTED].
      2. Apply the generic assignment pattern → replace the value half only,
         preserving the key name so the AI still knows a credential was there
         (e.g. "api_key: [REDACTED]" reads as a hint rather than mystery noise).

    Returns the redacted string. Idempotent on already-redacted text.
    """
    if not text:
        return text
    out = text
    for pat, token in _SECRET_PATTERNS:
        out = pat.sub(token, out)
    out = _ASSIGNMENT_PATTERN.sub(
        lambda m: f"{m.group('key')}={_REDACTED}",
        out,
    )
    return out


def is_fully_redacted(text: str) -> bool:
    """Return True if `text` consists ONLY of redaction tokens and whitespace/punctuation.
    Used by the memory extractor to drop entries that would carry no useful signal
    after sanitization (e.g. someone pasted only an API key)."""
    if not text:
        return True
    # Strip all known redaction tokens and remaining alnum/word content
    scrubbed = re.sub(r"\[REDACTED(?:_[A-Z_]+)?\]", "", text)
    # If nothing left but whitespace and punctuation, it's fully redacted
    return not re.search(r"[A-Za-z0-9]", scrubbed)


def redact_messages(messages: List[dict]) -> List[dict]:
    """Apply redact_secrets across a chat-history-shaped list of
    {role, content, ...} dicts. Returns a new list of new dicts — does not
    mutate the input. Non-string content (e.g. structured tool results) is
    passed through unchanged."""
    if not messages:
        return []
    out = []
    for m in messages:
        if not isinstance(m, dict):
            out.append(m)
            continue
        copy = dict(m)
        content = copy.get("content")
        if isinstance(content, str):
            copy["content"] = redact_secrets(content)
        out.append(copy)
    return out


__all__ = ["redact_secrets", "redact_messages", "is_fully_redacted"]
