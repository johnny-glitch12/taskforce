"""
Memory content encryption — Task Force AI

Fernet-based at-rest encryption for builder_memories, builder_profiles, and
other memory-system collections. Mirrors the style of lib/byok_crypto.py but
is intentionally kept separate so the two keys can be rotated independently
(BYOK rotation must NOT invalidate the user's accumulated memory and vice
versa).

Storage format:
    enc:mem:v1:<fernet-token>

Legacy / dev-seeded plaintext rows pass through `decrypt_text` unchanged so
migrations don't have to be flag-day.

Key resolution order (first non-empty wins):
    1. MEMORY_MASTER_KEY  (preferred — set in Phase 0 .env)
    2. BYOK_MASTER_KEY    (fallback — keeps dev working when memory key not set)
    3. JWT_SECRET         (last-resort fallback for local dev only)

The Fernet key is derived deterministically: sha256(master).digest() →
urlsafe-b64encode → 32-byte Fernet key. This means the same env value always
yields the same key, so rows encrypted on one boot stay readable on the next.
"""
import os
import base64
import hashlib
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("memory_crypto")

_VERSION_PREFIX = "enc:mem:v1:"
_fernet_cache: Fernet | None = None


def _resolve_master() -> str:
    """Return the first configured master key from the resolution chain.
    Raises RuntimeError on first use if NONE are set — this keeps app boot
    cheap and only fails when a memory operation is actually attempted."""
    for env_name in ("MEMORY_MASTER_KEY", "BYOK_MASTER_KEY", "JWT_SECRET"):
        v = os.environ.get(env_name)
        if v:
            return v
    raise RuntimeError(
        "No memory encryption key configured. Set one of "
        "MEMORY_MASTER_KEY / BYOK_MASTER_KEY / JWT_SECRET in backend/.env"
    )


def _get_fernet() -> Fernet:
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache
    master = _resolve_master()
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    _fernet_cache = Fernet(fernet_key)
    return _fernet_cache


# ─── Public API ───────────────────────────────────────────────
def encrypt_text(plaintext: str) -> str:
    """Encrypt a string. Returns the empty string for empty/None input so we
    don't write `enc:mem:v1:<garbage>` rows for blank user-supplied fields."""
    if not plaintext:
        return ""
    token = _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_VERSION_PREFIX}{token}"


def decrypt_text(stored: str) -> str:
    """Decrypt a stored string. Passes plaintext through unchanged so that
    dev-seeded or legacy rows don't break. Logs a warning on real ciphertext
    that fails to decrypt (bad key, corrupted blob) and returns empty string."""
    if not stored:
        return ""
    if not stored.startswith(_VERSION_PREFIX):
        # Plaintext passthrough — supports legacy / dev rows.
        return stored
    token = stored[len(_VERSION_PREFIX):]
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("[memory_crypto] decrypt failed (InvalidToken) — wrong key or tampered ciphertext")
        return ""
    except Exception as e:  # noqa: BLE001 — graceful degrade
        logger.warning(f"[memory_crypto] decrypt failed: {type(e).__name__}: {e}")
        return ""


def encrypt_dict(d: Any) -> Any:
    """Recursively encrypt string values inside a dict / list structure.
    Keys are NEVER encrypted. Non-string scalars (int, bool, float, None) and
    nested containers pass through. Returns a new structure — does not mutate.
    Used for builder_profiles.business and similar nested objects.
    """
    if isinstance(d, dict):
        return {k: encrypt_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [encrypt_dict(v) for v in d]
    if isinstance(d, str):
        return encrypt_text(d)
    return d


def decrypt_dict(d: Any) -> Any:
    """Inverse of encrypt_dict. Recursively decrypts string values."""
    if isinstance(d, dict):
        return {k: decrypt_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [decrypt_dict(v) for v in d]
    if isinstance(d, str):
        return decrypt_text(d)
    return d


def provider_info() -> dict:
    """Diagnostic helper — does NOT expose the key itself."""
    return {
        "version_prefix": _VERSION_PREFIX,
        "key_source": next(
            (n for n in ("MEMORY_MASTER_KEY", "BYOK_MASTER_KEY", "JWT_SECRET") if os.environ.get(n)),
            None,
        ),
        "initialised": _fernet_cache is not None,
    }


__all__ = [
    "encrypt_text", "decrypt_text", "encrypt_dict", "decrypt_dict", "provider_info",
]
