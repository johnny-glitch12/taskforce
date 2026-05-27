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


# ────────────────────────── 9. SAVE endpoint ──────────────────────────
class TestSaveEndpoint:
    def test_save_creates_runtime_workflow(self, base_url, admin_client):
        studio_id = f"TEST_studio_{uuid.uuid4().hex[:8]}"
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": 1}},
            {"id": "x1", "type": "transform", "data": {"code": "RESULT = INPUT + 1"}},
        ]
        edges = [{"from": "t1", "to": "x1"}]
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={
                "studio_workflow_id": studio_id,
                "name": "TEST_save_basic",
                "nodes": nodes,
                "edges": edges,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True
        assert "workflow_id" in data
        wf_id = data["workflow_id"]

        # Verify persisted via GET
        g = admin_client.get(f"{base_url}/api/workflows/{wf_id}")
        assert g.status_code == 200, g.text
        wf = g.json()
        assert wf["name"] == "TEST_save_basic"
        assert wf.get("studio_workflow_id") == studio_id
        assert len(wf["nodes"]) == 2
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_save_idempotent_same_studio_id(self, base_url, admin_client):
        studio_id = f"TEST_studio_{uuid.uuid4().hex[:8]}"
        body = {
            "studio_workflow_id": studio_id,
            "name": "TEST_idempotent_v1",
            "nodes": [{"id": "t1", "type": "trigger"}],
            "edges": [],
        }
        r1 = admin_client.post(f"{base_url}/api/workflows/save", json=body)
        assert r1.status_code == 200
        wf_id1 = r1.json()["workflow_id"]

        # Re-save with same studio_id, different name/nodes — must return same id
        body2 = {
            "studio_workflow_id": studio_id,
            "name": "TEST_idempotent_v2",
            "nodes": [
                {"id": "t1", "type": "trigger"},
                {"id": "x1", "type": "transform", "data": {"code": "RESULT=INPUT"}},
            ],
            "edges": [{"from": "t1", "to": "x1"}],
        }
        r2 = admin_client.post(f"{base_url}/api/workflows/save", json=body2)
        assert r2.status_code == 200
        wf_id2 = r2.json()["workflow_id"]
        assert wf_id1 == wf_id2, "upsert should return same workflow_id"

        # Verify content updated
        g = admin_client.get(f"{base_url}/api/workflows/{wf_id1}")
        assert g.json()["name"] == "TEST_idempotent_v2"
        assert len(g.json()["nodes"]) == 2
        admin_client.delete(f"{base_url}/api/workflows/{wf_id1}")

    def test_save_over_50_nodes_rejected(self, base_url, admin_client):
        nodes = [{"id": f"n{i}", "type": "trigger"} for i in range(51)]
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={
                "studio_workflow_id": f"TEST_oversize_{uuid.uuid4().hex[:6]}",
                "name": "TEST_oversize",
                "nodes": nodes,
                "edges": [],
            },
        )
        assert r.status_code == 400, r.text
        assert "exceed" in r.text.lower()

    def test_save_non_list_nodes_rejected(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={
                "studio_workflow_id": f"TEST_badtype_{uuid.uuid4().hex[:6]}",
                "name": "TEST_badtype",
                "nodes": "not-a-list",
                "edges": [],
            },
        )
        # iter29: now Pydantic returns 422 instead of 400
        assert r.status_code in (400, 422), r.text
        body = r.text.lower()
        assert "must be arrays" in body or "list_type" in body or "list" in body

    def test_save_empty_workflow_allowed_then_execute_no_keyerror(
        self, base_url, admin_client
    ):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={
                "studio_workflow_id": f"TEST_empty_{uuid.uuid4().hex[:6]}",
                "name": "TEST_empty",
                "nodes": [],
                "edges": [],
            },
        )
        assert r.status_code == 200, r.text
        wf_id = r.json()["workflow_id"]

        # Execute empty — must NOT raise KeyError; success:False, duration_ms present
        ex = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert ex.status_code == 200, ex.text
        data = ex.json()
        assert data["success"] is False
        assert "duration_ms" in data
        assert data["duration_ms"] == 0
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_save_isolation_between_users(
        self, base_url, admin_client, freeuser_client
    ):
        """User A's save must not appear in User B's workflows."""
        studio_id = f"TEST_iso_{uuid.uuid4().hex[:8]}"
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={
                "studio_workflow_id": studio_id,
                "name": "TEST_iso_adminonly",
                "nodes": [{"id": "t1", "type": "trigger"}],
                "edges": [],
            },
        )
        assert r.status_code == 200
        wf_id = r.json()["workflow_id"]

        # Freeuser must not see it
        g = freeuser_client.get(f"{base_url}/api/workflows/{wf_id}")
        assert g.status_code == 404, "isolation broken — freeuser saw admin's wf"
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_save_requires_auth(self, base_url):
        r = requests.post(
            f"{base_url}/api/workflows/save",
            json={"studio_workflow_id": "x", "name": "x", "nodes": [], "edges": []},
            timeout=15,
        )
        assert r.status_code in (401, 403), r.text


# ────────────────────────── 10. PATCH node data endpoint ──────────────────────────
class TestPatchNodeData:
    def _save(self, base_url, admin_client, nodes, edges, name="TEST_patch"):
        body = {
            "studio_workflow_id": f"TEST_pa_{uuid.uuid4().hex[:8]}",
            "name": name,
            "nodes": nodes,
            "edges": edges,
        }
        r = admin_client.post(f"{base_url}/api/workflows/save", json=body)
        assert r.status_code == 200, r.text
        return r.json()["workflow_id"]

    def test_patch_updates_only_target_node(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": 1}},
            {"id": "x1", "type": "transform", "data": {"code": "RESULT = INPUT * 2",
                                                       "label": "Doubler"}},
            {"id": "x2", "type": "transform", "data": {"code": "RESULT = INPUT + 7"}},
        ]
        edges = [{"from": "t1", "to": "x1"}, {"from": "x1", "to": "x2"}]
        wf_id = self._save(base_url, admin_client, nodes, edges)

        r = admin_client.patch(
            f"{base_url}/api/workflows/{wf_id}/nodes/x1",
            json={"data": {"code": "RESULT = INPUT * 3"}},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["node_id"] == "x1"
        # MERGED dict — existing 'label' preserved, code overwritten
        assert body["data"]["code"] == "RESULT = INPUT * 3"
        assert body["data"]["label"] == "Doubler"

        # Verify other node untouched
        g = admin_client.get(f"{base_url}/api/workflows/{wf_id}").json()
        x2 = next(n for n in g["nodes"] if n["id"] == "x2")
        assert x2["data"]["code"] == "RESULT = INPUT + 7"

        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_patch_wrong_workflow_returns_404(
        self, base_url, admin_client, freeuser_client
    ):
        # admin creates wf; freeuser tries to patch — should 404 (ownership)
        nodes = [{"id": "t1", "type": "trigger"}]
        wf_id = self._save(base_url, admin_client, nodes, [])
        r = freeuser_client.patch(
            f"{base_url}/api/workflows/{wf_id}/nodes/t1",
            json={"data": {"foo": "bar"}},
        )
        assert r.status_code == 404, r.text
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_patch_nonexistent_node_returns_404(self, base_url, admin_client):
        nodes = [{"id": "t1", "type": "trigger"}]
        wf_id = self._save(base_url, admin_client, nodes, [])
        r = admin_client.patch(
            f"{base_url}/api/workflows/{wf_id}/nodes/ghost_node",
            json={"data": {"foo": "bar"}},
        )
        assert r.status_code == 404, r.text
        assert "node" in r.text.lower()
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_full_loop_save_patch_execute(self, base_url, admin_client):
        """SAVE with INPUT*2 → PATCH to INPUT*3 → EXECUTE with 5 → expect 15."""
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": 5}},
            {"id": "x1", "type": "transform", "data": {"code": "RESULT = INPUT * 2"}},
        ]
        edges = [{"from": "t1", "to": "x1"}]
        wf_id = self._save(
            base_url, admin_client, nodes, edges, name="TEST_full_loop"
        )

        # PATCH transform code
        p = admin_client.patch(
            f"{base_url}/api/workflows/{wf_id}/nodes/x1",
            json={"data": {"code": "RESULT = INPUT * 3"}},
        )
        assert p.status_code == 200, p.text
        assert p.json()["data"]["code"] == "RESULT = INPUT * 3"

        # EXECUTE
        ex = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert ex.status_code == 200, ex.text
        data = ex.json()
        assert data["success"] is True, data
        assert data["final_output"] == 15, (
            f"Expected PATCHed code (*3) to run; got {data['final_output']}"
        )
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")
