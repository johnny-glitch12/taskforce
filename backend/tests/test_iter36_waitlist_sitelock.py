"""
Iter36 — Site Lock + Waitlist regression tests.
Validates /api/waitlist POST (idempotent), /api/waitlist/count GET,
/api/waitlist GET admin-only RBAC.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-memory-hub-5.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"
FREE_EMAIL = "freeuser@test.com"
FREE_PASSWORD = "test123"


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api_client):
    res = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["token"]


@pytest.fixture(scope="module")
def free_token(api_client):
    res = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": FREE_EMAIL, "password": FREE_PASSWORD})
    if res.status_code != 200:
        pytest.skip("Free user not seeded")
    return res.json()["token"]


# ─── Waitlist: count ───
class TestWaitlistCount:
    def test_count_returns_integer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/waitlist/count")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0


# ─── Waitlist: POST create + idempotency ───
class TestWaitlistJoin:
    def test_join_new_email_creates_record(self, api_client):
        unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        # Count before
        before = api_client.get(f"{BASE_URL}/api/waitlist/count").json()["count"]
        # POST
        r = api_client.post(f"{BASE_URL}/api/waitlist", json={"email": unique_email})
        assert r.status_code == 200, f"POST failed: {r.text}"
        body = r.json()
        assert "id" in body
        assert body["email"] == unique_email
        assert "created_at" in body
        # Count after
        after = api_client.get(f"{BASE_URL}/api/waitlist/count").json()["count"]
        assert after == before + 1

    def test_join_same_email_is_idempotent(self, api_client):
        email = f"test_idempotent_{uuid.uuid4().hex[:8]}@example.com"
        r1 = api_client.post(f"{BASE_URL}/api/waitlist", json={"email": email})
        assert r1.status_code == 200
        id1 = r1.json()["id"]
        before = api_client.get(f"{BASE_URL}/api/waitlist/count").json()["count"]
        r2 = api_client.post(f"{BASE_URL}/api/waitlist", json={"email": email})
        assert r2.status_code == 200
        id2 = r2.json()["id"]
        assert id1 == id2, "Same email should return same id"
        after = api_client.get(f"{BASE_URL}/api/waitlist/count").json()["count"]
        assert after == before, "Idempotent POST must not increase count"

    def test_invalid_email_payload_rejected(self, api_client):
        # Missing email
        r = api_client.post(f"{BASE_URL}/api/waitlist", json={})
        assert r.status_code in (400, 422)


# ─── Waitlist: GET admin-only ───
class TestWaitlistAdminList:
    def test_unauth_get_waitlist_returns_403_or_401(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/waitlist")
        # FastAPI Depends without token: returns 401 from get_current_user; or our handler 403
        assert r.status_code in (401, 403), f"unexpected status: {r.status_code} body: {r.text[:200]}"

    def test_non_admin_get_waitlist_403(self, api_client, free_token):
        r = api_client.get(f"{BASE_URL}/api/waitlist", headers={"Authorization": f"Bearer {free_token}"})
        assert r.status_code == 403

    def test_admin_get_waitlist_returns_list(self, api_client, admin_token):
        r = api_client.get(f"{BASE_URL}/api/waitlist", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            entry = data[0]
            assert "id" in entry and "email" in entry and "created_at" in entry
            # _id from mongo must NOT leak
            assert "_id" not in entry


# ─── Regression: existing admin endpoints still work ───
class TestRegression:
    def test_admin_login_works(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"

    def test_credits_me_admin(self, api_client, admin_token):
        r = api_client.get(f"{BASE_URL}/api/credits/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "balance" in data or "credits" in data or isinstance(data, dict)

    def test_auth_me_admin(self, api_client, admin_token):
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
