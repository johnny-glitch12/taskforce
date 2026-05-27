"""
BYOK Credential Encryption — Task Force AI

Provider-pluggable encryption. v1 default is `local` (Fernet from BYOK_MASTER_KEY env).
Set BYOK_KMS_PROVIDER=aws|gcp|vault to switch backends (stubs raise w/ migration
guidance; wire concrete clients before production).

⚠️ Production checklist:
    1. Set BYOK_KMS_PROVIDER=aws  (or gcp / vault)
    2. Rotate BYOK_MASTER_KEY off-host into your KMS
    3. Re-encrypt existing rows with a migration script
"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


_PROVIDER = (os.environ.get("BYOK_KMS_PROVIDER") or "local").lower()


def _get_local_fernet() -> Fernet:
    """v1 local provider — Fernet key derived from BYOK_MASTER_KEY env."""
    master = os.environ.get("BYOK_MASTER_KEY") or os.environ.get("JWT_SECRET", "fallback-dev-key")
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def _kms_not_ready(provider: str):
    raise NotImplementedError(
        f"BYOK_KMS_PROVIDER='{provider}' requires the platform team to wire the "
        f"concrete client. v1 only supports 'local'. Set BYOK_KMS_PROVIDER=local or "
        f"implement the encrypt/decrypt hook in lib/byok_crypto.py."
    )


def encrypt_key(plaintext: str) -> str:
    """Encrypt a credential. Returns 'enc:<provider>:<token>' for migration tracking."""
    if not plaintext:
        return ""
    if _PROVIDER == "local":
        f = _get_local_fernet()
        token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return f"enc:v1:{token}"
    if _PROVIDER in ("aws", "gcp", "vault"):
        _kms_not_ready(_PROVIDER)
    raise ValueError(f"Unknown BYOK_KMS_PROVIDER: {_PROVIDER}")


def decrypt_key(stored: str) -> str:
    """Decrypt a stored credential. Plaintext (no prefix) returned as-is (legacy)."""
    if not stored:
        return ""
    if not stored.startswith("enc:"):
        return stored  # legacy plaintext
    # Format: enc:<version>:<token>
    parts = stored.split(":", 2)
    if len(parts) != 3:
        return ""
    version, token = parts[1], parts[2]
    if version == "v1":
        f = _get_local_fernet()
        try:
            return f.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return ""
    if version in ("aws-v1", "gcp-v1", "vault-v1"):
        _kms_not_ready(version)
    return ""


def provider_info() -> dict:
    """Diagnostic — exposes which BYOK backend is currently active."""
    return {
        "provider": _PROVIDER,
        "supported": ["local", "aws (stub)", "gcp (stub)", "vault (stub)"],
        "version_prefix": "enc:v1:" if _PROVIDER == "local" else f"enc:{_PROVIDER}-v1:",
    }
