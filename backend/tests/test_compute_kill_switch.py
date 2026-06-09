"""
Backend tests for Compute Credits Kill Switch (Iteration 25)

Covers:
  - GET /api/subscriptions/status returns `compute` block
  - Free user (freeuser@test.com, 100/100 used) is blocked
  - Admin (admin@nova.ai) bypasses with unlimited=True
  - 403 detail is a structured object with the required keys
  - Kill switch fires on:
      * POST /api/run-agent
      * POST /api/dashboard/agents/{id}/run
      * POST /api/webhook/agent/{key}
  - compute_usage is incremented after a successful dispatch
  - Monthly period rollover uses YYYY-MM format
"""
import os
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-memory-hub-5.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

FREE_EMAIL = "freeuser@test.com"
FREE_PASSWORD = "test123"
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"


# ────────────────────────────── Helpers ──────────────────────────────

def _login(email: str, password: str):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data["user"]


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def free_session():
    token, user = _login(FREE_EMAIL, FREE_PASSWORD)
    return {"token": token, "user": user, "headers": _auth(token)}


@pytest.fixture(scope="module")
def admin_session():
    token, user = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": token, "user": user, "headers": _auth(token)}


@pytest.fixture(scope="module")
def db():
    """Direct MongoDB handle for state setup/cleanup (sync pymongo)."""
    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _current_period():
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ────────────────────────────── Tests ──────────────────────────────


class TestSubscriptionStatusCompute:
    """GET /api/subscriptions/status must now include `compute` object."""

    def test_free_user_compute_block(self, free_session):
        r = requests.get(f"{API}/subscriptions/status", headers=free_session["headers"], timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "compute" in data, f"compute key missing in response: {data}"
        c = data["compute"]
        for k in ("used", "limit", "remaining", "tier", "period", "unlimited"):
            assert k in c, f"compute.{k} missing"
        assert c["limit"] == 100, f"Free user limit should be 100, got {c['limit']}"
        assert c["used"] == 100, f"Seed says used=100, got {c['used']}"
        assert c["remaining"] == 0
        assert c["unlimited"] is False
        assert c["period"] == _current_period()

    def test_admin_user_unlimited(self, admin_session):
        r = requests.get(f"{API}/subscriptions/status", headers=admin_session["headers"], timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "compute" in data
        c = data["compute"]
        assert c["unlimited"] is True, f"Admin should be unlimited: {c}"
        assert c["limit"] == 999999
        assert c["remaining"] == 999999


class TestRunAgentKillSwitch:
    """POST /api/run-agent should 403 when free user is depleted."""

    def test_free_user_blocked_on_run_agent(self, free_session):
        r = requests.post(
            f"{API}/run-agent",
            headers=free_session["headers"],
            json={"user_message": "hello", "system_prompt": "you are a test"},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        body = r.json()
        # FastAPI wraps it as {"detail": {...}}
        detail = body.get("detail")
        assert isinstance(detail, dict), f"detail must be a dict object, got: {type(detail).__name__} -> {detail}"
        for k in ("error", "message", "used", "limit", "tier", "upgrade_url", "upgrade_prompt"):
            assert k in detail, f"detail.{k} missing in {detail}"
        assert detail["error"] == "COMPUTE_LIMIT_REACHED"
        assert detail["used"] == 100
        assert detail["limit"] == 100
        assert detail["upgrade_url"] == "/pricing"


class TestDashboardAgentRunKillSwitch:
    """POST /api/dashboard/agents/{id}/run must check compute before agent lookup."""

    def test_free_user_blocked_on_dashboard_run(self, free_session):
        # Kill switch runs before agent_id lookup, so any UUID works.
        fake_agent_id = str(uuid.uuid4())
        r = requests.post(
            f"{API}/dashboard/agents/{fake_agent_id}/run",
            headers=free_session["headers"],
            json={"input_data": {}},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        detail = r.json().get("detail")
        assert isinstance(detail, dict)
        assert detail.get("error") == "COMPUTE_LIMIT_REACHED"
        assert detail.get("limit") == 100
        assert detail.get("used") == 100


class TestWebhookKillSwitch:
    """POST /api/webhook/agent/{key} must check the owner's credits."""

    def test_webhook_blocked_for_depleted_owner(self, db, free_session):
        # Seed a webhook-capable agent owned by the free user directly in MongoDB
        user_id = free_session["user"]["id"]
        agent_id = str(uuid.uuid4())
        webhook_key = f"TEST_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": agent_id,
            "user_id": user_id,
            "name": "TEST_webhook_agent",
            "description": "TEST",
            "code": "def main(input_data):\n    return {'ok': True}\n",
            "env_vars": {},
            "trigger_type": "webhook",
            "webhook_key": webhook_key,
            "status": "ready",
            "last_run": None,
            "last_result": None,
            "run_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        db.user_agents.insert_one(doc)

        try:
            r = requests.post(f"{API}/webhook/agent/{webhook_key}", json={"foo": "bar"}, timeout=20)
            assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
            detail = r.json().get("detail")
            assert isinstance(detail, dict), f"detail must be a dict: {detail}"
            assert detail.get("error") == "COMPUTE_LIMIT_REACHED"
        finally:
            db.user_agents.delete_one({"id": agent_id})


class TestAdminBypass:
    """Admin should be allowed past the kill switch on dashboard run path."""

    def test_admin_not_blocked_on_dashboard_run(self, admin_session):
        # 404 (agent not found) means kill switch did NOT block (which would be 403).
        fake_agent_id = str(uuid.uuid4())
        r = requests.post(
            f"{API}/dashboard/agents/{fake_agent_id}/run",
            headers=admin_session["headers"],
            json={"input_data": {}},
            timeout=20,
        )
        assert r.status_code != 403, f"Admin should bypass kill switch, but got 403: {r.text}"
        assert r.status_code == 404, f"Expected 404 (agent not found) for admin, got {r.status_code}: {r.text}"


class TestIncrementOnDispatch:
    """compute_usage should be incremented after a successful run dispatch."""

    def test_increment_after_dashboard_run(self, db):
        # Create a fresh user and an agent for them, then run.
        email = f"TEST_compute_{uuid.uuid4().hex[:8]}@test.com"
        password = "test1234"
        reg = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": password, "name": "TEST"},
            timeout=15,
        )
        assert reg.status_code in (200, 201), f"register failed: {reg.status_code} {reg.text}"
        token = reg.json()["token"]
        user_id = reg.json()["user"]["id"]
        headers = _auth(token)

        # Create an agent via API
        agent_payload = {
            "name": "TEST_increment_agent",
            "description": "TEST",
            "code": "def main(input_data):\n    return {'ok': True}\n",
            "env_vars": {},
            "trigger_type": "manual",
        }
        cr = requests.post(f"{API}/dashboard/agents", headers=headers, json=agent_payload, timeout=15)
        assert cr.status_code == 200, f"create agent failed: {cr.status_code} {cr.text}"
        agent_id = cr.json()["id"]

        # Status before run
        s0 = requests.get(f"{API}/subscriptions/status", headers=headers, timeout=15).json()
        used_before = s0["compute"]["used"]

        # Trigger the agent
        rr = requests.post(
            f"{API}/dashboard/agents/{agent_id}/run",
            headers=headers,
            json={"input_data": {}},
            timeout=30,
        )
        assert rr.status_code == 200, f"run failed: {rr.status_code} {rr.text}"

        # Status after run -> +1
        s1 = requests.get(f"{API}/subscriptions/status", headers=headers, timeout=15).json()
        used_after = s1["compute"]["used"]
        assert used_after == used_before + 1, (
            f"compute_usage did not increment: before={used_before} after={used_after}"
        )
        assert s1["compute"]["period"] == _current_period()

        # Cleanup
        db.user_agents.delete_many({"user_id": user_id})
        db.agent_executions.delete_many({"user_id": user_id})
        db.compute_usage.delete_many({"user_id": user_id})
        db.users.delete_one({"id": user_id})
