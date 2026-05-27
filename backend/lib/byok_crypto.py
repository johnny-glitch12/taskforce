"""
BYOK Credential Encryption — Task Force AI

Encrypts user-provided api_keys/tokens at rest using Fernet (AES-128-CBC + HMAC).
Master key is derived from BYOK_MASTER_KEY env var. Old plaintext rows are
auto-migrated on first read.

⚠️ For v1 the BYOK_MASTER_KEY lives in backend/.env. Production: rotate to KMS-
managed key (AWS KMS / GCP KMS / HashiCorp Vault).
"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """Derive a Fernet key from BYOK_MASTER_KEY env (or JWT_SECRET fallback for dev)."""
    master = os.environ.get("BYOK_MASTER_KEY") or os.environ.get("JWT_SECRET", "fallback-dev-key")
    # Fernet requires a 32-byte url-safe base64 key
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_key(plaintext: str) -> str:
    """Encrypt a credential. Returns 'enc:v1:<token>' prefix for migration."""
    if not plaintext:
        return ""
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{token}"


def decrypt_key(stored: str) -> str:
    """Decrypt a stored credential. Returns plaintext as-is if not encrypted (legacy)."""
    if not stored:
        return ""
    if not stored.startswith("enc:v1:"):
        # Legacy plaintext — return as-is (will be re-encrypted on next save)
        return stored
    token = stored[len("enc:v1:"):]
    f = _get_fernet()
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
