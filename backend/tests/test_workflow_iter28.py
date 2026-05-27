"""
Iteration 28 — NEW coverage for BYOK credentials, deep-merge PATCH,
async dispatch, /runs endpoint, route-ordering precedence, refactored
auth routes, and engine v1.1.0 status changes.
"""
import os
import uuid
import time
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient


def _mongo():
    return MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=4000)[os.environ["DB_NAME"]]


def _seed_freeuser_at_limit():
    db = _mongo()
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    user = db.users.find_one({"email": "freeuser@test.com"})
    if not user:
        return
    uid = user.get("id", user.get("email"))
    db.users.update_one({"email": "freeuser@test.com"}, {"$set": {"tier": "recruit"}})
    db.compute_usage.update_one(
        {"user_id": uid, "period": period},
        {"$set": {"user_id": uid, "period": period, "count": 100,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


@pytest.fixture(scope="session", autouse=True)
def seed_freeuser():
    _seed_freeuser_at_limit()
    yield


def _save_wf(client, base_url, nodes, edges, name="TEST_iter28"):
    studio_id = f"TEST_i28_{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{base_url}/api/workflows/save",
        json={"studio_workflow_id": studio_id, "name": name,
              "nodes": nodes, "edges": edges},
    )
    assert r.status_code == 200, r.text
    return r.json()["workflow_id"]


# ───────────────────────── 1. BYOK Credentials ─────────────────────────
class TestBYOKCredentials:
    @pytest.fixture(autouse=True)
    def _clean(self, base_url, admin_client, freeuser_client):
        # Wipe any stale creds for these users before each test
        db = _mongo()
        for client in (admin_client, freeuser_client):
            me = client.get(f"{base_url}/api/auth/me").json()
            uid = str(me.get("id", me.get("email")))
            db.byok_credentials.delete_many({"user_id": uid})
        yield
        for client in (admin_client, freeuser_client):
            me = client.get(f"{base_url}/api/auth/me").json()
            uid = str(me.get("id", me.get("email")))
            db.byok_credentials.delete_many({"user_id": uid})

    def test_list_credentials_empty_with_supported_services(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["credentials"] == []
        assert set(d["supported_services"]) == {"slack", "sendgrid", "gmail"}

    def test_save_credential_success(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "https://hooks.slack.com/services/AAA/BBB/CCC", "extra": {}},
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
        assert r.json()["service"] == "slack"

    def test_save_credential_is_idempotent(self, base_url, admin_client):
        body = {"service": "sendgrid", "api_key": "SG.firstkey", "extra": {"from_email": "x@y.com"}}
        r1 = admin_client.post(f"{base_url}/api/workflows/credentials", json=body)
        assert r1.status_code == 200
        body["api_key"] = "SG.secondkey"
        r2 = admin_client.post(f"{base_url}/api/workflows/credentials", json=body)
        assert r2.status_code == 200
        # Exactly one document persisted
        db = _mongo()
        me = admin_client.get(f"{base_url}/api/auth/me").json()
        uid = str(me.get("id", me.get("email")))
        docs = list(db.byok_credentials.find({"user_id": uid, "service": "sendgrid"}))
        assert len(docs) == 1
        assert docs[0]["api_key"] == "SG.secondkey"

    def test_save_credential_bogus_service_400(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "bogus", "api_key": "x", "extra": {}},
        )
        assert r.status_code == 400, r.text
        assert "not supported" in r.text.lower()

    def test_save_credential_empty_api_key_400(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "", "extra": {}},
        )
        assert r.status_code == 400, r.text
        assert "api_key is required" in r.text.lower()

    def test_save_credential_extra_not_dict_400(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "https://hooks.slack.com/x", "extra": "nope"},
        )
        assert r.status_code == 400, r.text
        assert "must be an object" in r.text.lower()

    def test_list_credentials_masks_api_key(self, base_url, admin_client):
        admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "gmail", "api_key": "ya29.SECRETACCESSTOKEN1234", "extra": {}},
        )
        r = admin_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200
        creds = r.json()["credentials"]
        assert len(creds) == 1
        # No plaintext key
        assert "api_key" not in creds[0]
        assert "api_key_masked" in creds[0]
        assert "SECRETACCESSTOKEN" not in creds[0]["api_key_masked"]
        # Last 4 chars shown
        assert creds[0]["api_key_masked"].endswith("1234")

    def test_delete_credential_then_404(self, base_url, admin_client):
        admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "https://hooks.slack.com/services/X", "extra": {}},
        )
        d1 = admin_client.delete(f"{base_url}/api/workflows/credentials/slack")
        assert d1.status_code == 200, d1.text
        d2 = admin_client.delete(f"{base_url}/api/workflows/credentials/slack")
        assert d2.status_code == 404

    def test_byok_isolation_between_users(self, base_url, admin_client, freeuser_client):
        admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "https://hooks.slack.com/services/ADMINONLY", "extra": {}},
        )
        r = freeuser_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200
        assert r.json()["credentials"] == [], "isolation broken — freeuser saw admin's creds"


# ───────────────────────── 2. Deep-merge PATCH ─────────────────────────
class TestDeepMergePatch:
    def test_patch_preserves_sibling_headers(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger"},
            {"id": "h1", "type": "http_request",
             "data": {"url": "https://example.com", "method": "GET",
                      "headers": {"Authorization": "A", "X-Other": "B"}}},
        ]
        wf_id = _save_wf(admin_client, base_url, nodes, [{"from": "t1", "to": "h1"}])

        r = admin_client.patch(
            f"{base_url}/api/workflows/{wf_id}/nodes/h1",
            json={"data": {"headers": {"Authorization": "C"}}},
        )
        assert r.status_code == 200, r.text
        merged = r.json()["data"]["headers"]
        assert merged.get("Authorization") == "C"
        assert merged.get("X-Other") == "B", f"sibling key wiped — got {merged}"
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_patch_oversize_50kb_rejected(self, base_url, admin_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger"}], [])
        big = {"data": {"code": "x" * 60_000}}
        r = admin_client.patch(f"{base_url}/api/workflows/{wf_id}/nodes/t1", json=big)
        assert r.status_code == 400, r.text
        assert "50kb" in r.text.lower() or "exceed" in r.text.lower()
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ───────────────────────── 3. Save validation ─────────────────────────
class TestSaveValidation:
    def test_save_missing_studio_id_400(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"name": "x", "nodes": [], "edges": []},
        )
        assert r.status_code == 400, r.text
        assert "studio_workflow_id is required" in r.text.lower()

    def test_save_whitespace_studio_id_400(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"studio_workflow_id": "   ", "name": "x", "nodes": [], "edges": []},
        )
        assert r.status_code == 400, r.text


# ───────────────────────── 4. Action node dispatch ─────────────────────────
class TestActionNodeDispatch:
    def test_action_slack_without_byok_returns_error(self, base_url, admin_client):
        # Ensure no slack BYOK for admin
        db = _mongo()
        me = admin_client.get(f"{base_url}/api/auth/me").json()
        uid = str(me.get("id", me.get("email")))
        db.byok_credentials.delete_many({"user_id": uid, "service": "slack"})

        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": {"msg": "hi"}}},
            {"id": "a1", "type": "action", "data": {"service": "slack", "text": "Hello"}},
        ]
        edges = [{"from": "t1", "to": "a1"}]
        wf_id = _save_wf(admin_client, base_url, nodes, edges)
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        a_node = next(n for n in data["node_results"] if n["node_id"] == "a1")
        assert a_node["status"] == "error"
        assert "slack byok not configured" in (a_node.get("log") or "").lower()
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_action_unknown_service_skipped(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger"},
            {"id": "a1", "type": "action", "data": {"service": "foobar"}},
        ]
        edges = [{"from": "t1", "to": "a1"}]
        wf_id = _save_wf(admin_client, base_url, nodes, edges)
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        assert r.status_code == 200, r.text
        a_node = next(n for n in r.json()["node_results"] if n["node_id"] == "a1")
        assert a_node["status"] == "skipped", a_node
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ───────────────────────── 5. Async dispatch ─────────────────────────
class TestAsyncDispatch:
    def test_dispatch_returns_job_id_queued(self, base_url, admin_client):
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": 4}},
            {"id": "x1", "type": "transform", "data": {"code": "RESULT = INPUT * 2"}},
        ]
        wf_id = _save_wf(admin_client, base_url, nodes, [{"from": "t1", "to": "x1"}])
        r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/dispatch")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "queued"
        # poll
        job_id = body["job_id"]
        final = None
        for _ in range(20):  # up to 10s
            time.sleep(0.5)
            jr = admin_client.get(f"{base_url}/api/workflows/jobs/{job_id}")
            assert jr.status_code == 200, jr.text
            jd = jr.json()
            if jd["status"] in ("succeeded", "failed"):
                final = jd
                break
        assert final is not None, "Job did not finish within 10s"
        assert final["status"] == "succeeded", final
        assert final["result"]["final_output"] == 8
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_dispatch_nonexistent_workflow_404(self, base_url, admin_client):
        r = admin_client.post(f"{base_url}/api/workflows/nonexistent_{uuid.uuid4().hex}/dispatch")
        assert r.status_code == 404, r.text

    def test_dispatch_other_user_job_404(self, base_url, admin_client, freeuser_client):
        # admin dispatches a job, freeuser tries to fetch
        nodes = [{"id": "t1", "type": "trigger"},
                 {"id": "x1", "type": "transform", "data": {"code": "RESULT=INPUT"}}]
        wf_id = _save_wf(admin_client, base_url, nodes, [{"from": "t1", "to": "x1"}])
        d = admin_client.post(f"{base_url}/api/workflows/{wf_id}/dispatch")
        assert d.status_code == 200, d.text
        job_id = d.json()["job_id"]
        r = freeuser_client.get(f"{base_url}/api/workflows/jobs/{job_id}")
        assert r.status_code == 404, r.text
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_dispatch_compute_limit_freeuser(self, base_url, freeuser_client):
        # freeuser is at limit; fork a template and dispatch
        listing = freeuser_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        fork = freeuser_client.post(f"{base_url}/api/workflows/templates/{tid}/fork")
        assert fork.status_code == 200, fork.text
        wf_id = fork.json()["workflow"]["id"]
        r = freeuser_client.post(f"{base_url}/api/workflows/{wf_id}/dispatch")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("allowed") is False
        assert body.get("error") == "COMPUTE_LIMIT_REACHED"
        freeuser_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ───────────────────────── 6. Template execute logs run_id ─────────────────────────
class TestTemplateExecuteLogsRun:
    def test_template_execute_returns_run_id_persisted(self, base_url, admin_client):
        listing = admin_client.get(f"{base_url}/api/workflows/templates").json()
        tid = listing["templates"][0]["source_hash"]
        r = admin_client.post(f"{base_url}/api/workflows/templates/{tid}/execute")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "run_id" in data, data
        run_id = data["run_id"]
        db = _mongo()
        doc = db.workflow_runs.find_one({"id": run_id})
        assert doc is not None
        assert doc["source"] == "template"


# ───────────────────────── 7. /runs endpoint ─────────────────────────
class TestRunsEndpoint:
    def test_list_runs_for_own_workflow(self, base_url, admin_client):
        nodes = [{"id": "t1", "type": "trigger", "data": {"payload": 1}},
                 {"id": "x1", "type": "transform", "data": {"code": "RESULT=INPUT+1"}}]
        wf_id = _save_wf(admin_client, base_url, nodes, [{"from": "t1", "to": "x1"}])
        # execute twice
        admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        r = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs")
        assert r.status_code == 200, r.text
        runs = r.json()["runs"]
        assert len(runs) >= 2
        for run in runs:
            assert run["workflow_id"] == wf_id
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_list_runs_other_user_404(self, base_url, admin_client, freeuser_client):
        nodes = [{"id": "t1", "type": "trigger"}]
        wf_id = _save_wf(admin_client, base_url, nodes, [])
        r = freeuser_client.get(f"{base_url}/api/workflows/{wf_id}/runs")
        assert r.status_code == 404, r.text
        admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ───────────────────────── 8. Auth routes still work ─────────────────────────
class TestAuthRoutesExtracted:
    def test_login(self, base_url):
        r = requests.post(f"{base_url}/api/auth/login",
                          json={"email": "admin@nova.ai", "password": "admin123"},
                          timeout=15)
        assert r.status_code == 200, r.text
        assert "token" in r.json()

    def test_me(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "admin@nova.ai"

    def test_register_new(self, base_url):
        email = f"TEST_iter28_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{base_url}/api/auth/register",
                          json={"email": email, "password": "Pw_testing12345!", "name": "T"},
                          timeout=15)
        assert r.status_code in (200, 201), r.text
        # Cleanup
        _mongo().users.delete_one({"email": email})

    def test_forgot_password(self, base_url):
        r = requests.post(f"{base_url}/api/auth/forgot-password",
                          json={"email": "admin@nova.ai"}, timeout=15)
        # Endpoint should not fail even if email send is mocked
        assert r.status_code in (200, 202), r.text

    def test_reset_password_invalid_token(self, base_url):
        r = requests.post(f"{base_url}/api/auth/reset-password",
                          json={"token": "definitely-not-a-real-token", "new_password": "Whatever123!"},
                          timeout=15)
        # Should fail with 400/404 — proving route is wired
        assert r.status_code in (400, 401, 404), r.text


# ───────────────────────── 9. Engine v1.1 status ─────────────────────────
class TestEngineV1_1:
    def test_engine_status_v1_1(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/engine/status")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("version") == "1.1.0", d
        assert d.get("async_dispatch") is True
        assert set(d.get("byok_services", [])) == {"slack", "sendgrid", "gmail"}


# ───────────────────────── 10. Route ordering precedence ─────────────────────────
class TestRouteOrdering:
    def test_credentials_route_not_swallowed(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200, r.text
        assert "supported_services" in r.json()

    def test_engine_status_route_not_swallowed(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/engine/status")
        assert r.status_code == 200, r.text
        assert r.json().get("engine") == "native-python"

    def test_jobs_nonexistent_returns_404_not_workflow_not_found(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/jobs/does_not_exist_{uuid.uuid4().hex}")
        assert r.status_code == 404, r.text
        # Must be "Job not found", NOT "Workflow not found"
        assert "job" in r.text.lower()
        assert "workflow not found" not in r.text.lower()
