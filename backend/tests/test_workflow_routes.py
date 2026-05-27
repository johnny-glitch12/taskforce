"""
Integration tests for native Python workflow executor routes (/api/workflows/*).
Covers templates catalog, fork, CRUD, execution (DAG, SSRF, condition, transform),
compute-credit gating, cycle detection, isolation, and template-direct execution.
"""
import os
import time
import uuid
import json
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient


# ────────────────────────── Helpers / seeding ──────────────────────────
def _mongo():
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=4000)
    return client[os.environ["DB_NAME"]]


def _seed_freeuser_at_limit():
    """Force freeuser@test.com to be at 100/100 compute usage for current period."""
    db = _mongo()
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    user = db.users.find_one({"email": "freeuser@test.com"})
    if not user:
        return None
    uid = user.get("id", user.get("email"))
    # Ensure tier is 'recruit' or 'free' (limited)
    db.users.update_one({"email": "freeuser@test.com"}, {"$set": {"tier": "recruit"}})
    db.compute_usage.update_one(
        {"user_id": uid, "period": period},
        {"$set": {"user_id": uid, "period": period, "count": 100,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return uid


@pytest.fixture(scope="session", autouse=True)
def seed_freeuser():
    _seed_freeuser_at_limit()
    yield


# ────────────────────────── 1. engine status ──────────────────────────
class TestEngineStatus:
    def test_engine_status_requires_auth(self, base_url):
        r = requests.get(f"{base_url}/api/workflows/engine/status", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_engine_status_admin(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/engine/status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["engine"] == "native-python"
        assert isinstance(data["templates_available"], int)
        assert data["templates_available"] >= 1
        assert isinstance(data["supported_node_types"], list)
        for t in ["trigger", "http_request", "condition", "transform",
                  "llm", "webhook"]:
            assert t in data["supported_node_types"], f"missing {t}"


# ────────────────────────── 2. templates catalog ──────────────────────────
class TestTemplates:
    def test_list_templates(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/templates")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "templates" in data and isinstance(data["templates"], list)
        assert data["count"] >= 1, "Expected ingested templates"
        sample = data["templates"][0]
        for key in ("name", "category", "node_count", "complexity", "source_hash"):
            assert key in sample, f"template missing key: {key}; sample={sample}"

    def test_list_templates_category_filter(self, base_url, admin_client):
        # Find an existing category from the catalog first
        all_r = admin_client.get(f"{base_url}/api/workflows/templates").json()
        cats = {t["category"] for t in all_r["templates"] if t.get("category")}
        if not cats:
            pytest.skip("No categories available")
        # Prefer devops if exists, else first
        chosen = "devops" if "devops" in cats else next(iter(cats))
        r = admin_client.get(
            f"{base_url}/api/workflows/templates", params={"category": chosen}
        )
        assert r.status_code == 200
        out = r.json()
        if out["count"] > 0:
            assert all(t["category"] == chosen for t in out["templates"])

    def test_get_single_template(self, base_url, admin_client):
        listing = admin_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        r = admin_client.get(f"{base_url}/api/workflows/templates/{tid}")
        assert r.status_code == 200, r.text
        tpl = r.json()
        assert isinstance(tpl.get("nodes"), list)
        assert isinstance(tpl.get("edges"), list)
        assert tpl["source_hash"] == tid

    def test_get_template_404(self, base_url, admin_client):
        r = admin_client.get(
            f"{base_url}/api/workflows/templates/nonexistent_{uuid.uuid4().hex}"
        )
        assert r.status_code == 404, r.text


# ────────────────────────── 3. Fork & user CRUD ──────────────────────────
class TestForkAndCRUD:
    @pytest.fixture(scope="class")
    def forked_workflow_id(self, base_url, admin_client):
        listing = admin_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        r = admin_client.post(f"{base_url}/api/workflows/templates/{tid}/fork")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True
        wf = data["workflow"]
        assert "id" in wf
        assert wf["source_template"] == tid
        assert isinstance(wf["nodes"], list)
        assert isinstance(wf["edges"], list)
        return wf["id"]

    def test_list_user_workflows_includes_fork(
        self, base_url, admin_client, forked_workflow_id
    ):
        r = admin_client.get(f"{base_url}/api/workflows")
        assert r.status_code == 200
        wfs = r.json()["workflows"]
        ids = [w["id"] for w in wfs]
        assert forked_workflow_id in ids

    def test_get_own_workflow(self, base_url, admin_client, forked_workflow_id):
        r = admin_client.get(f"{base_url}/api/workflows/{forked_workflow_id}")
        assert r.status_code == 200
        assert r.json()["id"] == forked_workflow_id

    def test_isolation_other_user_cannot_see(
        self, base_url, freeuser_client, forked_workflow_id
    ):
        r = freeuser_client.get(f"{base_url}/api/workflows/{forked_workflow_id}")
        assert r.status_code == 404, "isolation broken"

    def test_isolation_other_user_cannot_delete(
        self, base_url, freeuser_client, forked_workflow_id
    ):
        r = freeuser_client.delete(f"{base_url}/api/workflows/{forked_workflow_id}")
        assert r.status_code == 404

    def test_delete_own_workflow(self, base_url, admin_client, forked_workflow_id):
        r = admin_client.delete(f"{base_url}/api/workflows/{forked_workflow_id}")
        assert r.status_code == 200
        # confirm gone
        g = admin_client.get(f"{base_url}/api/workflows/{forked_workflow_id}")
        assert g.status_code == 404


# ────────────────────────── 4. Synthetic execution ──────────────────────────
def _create_synthetic_workflow(admin_client, base_url, nodes, edges, name):
    """Insert a workflow directly via MongoDB (no public CRUD create route)."""
    db = _mongo()
    me = admin_client.get(f"{base_url}/api/auth/me").json()
    wf_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.user_workflows.insert_one({
        "id": wf_id, "user_id": me["id"], "name": name,
        "nodes": nodes, "edges": edges,
        "created_at": now, "updated_at": now,
    })
    return wf_id, me["id"]


class TestExecution:
    def test_execute_transform_double(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": 5}},
            {"id": "x1", "type": "transform", "data": {"code": "RESULT = INPUT * 2"}},
        ]
        edges = [{"from": "t1", "to": "x1"}]
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_transform_double"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True, data
        assert data["final_output"] == 10, data
        assert "run_id" in data
        assert len(data["node_results"]) == 2
        # cleanup
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_execute_condition_branch(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": {"score": 80}}},
            {"id": "c1", "type": "condition",
             "data": {"condition": "INPUT.get('score', 0) > 50"}},
        ]
        edges = [{"from": "t1", "to": "c1"}]
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_condition"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        cond_results = [n for n in data["node_results"] if n["type"] == "condition"]
        assert cond_results, "no condition node result"
        assert cond_results[0]["branch"] == "true"
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_execute_ssrf_blocked(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger"},
            {"id": "h1", "type": "http_request",
             "data": {"url": "http://localhost:22", "method": "GET"}},
        ]
        edges = [{"from": "t1", "to": "h1"}]
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_ssrf"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        http_node = [n for n in data["node_results"] if n["type"] == "http_request"][0]
        assert http_node["status"] == "error"
        assert ("ssrf" in (http_node.get("log") or "").lower()
                or "blocked" in (http_node.get("log") or "").lower())
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_execute_http_external(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger"},
            {"id": "h1", "type": "http_request",
             "data": {"url": "https://httpbin.org/get", "method": "GET"}},
        ]
        edges = [{"from": "t1", "to": "h1"}]
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_http_external"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        http_node = [n for n in data["node_results"] if n["type"] == "http_request"][0]
        # Should succeed or at worst time out — accept "ok" preferred
        assert http_node["status"] in ("ok", "error")
        if http_node["status"] != "ok":
            pytest.skip(f"httpbin.org unreachable: {http_node.get('log')}")
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_run_persisted_in_db(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": 1}},
            {"id": "x1", "type": "transform", "data": {"code": "RESULT = INPUT + 1"}},
        ]
        edges = [{"from": "t1", "to": "x1"}]
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_persistence"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        run_id = r.json()["run_id"]
        db = _mongo()
        doc = db.workflow_runs.find_one({"id": run_id})
        assert doc is not None
        assert doc["workflow_id"] == wf_id
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ────────────────────────── 5. Guardrails ──────────────────────────
class TestGuardrails:
    def test_cycle_rejected(self, base_url, admin_client):
        nodes = [
            {"id": "a", "type": "trigger"},
            {"id": "b", "type": "transform", "data": {"code": "RESULT=INPUT"}},
        ]
        edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_cycle"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 400, r.text
        assert "cycle" in r.text.lower()
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_over_50_nodes_rejected(self, base_url, admin_client):
        nodes = [{"id": f"n{i}", "type": "trigger"} for i in range(51)]
        edges = []
        wf_id, _ = _create_synthetic_workflow(
            admin_client, base_url, nodes, edges, "TEST_too_big"
        )
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text  # body says success=False
        data = r.json()
        assert data["success"] is False
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ────────────────────────── 6. Compute credits ──────────────────────────
class TestComputeGate:
    def test_freeuser_at_limit_gated(self, base_url, admin_client, freeuser_client):
        """freeuser is at 100/100 — execute should return allowed:false body."""
        # Admin creates a workflow then assigns to freeuser via mongo (simulating
        # freeuser owns workflow). Easiest path: have freeuser fork a template.
        listing = freeuser_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        fork = freeuser_client.post(f"{base_url}/api/workflows/templates/{tid}/fork")
        assert fork.status_code == 200, fork.text
        wf_id = fork.json()["workflow"]["id"]

        r = freeuser_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("allowed") is False, body
        assert body.get("error") == "COMPUTE_LIMIT_REACHED"
        freeuser_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_freeuser_template_execute_gated(self, base_url, freeuser_client):
        listing = freeuser_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        r = freeuser_client.post(
            f"{base_url}/api/workflows/templates/{tid}/execute"
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("allowed") is False
        assert body.get("error") == "COMPUTE_LIMIT_REACHED"


# ────────────────────────── 7. Direct template execution (admin) ──────────────────────────
class TestTemplateDirectExecute:
    def test_admin_can_execute_template(self, base_url, admin_client):
        listing = admin_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        r = admin_client.post(f"{base_url}/api/workflows/templates/{tid}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        # Should NOT be compute-gated (admin) — must have node_results
        assert "node_results" in data, data
        assert isinstance(data["node_results"], list)


# ────────────────────────── 8. n8n proxy removal ──────────────────────────
class TestN8nProxyRemoved:
    def test_n8n_status_route_gone(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/n8n/status")
        assert r.status_code == 404
