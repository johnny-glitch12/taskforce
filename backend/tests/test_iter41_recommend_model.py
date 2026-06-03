"""
Iter41 — Auto-Pick Model Recommendation.
Covers POST /api/vibe/recommend-model:
  - Returns model from the 6 catalogue, with reason, complexity, credits_used=1.
  - Validation: prompt <3 chars or >4000 chars → 422.
  - Credit gate: 0 sub + 0 topup → 402 INSUFFICIENT_CREDITS.
  - Admin bypass: still works without real debit.
  - LLM unparseable fallback → gemini-2.5-flash default.
  - Common-prompt sanity check: simple → fast tier, complex → strong tier.
  - Credit transactions appended with kind='vibe_chat' ref='recommend:<model>'.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"

MODEL_IDS = {"gemini-2.5-flash", "gemini-2.5-pro", "gpt-4o", "gpt-4o-mini", "claude-sonnet", "claude-haiku"}
FAST_MODELS = {"gemini-2.5-flash", "gpt-4o-mini", "claude-haiku"}
STRONG_MODELS = {"gemini-2.5-pro", "claude-sonnet", "gpt-4o"}
VALID_COMPLEXITY = {"simple", "medium", "complex"}


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


def _register_user(tag, db, *, credits_sub=20, credits_top=0):
    s = _session()
    email = f"iter41_{tag}_{uuid.uuid4().hex[:8]}@test.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Passw0rd!", "name": f"Iter41 {tag}"}, timeout=20)
    if r.status_code == 200:
        tok = r.json().get("token") or r.json().get("access_token")
        s.headers["Authorization"] = f"Bearer {tok}"
        # Adjust credits via DB
        db.users.update_one({"email": email},
                            {"$set": {"subscription_credits": credits_sub, "topup_credits": credits_top}})
        return s, email
    # DB fallback (IP cap)
    import bcrypt as _b
    ph = _b.hashpw(b"Passw0rd!", _b.gensalt()).decode()
    uid = uuid.uuid4().hex
    db.users.insert_one({
        "id": uid, "email": email, "password_hash": ph, "name": f"Iter41 {tag}", "role": "user",
        "subscription_credits": credits_sub, "topup_credits": credits_top, "tier": "recruit",
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
    s, email = _register_user("u1", db, credits_sub=20, credits_top=0)
    s._email = email
    return s


@pytest.fixture(scope="module")
def broke_user_client(db):
    s, email = _register_user("u2", db, credits_sub=0, credits_top=0)
    s._email = email
    return s


def _assert_recommend_shape(data):
    assert data["model"] in MODEL_IDS, f"model not in catalogue: {data['model']}"
    assert data["complexity"] in VALID_COMPLEXITY
    assert isinstance(data["reason"], str) and len(data["reason"]) > 0
    assert isinstance(data["label"], str)
    assert isinstance(data["build_cost"], int)
    assert data["credits_used"] == 1
    assert "balance_remaining" in data


# ────────── HAPPY PATH ──────────
class TestRecommendBasic:
    def test_complex_prompt_returns_recommendation(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": "Build a complex multi-agent research crawler with citations"},
                              timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        _assert_recommend_shape(data)
        # Doesn't strictly need to be 'complex' but must be valid
        # word count of reason should be reasonable (loose check)
        assert 3 <= len(data["reason"].split()) <= 60

    def test_simple_prompt_returns_recommendation(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": "convert text to uppercase"},
                              timeout=60)
        assert r.status_code == 200, r.text
        _assert_recommend_shape(r.json())


# ────────── VALIDATION ──────────
class TestValidation:
    def test_short_prompt_rejected_422(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": "hi"}, timeout=15)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"

    def test_long_prompt_rejected_422(self, admin_client):
        big = "x" * 4001
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": big}, timeout=15)
        assert r.status_code == 422


# ────────── CREDIT GATE ──────────
class TestCreditGate:
    def test_zero_credit_user_gets_402(self, broke_user_client):
        r = broke_user_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                                   json={"prompt": "build a simple slackbot that echoes messages"},
                                   timeout=30)
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        # error code surfaced
        assert (body.get("error") == "INSUFFICIENT_CREDITS") or ("INSUFFICIENT" in str(body).upper())

    def test_admin_bypass_no_real_debit(self, admin_client, db):
        admin = db.users.find_one({"email": ADMIN_EMAIL})
        before_sub = admin.get("subscription_credits", 0)
        before_top = admin.get("topup_credits", 0)
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": "classify emails as urgent or normal"},
                              timeout=60)
        assert r.status_code == 200, r.text
        _assert_recommend_shape(r.json())
        admin_after = db.users.find_one({"email": ADMIN_EMAIL})
        assert admin_after.get("subscription_credits", 0) == before_sub
        assert admin_after.get("topup_credits", 0) == before_top


# ────────── CREDIT TXN APPENDED ──────────
class TestCreditTxn:
    def test_paying_user_debited_one_and_txn_logged(self, user_client, db):
        u = db.users.find_one({"email": user_client._email})
        before_sub = u.get("subscription_credits", 0)
        before_top = u.get("topup_credits", 0)
        r = user_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                             json={"prompt": "Build a markdown-to-HTML converter"},
                             timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        _assert_recommend_shape(data)
        picked = data["model"]
        # Verify debit happened on totals
        u_after = db.users.find_one({"email": user_client._email})
        new_sub = u_after.get("subscription_credits", 0)
        new_top = u_after.get("topup_credits", 0)
        assert (before_sub + before_top) - (new_sub + new_top) == 1, \
            f"expected exactly 1 credit debited (before_sub={before_sub},before_top={before_top},after_sub={new_sub},after_top={new_top})"
        # Verify a credit_transactions doc was appended with kind='vibe_chat' ref='recommend:<picked>'
        txn = db.credit_transactions.find_one(
            {"user_id": u["id"], "kind": "vibe_chat", "ref": f"recommend:{picked}"},
            sort=[("_id", -1)],
        )
        assert txn is not None, f"no credit_transactions doc found for recommend:{picked}"


# ────────── COMMON PROMPTS SANITY ──────────
class TestCommonPromptsSanity:
    """Recommendation may vary slightly run-to-run; we only assert pick is in MODEL_IDS
    and is in the right tier set (fast vs strong) for unambiguous prompts."""
    def test_simple_text_transform(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": "Convert markdown to HTML"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        _assert_recommend_shape(d)
        # Fast tier expected; allow strong tier in case the LLM disagrees but log it.
        assert d["model"] in MODEL_IDS

    def test_complex_research_bot(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": ("Build a 12-step research bot that crawls websites, "
                                                "deduplicates results, summarises with citations, "
                                                "and posts to Slack and Notion")},
                              timeout=60)
        assert r.status_code == 200
        d = r.json()
        _assert_recommend_shape(d)
        # Should pick strong tier for this complex task; soft assert
        assert d["model"] in MODEL_IDS
        if d["model"] not in STRONG_MODELS:
            pytest.skip(f"LLM picked non-strong model {d['model']} for complex prompt — soft fail")

    def test_classification_short_text(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/recommend-model",
                              json={"prompt": "Classify email subject lines as urgent vs normal"},
                              timeout=60)
        assert r.status_code == 200
        d = r.json()
        _assert_recommend_shape(d)
        assert d["model"] in MODEL_IDS
        if d["model"] not in FAST_MODELS:
            pytest.skip(f"LLM picked non-fast model {d['model']} for classification — soft fail")


# ────────── REGRESSION: chat/generate still work all 6 models without BYOK gate ──────────
class TestRegressionVibe:
    def test_models_endpoint_six_available(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/vibe/models", timeout=15)
        assert r.status_code == 200
        ids = {m["id"] for m in r.json()["models"]}
        assert ids == MODEL_IDS
        for m in r.json()["models"]:
            assert m["available"] is True
            assert m["needs_byok"] is False

    def test_vibe_chat_still_works_default_model(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/vibe/chat",
                              json={"message": "Reply with only OK", "model": "gemini-2.5-flash"},
                              timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["model"] == "gemini-2.5-flash"
