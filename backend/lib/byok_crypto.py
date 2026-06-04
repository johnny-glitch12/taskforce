"""
BYOK Credential Encryption — Task Force AI

Provider-pluggable encryption for at-rest BYOK credentials. The active backend
is selected by the BYOK_KMS_PROVIDER env var:

    local  (default)  — Fernet from BYOK_MASTER_KEY env (dev / preview)
    aws               — AWS KMS via boto3 (production)
    gcp               — Google Cloud KMS via google-cloud-kms (production)
    vault             — HashiCorp Vault Transit (production)

For AWS / GCP / Vault, the corresponding library is imported lazily and the
adapter raises at init time with a clear message if the SDK or env vars are
missing. This keeps the local dev path zero-dep.

Storage format: `enc:<provider-version>:<token>`
    Local: `enc:v1:<fernet>`
    AWS:   `enc:aws-v1:<b64-ciphertext-blob>`
    GCP:   `enc:gcp-v1:<b64-ciphertext>`
    Vault: `enc:vault-v1:<vault-ciphertext>`

Existing rows encrypted by an older provider continue to decrypt correctly
because the provider is read from the ciphertext prefix, not the env var.
This lets the operator do a "dual-write / one-shot migration" rotation
without downtime.
"""
import os
import base64
import hashlib
import logging
from typing import Callable, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("byok_crypto")

_PROVIDER = (os.environ.get("BYOK_KMS_PROVIDER") or "local").lower()


# ─── Local (Fernet) ─────────────────────────────────────
def _get_local_fernet() -> Fernet:
    """v1 local provider — Fernet key derived from BYOK_MASTER_KEY env."""
    master = os.environ.get("BYOK_MASTER_KEY") or os.environ.get("JWT_SECRET", "fallback-dev-key")
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def _local_encrypt(plaintext: str) -> str:
    f = _get_local_fernet()
    token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{token}"


def _local_decrypt(token: str) -> str:
    f = _get_local_fernet()
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


# ─── AWS KMS ────────────────────────────────────────────
_AWS_CLIENT = None


def _aws_client():
    """Lazy-init boto3 KMS client. Raises if SDK or AWS_KMS_KEY_ID missing."""
    global _AWS_CLIENT
    if _AWS_CLIENT is not None:
        return _AWS_CLIENT
    try:
        import boto3  # noqa: WPS433
    except ImportError as e:
        raise RuntimeError("BYOK_KMS_PROVIDER=aws requires `boto3`. Install with `pip install boto3`.") from e
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    _AWS_CLIENT = boto3.client("kms", region_name=region)
    return _AWS_CLIENT


def _aws_encrypt(plaintext: str) -> str:
    key_id = os.environ.get("AWS_KMS_KEY_ID")
    if not key_id:
        raise RuntimeError("AWS_KMS_KEY_ID env var required for BYOK_KMS_PROVIDER=aws")
    client = _aws_client()
    resp = client.encrypt(KeyId=key_id, Plaintext=plaintext.encode("utf-8"))
    blob = base64.urlsafe_b64encode(resp["CiphertextBlob"]).decode("utf-8")
    return f"enc:aws-v1:{blob}"


def _aws_decrypt(token: str) -> str:
    client = _aws_client()
    try:
        blob = base64.urlsafe_b64decode(token.encode("utf-8"))
        resp = client.decrypt(CiphertextBlob=blob)
        return resp["Plaintext"].decode("utf-8")
    except Exception as e:
        logger.warning(f"[byok_crypto:aws] decrypt failed: {e}")
        return ""


# ─── Google Cloud KMS ───────────────────────────────────
_GCP_CLIENT = None
_GCP_KEY_NAME: Optional[str] = None


def _gcp_client():
    """Lazy-init google-cloud-kms client. Resolves the full key resource path once."""
    global _GCP_CLIENT, _GCP_KEY_NAME
    if _GCP_CLIENT is not None:
        return _GCP_CLIENT, _GCP_KEY_NAME
    try:
        from google.cloud import kms  # noqa: WPS433
    except ImportError as e:
        raise RuntimeError("BYOK_KMS_PROVIDER=gcp requires `google-cloud-kms`. Install with `pip install google-cloud-kms`.") from e
    project = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_KMS_LOCATION", "global")
    keyring = os.environ.get("GCP_KMS_KEYRING")
    key = os.environ.get("GCP_KMS_KEY")
    if not all([project, keyring, key]):
        raise RuntimeError("GCP KMS requires GCP_PROJECT_ID + GCP_KMS_KEYRING + GCP_KMS_KEY env vars.")
    _GCP_CLIENT = kms.KeyManagementServiceClient()
    _GCP_KEY_NAME = _GCP_CLIENT.crypto_key_path(project, location, keyring, key)
    return _GCP_CLIENT, _GCP_KEY_NAME


def _gcp_encrypt(plaintext: str) -> str:
    client, key = _gcp_client()
    resp = client.encrypt(request={"name": key, "plaintext": plaintext.encode("utf-8")})
    blob = base64.urlsafe_b64encode(resp.ciphertext).decode("utf-8")
    return f"enc:gcp-v1:{blob}"


def _gcp_decrypt(token: str) -> str:
    client, key = _gcp_client()
    try:
        blob = base64.urlsafe_b64decode(token.encode("utf-8"))
        resp = client.decrypt(request={"name": key, "ciphertext": blob})
        return resp.plaintext.decode("utf-8")
    except Exception as e:
        logger.warning(f"[byok_crypto:gcp] decrypt failed: {e}")
        return ""


# ─── HashiCorp Vault Transit ────────────────────────────
def _vault_client():
    try:
        import hvac  # noqa: WPS433
    except ImportError as e:
        raise RuntimeError("BYOK_KMS_PROVIDER=vault requires `hvac`. Install with `pip install hvac`.") from e
    addr = os.environ.get("VAULT_ADDR")
    token = os.environ.get("VAULT_TOKEN")
    if not addr or not token:
        raise RuntimeError("Vault KMS requires VAULT_ADDR + VAULT_TOKEN env vars.")
    client = hvac.Client(url=addr, token=token)
    if not client.is_authenticated():
        raise RuntimeError("Vault client failed to authenticate — check VAULT_TOKEN.")
    return client


def _vault_encrypt(plaintext: str) -> str:
    client = _vault_client()
    key = os.environ.get("VAULT_TRANSIT_KEY", "tfai-byok")
    b64_plain = base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")
    resp = client.secrets.transit.encrypt_data(name=key, plaintext=b64_plain)
    cipher = resp["data"]["ciphertext"]
    return f"enc:vault-v1:{cipher}"


def _vault_decrypt(token: str) -> str:
    client = _vault_client()
    key = os.environ.get("VAULT_TRANSIT_KEY", "tfai-byok")
    try:
        resp = client.secrets.transit.decrypt_data(name=key, ciphertext=token)
        return base64.b64decode(resp["data"]["plaintext"]).decode("utf-8")
    except Exception as e:
        logger.warning(f"[byok_crypto:vault] decrypt failed: {e}")
        return ""


# ─── Dispatch Table ─────────────────────────────────────
_ENCRYPTERS: dict[str, Callable[[str], str]] = {
    "local": _local_encrypt, "aws": _aws_encrypt, "gcp": _gcp_encrypt, "vault": _vault_encrypt,
}
_DECRYPTERS: dict[str, Callable[[str], str]] = {
    "v1": _local_decrypt, "aws-v1": _aws_decrypt, "gcp-v1": _gcp_decrypt, "vault-v1": _vault_decrypt,
}


def encrypt_key(plaintext: str) -> str:
    """Encrypt a credential with the active KMS provider. Returns 'enc:<v>:<tok>'."""
    if not plaintext:
        return ""
    enc = _ENCRYPTERS.get(_PROVIDER)
    if enc is None:
        raise ValueError(f"Unknown BYOK_KMS_PROVIDER: {_PROVIDER}")
    return enc(plaintext)


def decrypt_key(stored: str) -> str:
    """Decrypt by reading the version prefix — provider-agnostic so a rotated
    database (e.g. some rows still local, some on aws) decrypts cleanly during
    a dual-write migration."""
    if not stored:
        return ""
    if not stored.startswith("enc:"):
        return stored  # legacy plaintext
    parts = stored.split(":", 2)
    if len(parts) != 3:
        return ""
    version, token = parts[1], parts[2]
    dec = _DECRYPTERS.get(version)
    if dec is None:
        logger.warning(f"[byok_crypto] unknown ciphertext version: {version}")
        return ""
    try:
        return dec(token)
    except Exception as e:
        logger.warning(f"[byok_crypto] decrypt error for version {version}: {e}")
        return ""


def provider_info() -> dict:
    """Diagnostic — exposes which BYOK backend is currently active."""
    return {
        "active_provider": _PROVIDER,
        "supported": ["local", "aws", "gcp", "vault"],
        "version_prefix": f"enc:{_PROVIDER}-v1:" if _PROVIDER != "local" else "enc:v1:",
        "rotation_safe": True,
    }
