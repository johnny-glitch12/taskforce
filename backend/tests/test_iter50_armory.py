"""Iter50 — Armory test-run endpoint + regression for vibe/* and bot-projects."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dark-mode-nova.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@nova.ai", "password": "admin123"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Vibe regression ─────────────────────────────────────
class TestVibeRegression:
    def test_models_endpoint(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/vibe/models", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "models" in d and isinstance(d["models"], list)
        ids = {m["id"] for m in d["models"]}
        assert "gemini-2.5-flash" in ids
        assert "gemini-2.5-pro" in ids
        # Has build_cost
        assert any("build_cost" in m for m in d["models"])

    def test_sessions_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/vibe/sessions", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert "sessions" in r.json()

    def test_chat_endpoint_short(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/vibe/chat",
            headers=admin_headers,
            json={"session_id": None, "message": "Say OK and exit.", "model": "gemini-2.5-flash"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "response" in d
        assert "session_id" in d


# ─── Bot-projects GET still works ───────────────────────
class TestBotProjects:
    def test_list_projects(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/armory/bot-projects", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert "projects" in r.json()


# ─── NEW Test-run endpoint ──────────────────────────────
@pytest.fixture(scope="module")
def project_with_nodes(admin_headers):
    """Find any existing admin project with nodes, else create a minimal one via Mongo-shaped POST.
    Falls back to skip if no projects exist."""
    r = requests.get(f"{BASE_URL}/api/armory/bot-projects", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    projects = r.json().get("projects", [])
    # Need full project to see nodes — list endpoint omits commit_history; nodes are still present
    for p in projects:
        if p.get("nodes"):
            return p
    pytest.skip("No bot_project with nodes available — skipping test-run tests")


class TestTestRunEndpoint:
    def test_test_run_owner_ok(self, admin_headers, project_with_nodes):
        pid = project_with_nodes["id"]
        r = requests.post(
            f"{BASE_URL}/api/armory/bot-projects/{pid}/test-run",
            headers=admin_headers,
            timeout=60,
        )
        # Acceptable: 200 success/failure body, or compute-gate dict
        assert r.status_code in (200, 400, 402)
        d = r.json()
        # If allowed:false, that's the gate
        if isinstance(d, dict) and d.get("allowed") is False:
            return
        # Else expect contract keys
        assert "success" in d
        assert "duration_ms" in d
        assert "run_id" in d
        assert "node_results" in d

    def test_test_run_not_owner_or_missing(self, admin_headers):
        fake_id = uuid.uuid4().hex
        r = requests.post(
            f"{BASE_URL}/api/armory/bot-projects/{fake_id}/test-run",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 404

    def test_test_run_unauthenticated(self):
        r = requests.post(f"{BASE_URL}/api/armory/bot-projects/anyid/test-run", timeout=10)
        assert r.status_code in (401, 403)


# ─── Empty-nodes 400 path ───────────────────────────────
class TestTestRunEmptyNodes:
    def test_empty_nodes_returns_400(self, admin_headers):
        """Create a project via build-bot is expensive; instead, hit the endpoint with a
        synthetically-empty project if user has one. Skip if none exist."""
        r = requests.get(f"{BASE_URL}/api/armory/bot-projects", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        projects = r.json().get("projects", [])
        empty = next((p for p in projects if not p.get("nodes")), None)
        if not empty:
            pytest.skip("No empty-node project available — 400 path not directly testable without seeding")
        r2 = requests.post(
            f"{BASE_URL}/api/armory/bot-projects/{empty['id']}/test-run",
            headers=admin_headers,
            timeout=15,
        )
        assert r2.status_code == 400
