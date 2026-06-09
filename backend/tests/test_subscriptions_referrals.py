"""Backend tests for Subscriptions and Referrals API."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-memory-hub-5.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def second_user():
    """Register a fresh second user for referral apply tests."""
    email = f"TEST_referee_{uuid.uuid4().hex[:8]}@example.com"
    password = "Testpass123!"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": password, "name": "Referee Test"})
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    return {"email": email, "password": password, "token": data["token"], "id": data["user"]["id"]}


# ── Subscription Tests ──
class TestSubscriptions:

    def test_status_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/subscriptions/status")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_status_recruit_for_free_user(self, second_user):
        h = {"Authorization": f"Bearer {second_user['token']}"}
        r = requests.get(f"{BASE_URL}/api/subscriptions/status", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "recruit"
        assert data["status"] == "free"
        assert data["label"] == "Recruit"
        assert data["agent_limit"] == 3

    def test_checkout_invalid_tier(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/subscriptions/checkout",
            headers=admin_headers,
            json={"tier": "invalid_tier", "origin_url": "https://example.com"},
        )
        assert r.status_code == 400, r.text
        assert "Invalid tier" in r.json().get("detail", "")

    def test_checkout_cadet_returns_stripe_url(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/subscriptions/checkout",
            headers=admin_headers,
            json={"tier": "cadet", "origin_url": "https://example.com"},
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        data = r.json()
        assert "url" in data
        assert "session_id" in data
        assert "stripe.com" in data["url"] or "checkout.stripe.com" in data["url"]

    def test_checkout_operator_returns_stripe_url(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/subscriptions/checkout",
            headers=admin_headers,
            json={"tier": "operator", "origin_url": "https://example.com"},
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        data = r.json()
        assert "url" in data
        assert "stripe.com" in data["url"] or "checkout.stripe.com" in data["url"]

    def test_checkout_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/subscriptions/checkout",
            json={"tier": "cadet", "origin_url": "https://example.com"},
        )
        assert r.status_code in (401, 403)

    def test_cancel_no_active_subscription_returns_404(self, second_user):
        h = {"Authorization": f"Bearer {second_user['token']}"}
        r = requests.post(f"{BASE_URL}/api/subscriptions/cancel", headers=h)
        assert r.status_code == 404, r.text
        assert "No active subscription" in r.json().get("detail", "")

    def test_cancel_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/subscriptions/cancel")
        assert r.status_code in (401, 403)


# ── Referral Tests ──
class TestReferrals:

    def test_my_code_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/referrals/my-code")
        assert r.status_code in (401, 403)

    def test_my_code_generates_format(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/referrals/my-code", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "code" in data
        code = data["code"]
        assert code.startswith("TF-"), f"Code format wrong: {code}"
        suffix = code.split("-", 1)[1]
        assert len(suffix) == 6, f"Suffix length wrong: {suffix}"
        assert suffix.isalnum() and suffix.isupper()
        assert "referral_count" in data
        assert "total_earned" in data

    def test_my_code_idempotent(self, admin_headers):
        r1 = requests.get(f"{BASE_URL}/api/referrals/my-code", headers=admin_headers)
        r2 = requests.get(f"{BASE_URL}/api/referrals/my-code", headers=admin_headers)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["code"] == r2.json()["code"], "Referral code changed between calls"

    def test_apply_invalid_code_returns_404(self, second_user):
        h = {"Authorization": f"Bearer {second_user['token']}"}
        r = requests.post(f"{BASE_URL}/api/referrals/apply", headers=h, json={"code": "TF-INVALID"})
        assert r.status_code == 404, r.text
        assert "Invalid referral code" in r.json().get("detail", "")

    def test_apply_own_code_returns_400(self, admin_headers):
        # Get admin's own code first
        rc = requests.get(f"{BASE_URL}/api/referrals/my-code", headers=admin_headers)
        own_code = rc.json()["code"]
        r = requests.post(f"{BASE_URL}/api/referrals/apply", headers=admin_headers, json={"code": own_code})
        assert r.status_code == 400, r.text
        assert "own referral" in r.json().get("detail", "").lower()

    def test_credits_endpoint(self, second_user):
        h = {"Authorization": f"Bearer {second_user['token']}"}
        r = requests.get(f"{BASE_URL}/api/referrals/credits", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "available_credit" in data
        assert "total_earned" in data
        assert isinstance(data["available_credit"], (int, float))
        assert isinstance(data["total_earned"], (int, float))

    def test_apply_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/referrals/apply", json={"code": "TF-AAAAAA"})
        assert r.status_code in (401, 403)

    def test_credits_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/referrals/credits")
        assert r.status_code in (401, 403)
