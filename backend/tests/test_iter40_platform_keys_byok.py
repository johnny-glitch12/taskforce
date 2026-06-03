"""
Iter40 — Platform Keys Default + BYOK Optional Override.
Covers:
  - /api/vibe/models: all 6 available=true, needs_byok=false, using_byok flag
  - /api/vibe/chat: works for ALL models via platform key (no 402 BYOK gate)
  - BYOK silent override: openai/anthropic stored key fronts the call (key_source='byok')
  - BYOK badge flag reflects stored credential
  - Model ID decoupling (api_model not exposed)
  - Claude works (mapped to versioned ids internally)
  - Per-model build cost: 3/5/5/2/5/2 for flash/pro/4o/mini/sonnet/haiku
"""
import os
import uuid
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"

MODEL_IDS = ["gemini-2.5-flash", "gemini-2.5-pro", "gpt-4o", "gpt-4o-mini", "claude-sonnet", "claude-haiku"]
EXPECTED_BUILD_COST = {
    "gemini-2.5-flash": 3, "gemini-2.5-pro": 5,
    "gpt-4o": 5, "gpt-4o-mini": 2,
    "claude-sonnet": 5, "claude-haiku": 2,
}


def _session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_client():
    s = _session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def _register_user(tag, db):
    s = _session()
    email = f"iter40_{tag}_{uuid.uuid4().hex[:8]}@test.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Passw0rd!", "name": f"Iter40 {tag}"}, timeout=20)
    if r.status_code == 200:
        tok = r.json().get("token") or r.json().get("access_token")
        s.headers["Authorization"] = f"Bearer {tok}"
        return s, email
    # DB fallback on IP cap
    import bcrypt as _b
    ph = _b.hashpw(b"Passw0rd!", _b.gensalt()).decode()
    uid = uuid.uuid4().hex
    db.users.insert_one({
        "id": uid, "email": email, "password_hash": ph, "name": f"Iter40 {tag}", "role": "user",
        "subscription_credits": 50, "topup_credits": 50, "tier": "recruit",
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    s2 = _session()
    rl = s2.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Passw0rd!"}, timeout=20)
    if rl.status_code != 200:
        pytest.skip(f"seeded login failed: {rl.text[:150]}")
    tok = rl.json().get("token") or rl.json().get("access_token")
    s2.headers["Authorization"] = f"Bearer {tok}"
    return s2, email


@pytest.fixture(scope="module")
def user_client(db):
    s, email = _register_user("u1", db)
    s._email = email
    return s


# ────────── MODELS ENDPOINT ──────────
class TestModels:
    def test_all_six_available_no_byok_gate(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/vibe/models", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["default"] == "gemini-2.5-flash"
        assert len(data["models"]) == 6
        ids = {m["id"] for m in data["models"]}
        assert ids == set(MODEL_IDS)
        for m in data["models"]:
            assert m["available"] is True, f"{m['id']} not available"
            assert m["needs_byok"] is False, f"{m['id']} needs_byok should be False"
            assert m["chat_cost"] == 1
            assert m["build_cost"] == EXPECTED_BUILD_COST[m["id"]]
            # api_model must NOT be exposed
            assert "api_model" not in m, f"api_model leaked for {m['id']}"

    def test_using_byok_false_without_keys(self, user_client, db):
        # Make sure no byok credentials for this user
        u = db.users.find_one({"email": user_client._email})
        db.byok_credentials.delete_many({"user_id": u["id"]})
        r = user_client.get(f"{BASE_URL}/api/vibe/models", timeout=15)
        assert r.status_code == 200
        for m in r.json()["models"]:
            assert m["using_byok"] is False, f"{m['id']} using_byok should be False"


# ────────── PLATFORM CALLS FOR ALL 6 MODELS ──────────
class TestPlatformChat:
    @pytest.mark.parametrize("model", MODEL_IDS)
    def test_chat_platform_each_model(self, admin_client, model):
        r = admin_client.post(f"{BASE_URL}/api/vibe/chat",
                              json={"message": "Reply with only the word OK", "model": model},
                              timeout=120)
        assert r.status_code == 200, f"{model}: HTTP {r.status_code} → {r.text[:300]}"
        d = r.json()
        assert d["model"] == model
        assert d["key_source"] == "platform", f"{model}: key_source={d.get('key_source')}"
        assert d["credits_used"] == 1
        assert isinstance(d["response"], str) and len(d["response"]) > 0


# ────────── BYOK SILENT OVERRIDE ──────────
class TestBYOKOverride:
    def test_save_openai_byok_and_route(self, user_client, db):
        # Clean slate
        u = db.users.find_one({"email": user_client._email})
        db.byok_credentials.delete_many({"user_id": u["id"]})
        # Save fake openai key via API
        r = user_client.post(f"{BASE_URL}/api/workflows/credentials",
                             json={"service": "openai", "api_key": "sk-test-fake-12345-xxx"}, timeout=15)
        assert r.status_code in (200, 201), f"credentials save failed: {r.text[:200]}"

        # Verify badge flag in /vibe/models
        rm = user_client.get(f"{BASE_URL}/api/vibe/models", timeout=15)
        assert rm.status_code == 200
        m_map = {m["id"]: m for m in rm.json()["models"]}
        assert m_map["gpt-4o"]["using_byok"] is True
        assert m_map["gpt-4o-mini"]["using_byok"] is True
        assert m_map["gemini-2.5-flash"]["using_byok"] is False
        assert m_map["claude-sonnet"]["using_byok"] is False

        # Call chat with gpt-4o — expect either 502 (fake key fails upstream)
        # OR 200 with key_source='byok'. If 200, key_source MUST be 'byok'.
        r2 = user_client.post(f"{BASE_URL}/api/vibe/chat",
                              json={"message": "hi", "model": "gpt-4o"}, timeout=60)
        # The resolution path picks BYOK; LLM provider rejects fake key → 502 expected.
        # No 402 gate must be returned (the old BYOK_REQUIRED gate is gone).
        assert r2.status_code != 402, "Old BYOK_REQUIRED gate must NOT trigger"
        if r2.status_code == 200:
            assert r2.json().get("key_source") == "byok"
        else:
            # 502 is acceptable (fake key)
            assert r2.status_code == 502, f"unexpected status {r2.status_code}: {r2.text[:200]}"

        # Cleanup credential
        user_client.delete(f"{BASE_URL}/api/workflows/credentials/openai", timeout=15)

    def test_corrupted_byok_falls_back_to_platform(self, user_client, db):
        """If decrypt_key throws, code falls back to platform key silently."""
        u = db.users.find_one({"email": user_client._email})
        db.byok_credentials.delete_many({"user_id": u["id"]})
        # Inject corrupted ciphertext directly (uses enc:v1: prefix so decrypt_key
        # actually tries to decrypt; the bogus token will fail and return "").
        db.byok_credentials.insert_one({
            "user_id": u["id"], "service": "openai",
            "api_key": "enc:v1:BOGUS-CIPHERTEXT-NOT-FERNET",
            "created_at": "2026-01-01T00:00:00+00:00",
        })
        r = user_client.post(f"{BASE_URL}/api/vibe/chat",
                             json={"message": "say OK", "model": "gpt-4o"}, timeout=120)
        # Decrypt fails → falls through to platform key → 200
        assert r.status_code == 200, f"fallback failed: {r.text[:200]}"
        assert r.json()["key_source"] == "platform"
        # cleanup
        db.byok_credentials.delete_many({"user_id": u["id"]})


# ────────── ADMIN CREDIT BYPASS ──────────
class TestAdminCreditBypass:
    def test_admin_chat_no_real_debit(self, admin_client, db):
        admin = db.users.find_one({"email": ADMIN_EMAIL})
        before_sub = admin.get("subscription_credits", 0)
        before_top = admin.get("topup_credits", 0)
        r = admin_client.post(f"{BASE_URL}/api/vibe/chat",
                              json={"message": "say OK", "model": "gemini-2.5-flash"}, timeout=60)
        assert r.status_code == 200
        admin_after = db.users.find_one({"email": ADMIN_EMAIL})
        # Admin bypass: balance should not have decreased
        assert admin_after.get("subscription_credits", 0) == before_sub
        assert admin_after.get("topup_credits", 0) == before_top


# ────────── REGRESSION: armory/build-bot exists ──────────
class TestRegression:
    def test_armory_build_bot_route_exists(self, admin_client):
        try:
            r = admin_client.post(f"{BASE_URL}/api/armory/build-bot",
                                  json={"prompt": "noop", "model": "gemini-2.5-flash"}, timeout=15)
            assert r.status_code != 404
        except requests.exceptions.ReadTimeout:
            pass  # slow LLM call, route exists
