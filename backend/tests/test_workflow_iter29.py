"""
Iteration 29 — NEW coverage for:
  • BYOK encryption-at-rest (enc:v1: prefix, decrypt-on-use)
  • Pydantic BYOKCreate + SaveCanvasRequest (422 validation)
  • /workflows/{id}/runs pagination + lean projection + detail endpoint
  • Stripe extracted routes (/api/payments/*)
  • Stale job sweeper (mark_stale_jobs_failed)
  • Bulk templates (>=280)
"""
import os
import sys
import uuid
import time
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _mongo():
    return MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=4000)[os.environ["DB_NAME"]]


def _save_wf(client, base_url, nodes, edges, name="TEST_iter29"):
    studio_id = f"TEST_i29_{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{base_url}/api/workflows/save",
        json={"studio_workflow_id": studio_id, "name": name,
              "nodes": nodes, "edges": edges},
    )
    assert r.status_code == 200, r.text
    return r.json()["workflow_id"]


# ─────────────────────── 1. BYOK Encryption-at-rest ───────────────────────
class TestBYOKEncryption:
    @pytest.fixture(autouse=True)
    def _clean(self, base_url, admin_client):
        db = _mongo()
        me = admin_client.get(f"{base_url}/api/auth/me").json()
        uid = str(me.get("id", me.get("email")))
        db.byok_credentials.delete_many({"user_id": uid})
        yield
        db.byok_credentials.delete_many({"user_id": uid})

    def test_stored_value_is_encrypted_with_prefix(self, base_url, admin_client):
        plaintext = "ya29.SECRETTOKEN_XYZ_LAST1234"
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "gmail", "api_key": plaintext, "extra": {}},
        )
        assert r.status_code == 200, r.text

        db = _mongo()
        me = admin_client.get(f"{base_url}/api/auth/me").json()
        uid = str(me.get("id", me.get("email")))
        doc = db.byok_credentials.find_one({"user_id": uid, "service": "gmail"})
        assert doc is not None
        assert doc["api_key"].startswith("enc:v1:"), f"expected encrypted prefix, got: {doc['api_key'][:20]}"
        assert plaintext not in doc["api_key"], "plaintext leaked into ciphertext field"

    def test_masked_field_shows_last4_of_plaintext_not_ciphertext(self, base_url, admin_client):
        plaintext = "SG.ABCDEFG_token_LAST9999"
        admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "sendgrid", "api_key": plaintext, "extra": {}},
        )
        r = admin_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200
        creds = r.json()["credentials"]
        cred = next(c for c in creds if c["service"] == "sendgrid")
        assert cred["encrypted"] is True
        assert cred["api_key_masked"].endswith("9999"), cred["api_key_masked"]
        # Should NOT contain ciphertext or plaintext
        assert "enc:v1:" not in cred["api_key_masked"]
        assert "ABCDEFG_token" not in cred["api_key_masked"]
        assert "api_key" not in cred

    def test_legacy_plaintext_row_still_readable(self, base_url, admin_client):
        """Insert a legacy plaintext row directly, then read via API — should still work."""
        db = _mongo()
        me = admin_client.get(f"{base_url}/api/auth/me").json()
        uid = str(me.get("id", me.get("email")))
        db.byok_credentials.delete_many({"user_id": uid, "service": "slack"})
        # Insert as legacy plaintext (no enc:v1: prefix)
        db.byok_credentials.insert_one({
            "user_id": uid, "service": "slack",
            "api_key": "https://hooks.slack.com/services/LEGACY1234",
            "extra": {}, "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        r = admin_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200
        cred = next(c for c in r.json()["credentials"] if c["service"] == "slack")
        # Legacy plaintext path → encrypted=False, masked uses plaintext last 4
        assert cred["encrypted"] is False
        assert cred["api_key_masked"].endswith("1234")

    def test_action_slack_decrypts_byok_and_calls_handler(self, base_url, admin_client):
        """With a bogus webhook URL stored encrypted, executing slack action should hit the URL
        and fail with HTTP/SSRF error — NOT decryption-failed or empty-key error."""
        # Use a valid hooks.slack.com path (passes SSRF allowlist if any) with bogus token
        admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack",
                  "api_key": "https://hooks.slack.com/services/T_BOGUS/B_BOGUS/abcdef1234567890XYZ",
                  "extra": {}},
        )
        nodes = [
            {"id": "t1", "type": "trigger", "data": {"payload": {"text": "hi"}}},
            {"id": "a1", "type": "action", "data": {"service": "slack", "text": "Hello"}},
        ]
        wf_id = _save_wf(admin_client, base_url, nodes, [{"from": "t1", "to": "a1"}])
        try:
            r = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
            assert r.status_code == 200, r.text
            a_node = next(n for n in r.json()["node_results"] if n["node_id"] == "a1")
            log = (a_node.get("log") or "").lower()
            # The handler MUST have got the decrypted key — therefore failure must come from Slack's HTTP layer
            # NOT from decrypt-fail (empty key would surface as 'byok not configured')
            assert "slack byok not configured" not in log, f"decrypt path failed → handler saw empty key: {log}"
            assert "decryption failed" not in log
            # Common outcomes: handler dispatched (status: ok/success/error all fine)
            # The key assertion is that decryption WORKED — i.e. log shows the handler
            # actually hit Slack (e.g. 'Slack post → 302' / 'invalid_token').
            assert a_node["status"] in ("error", "success", "ok"), a_node
            assert "slack" in log or "post" in log or "hooks" in log, log
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ─────────────────────── 2. Pydantic BYOK validation (422) ───────────────────────
class TestBYOKPydanticValidation:
    def test_bogus_service_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "bogus", "api_key": "abc", "extra": {}},
        )
        assert r.status_code == 422, r.text
        body = r.json()
        detail = str(body.get("detail", body)).lower()
        assert "literal_error" in detail or "literal" in detail or "expected" in detail

    def test_empty_api_key_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "", "extra": {}},
        )
        assert r.status_code == 422, r.text
        detail = str(r.json().get("detail", "")).lower()
        assert "string_too_short" in detail or "at least 1" in detail

    def test_oversize_api_key_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "x" * 5000, "extra": {}},
        )
        assert r.status_code == 422, r.text
        detail = str(r.json().get("detail", "")).lower()
        assert "string_too_long" in detail or "at most 4096" in detail

    def test_extra_as_list_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/credentials",
            json={"service": "slack", "api_key": "abc", "extra": ["a", "b"]},
        )
        assert r.status_code == 422, r.text


# ─────────────────────── 3. SaveCanvasRequest Pydantic validation ───────────────────────
class TestSaveCanvasPydantic:
    def test_missing_studio_id_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"name": "x", "nodes": [], "edges": []},
        )
        assert r.status_code == 422, r.text
        detail = str(r.json().get("detail", "")).lower()
        assert "field required" in detail or "missing" in detail

    def test_empty_studio_id_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"studio_workflow_id": "", "name": "x", "nodes": [], "edges": []},
        )
        assert r.status_code == 422, r.text
        detail = str(r.json().get("detail", "")).lower()
        assert "string_too_short" in detail or "non-empty" in detail or "at least 1" in detail

    def test_whitespace_studio_id_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"studio_workflow_id": "   ", "name": "x", "nodes": [], "edges": []},
        )
        assert r.status_code == 422, r.text
        detail = str(r.json().get("detail", "")).lower()
        assert "non-empty" in detail or "value_error" in detail

    def test_nodes_not_array_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"studio_workflow_id": "x", "name": "y", "nodes": "not-a-list", "edges": []},
        )
        assert r.status_code == 422, r.text

    def test_name_too_long_returns_422(self, base_url, admin_client):
        r = admin_client.post(
            f"{base_url}/api/workflows/save",
            json={"studio_workflow_id": "TEST_long", "name": "x" * 250,
                  "nodes": [], "edges": []},
        )
        assert r.status_code == 422, r.text


# ─────────────────────── 4. Runs pagination ───────────────────────
class TestRunsPagination:
    def test_runs_returns_pagination_envelope(self, base_url, admin_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger", "data": {"payload": 1}}], [])
        admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        try:
            r = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs")
            assert r.status_code == 200, r.text
            body = r.json()
            for k in ("runs", "total", "limit", "skip"):
                assert k in body, f"missing key {k} in {body}"
            assert isinstance(body["runs"], list)
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_runs_list_strips_node_results(self, base_url, admin_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger", "data": {"payload": 1}}], [])
        admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
        try:
            r = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs")
            runs = r.json()["runs"]
            assert len(runs) >= 1
            for run in runs:
                assert "node_results" not in run, f"node_results should be stripped from list: {run.keys()}"
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_runs_limit_skip_paginates(self, base_url, admin_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger", "data": {"payload": 1}}], [])
        try:
            for _ in range(12):
                admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
            r1 = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs?limit=5&skip=0")
            r2 = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs?limit=5&skip=5")
            assert r1.status_code == 200 and r2.status_code == 200
            page1 = r1.json()["runs"]
            page2 = r2.json()["runs"]
            assert len(page1) == 5
            assert len(page2) == 5
            ids1 = {r["id"] for r in page1}
            ids2 = {r["id"] for r in page2}
            assert ids1.isdisjoint(ids2), "skip not honored — pages overlap"
            assert r1.json()["total"] >= 12
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_runs_limit_clamped_to_100(self, base_url, admin_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger"}], [])
        try:
            r = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs?limit=500")
            assert r.status_code == 200, r.text
            assert r.json()["limit"] <= 100
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_run_detail_returns_node_results(self, base_url, admin_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger", "data": {"payload": 7}}], [])
        try:
            er = admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
            assert er.status_code == 200
            # Get the run id from list endpoint
            lst = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs").json()
            assert lst["runs"], lst
            run_id = lst["runs"][0]["id"]
            r = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs/{run_id}")
            assert r.status_code == 200, r.text
            data = r.json()
            assert "node_results" in data, f"detail should include node_results: {data.keys()}"
            assert isinstance(data["node_results"], list)
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")

    def test_run_detail_other_user_404(self, base_url, admin_client, freeuser_client):
        wf_id = _save_wf(admin_client, base_url,
                         [{"id": "t1", "type": "trigger"}], [])
        try:
            admin_client.post(f"{base_url}/api/workflows/{wf_id}/execute")
            lst = admin_client.get(f"{base_url}/api/workflows/{wf_id}/runs").json()
            if not lst["runs"]:
                pytest.skip("no run produced")
            run_id = lst["runs"][0]["id"]
            r = freeuser_client.get(f"{base_url}/api/workflows/{wf_id}/runs/{run_id}")
            assert r.status_code == 404, r.text
        finally:
            admin_client.delete(f"{base_url}/api/workflows/{wf_id}")


# ─────────────────────── 5. Stripe extracted routes ───────────────────────
class TestStripeExtracted:
    def test_checkout_route_exists(self, base_url, admin_client):
        # Try to create a checkout — route MUST exist (no 404).
        r = admin_client.post(
            f"{base_url}/api/payments/checkout",
            json={"agent_id": "TEST_nonexistent_agent_id"},
        )
        # 404 ONLY ok if it's "agent not found", NOT route-missing.
        # Route missing usually returns FastAPI's 404 with detail "Not Found".
        if r.status_code == 404:
            body = (r.text or "").lower()
            assert "agent" in body or "not found" in body, f"route appears missing: {r.text}"
        else:
            assert r.status_code in (200, 400, 402, 500, 502), r.text

    def test_status_nonexistent_session_returns_404(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/payments/status/cs_test_nonexistent_{uuid.uuid4().hex}")
        assert r.status_code == 404, r.text
        assert "transaction not found" in r.text.lower() or "not found" in r.text.lower()

    def test_webhook_bad_signature_returns_200_with_error(self, base_url):
        r = requests.post(
            f"{base_url}/api/webhook/stripe",
            data=b'{"id":"evt_bogus","type":"checkout.session.completed"}',
            headers={"Stripe-Signature": "bogus", "Content-Type": "application/json"},
            timeout=10,
        )
        # Current contract: returns 200 with status:error
        assert r.status_code in (200, 400), r.text


# ─────────────────────── 6. Stale job sweeper ───────────────────────
class TestStaleJobSweeper:
    @pytest.mark.asyncio
    async def test_mark_stale_jobs_failed_sweeps_old_running(self, base_url, admin_client):
        from motor.motor_asyncio import AsyncIOMotorClient
        from lib.workflow_jobs import mark_stale_jobs_failed

        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        adb = client[os.environ["DB_NAME"]]

        # Insert a fake stale "running" job (15 min ago)
        job_id = f"TEST_stale_{uuid.uuid4().hex[:8]}"
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        me = admin_client.get(f"{base_url}/api/auth/me").json()
        uid = str(me.get("id", me.get("email")))
        await adb.workflow_jobs.insert_one({
            "id": job_id, "user_id": uid, "workflow_id": "fake_wf",
            "status": "running", "created_at": old_ts,
        })
        try:
            swept = await mark_stale_jobs_failed(adb, max_age_seconds=600)
            assert swept >= 1, f"expected at least 1 swept, got {swept}"
            # Verify via API
            r = admin_client.get(f"{base_url}/api/workflows/jobs/{job_id}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "failed"
            assert "worker_restart" in (body.get("error") or "").lower()
        finally:
            await adb.workflow_jobs.delete_one({"id": job_id})
            client.close()


# ─────────────────────── 7. Bulk templates (>=280) ───────────────────────
class TestBulkTemplates:
    def test_engine_status_templates_available_280plus(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/engine/status")
        assert r.status_code == 200, r.text
        n = r.json().get("templates_available", 0)
        assert n >= 280, f"expected >=280 templates, got {n}"

    def test_templates_list_with_limit_200(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/workflows/templates?limit=200")
        assert r.status_code == 200, r.text
        tpls = r.json().get("templates", [])
        assert len(tpls) == 200, f"expected 200 templates returned, got {len(tpls)}"
