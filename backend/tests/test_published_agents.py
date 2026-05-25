"""
Backend tests for Published Agents API + Creator Analytics
Endpoints under test:
  POST   /api/published-agents/publish
  GET    /api/published-agents
  GET    /api/published-agents/{id}
  PUT    /api/published-agents/{id}
  DELETE /api/published-agents/{id}
  GET    /api/creator/analytics
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dark-mode-nova.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"


# ── Fixtures ──
@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sample_manifest():
    return {
        "nodes": [
            {"id": "n1", "type": "trigger", "label": "TEST start"},
            {"id": "n2", "type": "action", "label": "TEST run"},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }


# Track created IDs so we can cleanup
_created_ids = []


# ── Auth Guard ──
class TestAuthGuard:
    def test_publish_requires_auth(self, sample_manifest):
        r = requests.post(f"{BASE_URL}/api/published-agents/publish",
                          json={"name": "TEST_NoAuth", "manifest": sample_manifest},
                          timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/published-agents", timeout=10)
        assert r.status_code in (401, 403)

    def test_analytics_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/creator/analytics", timeout=10)
        assert r.status_code in (401, 403)


# ── CRUD Flow ──
class TestPublishedAgentsCRUD:
    def test_01_publish_creates_agent(self, headers, sample_manifest):
        payload = {
            "name": "TEST_Agent_CRUD",
            "description": "Test agent created by backend_test",
            "manifest": sample_manifest,
            "trust_score": 85,
            "linter_status": "pass",
        }
        r = requests.post(f"{BASE_URL}/api/published-agents/publish",
                          headers=headers, json=payload, timeout=15)
        assert r.status_code == 200, f"Publish failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("version") == 1
        assert "agent_id" in data
        _created_ids.append(data["agent_id"])

    def test_02_list_includes_created(self, headers):
        assert _created_ids, "No agent created in step 1"
        r = requests.get(f"{BASE_URL}/api/published-agents", headers=headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "agents" in body
        ids = [a["agent_id"] for a in body["agents"]]
        assert _created_ids[0] in ids

    def test_03_get_single_returns_full_with_history(self, headers):
        aid = _created_ids[0]
        r = requests.get(f"{BASE_URL}/api/published-agents/{aid}",
                         headers=headers, timeout=15)
        assert r.status_code == 200
        agent = r.json()
        assert agent["agent_id"] == aid
        assert agent["version"] == 1
        assert agent["status"] == "published"
        assert isinstance(agent.get("version_history"), list)
        assert len(agent["version_history"]) == 1
        assert agent["version_history"][0]["version"] == 1
        assert agent["version_history"][0]["node_count"] == 2
        assert agent["version_history"][0]["edge_count"] == 1
        assert "manifest" in agent

    def test_04_put_name_only_does_not_bump_version(self, headers):
        aid = _created_ids[0]
        r = requests.put(f"{BASE_URL}/api/published-agents/{aid}",
                         headers=headers,
                         json={"name": "TEST_Agent_CRUD_Renamed"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("version") == 1, f"Version bumped unexpectedly: {data}"

        # Verify persistence
        g = requests.get(f"{BASE_URL}/api/published-agents/{aid}",
                        headers=headers, timeout=15)
        assert g.status_code == 200
        agent = g.json()
        assert agent["name"] == "TEST_Agent_CRUD_Renamed"
        assert agent["version"] == 1
        assert len(agent["version_history"]) == 1

    def test_05_put_manifest_bumps_version_and_appends_history(self, headers):
        aid = _created_ids[0]
        new_manifest = {
            "nodes": [
                {"id": "n1", "type": "trigger", "label": "v2"},
                {"id": "n2", "type": "action", "label": "v2"},
                {"id": "n3", "type": "output", "label": "v2"},
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
        }
        r = requests.put(f"{BASE_URL}/api/published-agents/{aid}",
                         headers=headers,
                         json={"manifest": new_manifest}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("version") == 2

        # Verify persistence
        g = requests.get(f"{BASE_URL}/api/published-agents/{aid}",
                        headers=headers, timeout=15)
        agent = g.json()
        assert agent["version"] == 2
        assert len(agent["version_history"]) == 2
        latest = agent["version_history"][-1]
        assert latest["version"] == 2
        assert latest["node_count"] == 3
        assert latest["edge_count"] == 2

    def test_06_creator_analytics(self, headers):
        r = requests.get(f"{BASE_URL}/api/creator/analytics", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        for key in ("total_agents", "published", "drafts", "total_executions",
                    "avg_trust_score", "total_versions", "agents"):
            assert key in data, f"Missing key '{key}' in analytics response"
        assert isinstance(data["agents"], list)
        assert data["total_agents"] >= 1
        # Our test agent (v2) should contribute to total_versions
        assert data["total_versions"] >= 2

    def test_07_get_nonexistent_returns_404(self, headers):
        r = requests.get(f"{BASE_URL}/api/published-agents/does-not-exist-uuid",
                         headers=headers, timeout=10)
        assert r.status_code == 404

    def test_08_delete_agent(self, headers):
        aid = _created_ids[0]
        r = requests.delete(f"{BASE_URL}/api/published-agents/{aid}",
                            headers=headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("success") is True

        # Verify deletion
        g = requests.get(f"{BASE_URL}/api/published-agents/{aid}",
                        headers=headers, timeout=10)
        assert g.status_code == 404

    def test_09_delete_again_returns_404(self, headers):
        aid = _created_ids[0]
        r = requests.delete(f"{BASE_URL}/api/published-agents/{aid}",
                            headers=headers, timeout=10)
        assert r.status_code == 404
