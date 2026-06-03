"""
Iter42 backend tests — P7 Part 1 (.tfagent upload + AST scan), External Webhooks,
Real bot runtime, Onboarding endpoints.
"""
import io
import json
import hmac
import hashlib
import os
import time
import uuid
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"
ADMIN_DEPLOYMENT_ID = "9736667a4a2a4acca927acfb8de48a9c"


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


def _register_fresh():
    email = f"TEST_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "Test1234!", "name": "Fresh User"},
                      timeout=15)
    if r.status_code not in (200, 201):
        return None, None
    token = r.json().get("token") or r.json().get("access_token")
    return email, token


def _build_zip(files: dict) -> bytes:
    """files = {"manifest.json": "...", "main.py": "...", ...}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            z.writestr(path, content)
    return buf.getvalue()


VALID_MANIFEST = {
    "name": "demo-agent", "version": "1.0.0", "display_name": "Demo Agent",
    "description": "Test agent", "runtime": "python3.11",
    "entry_point": "main.py", "entry_function": "run",
}
VALID_MAIN = "async def run(input):\n    return {'ok': True}\n"


# ─── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    if not t:
        pytest.skip("Admin login failed")
    return t


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def fresh_user():
    # Try to register a fresh user; if rate-limited, fall back to freeuser@test.com
    email, token = _register_fresh()
    if not token:
        token = _login("freeuser@test.com", "test123")
        if not token:
            pytest.skip("Could not register or login fresh user")
        email = "freeuser@test.com"
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


# ============================================================================
# WHITELIST (public)
# ============================================================================
class TestWhitelist:
    def test_public_whitelist(self):
        r = requests.get(f"{BASE_URL}/api/external-agents/whitelist", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "openai" in data["allowed_packages"]
        assert "anthropic" in data["allowed_packages"]
        assert "httpx" in data["allowed_packages"]
        assert "pandas" in data["allowed_packages"]
        assert "numpy" in data["allowed_packages"]
        assert "subprocess" in data["banned_modules"]
        assert "socket" in data["banned_modules"]
        assert "ctypes" in data["banned_modules"]
        assert data["max_upload_mb"] == 50
        assert data["max_uncompressed_mb"] == 100
        assert len(data["manifest_required_fields"]) == 7
        assert "entry_point" in data["manifest_required_fields"]
        assert len(data["allowed_packages"]) >= 30


# ============================================================================
# EXTERNAL AGENT UPLOAD — valid + rejection paths
# ============================================================================
class TestExternalAgentUpload:
    def _upload(self, headers, zip_bytes, filename="agent.tfagent"):
        return requests.post(
            f"{BASE_URL}/api/external-agents/upload",
            headers=headers,
            files={"file": (filename, zip_bytes, "application/zip")},
            timeout=30,
        )

    def test_valid_upload(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": VALID_MAIN,
            "requirements.txt": "openai>=1.40.0\nhttpx\n",
        })
        r = self._upload(admin_headers, z)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["package_id"]
        assert data["scan_result"]["verdict"] == "passed"
        assert data["scan_result"]["violations"] == []
        assert "openai" in data["scan_result"]["allowed_packages"]
        # store for later tests
        TestExternalAgentUpload._pkg_id = data["package_id"]

    def test_corrupt_zip_rejected(self, admin_headers):
        r = self._upload(admin_headers, b"not-a-zip-file")
        assert r.status_code == 400
        assert "zip" in r.json()["detail"].lower()

    def test_missing_manifest_rejected(self, admin_headers):
        z = _build_zip({"main.py": VALID_MAIN})
        r = self._upload(admin_headers, z)
        assert r.status_code == 400
        assert "manifest" in r.json()["detail"].lower()

    def test_manifest_missing_field(self, admin_headers):
        bad = {k: v for k, v in VALID_MANIFEST.items() if k != "entry_point"}
        z = _build_zip({"manifest.json": json.dumps(bad), "main.py": VALID_MAIN})
        r = self._upload(admin_headers, z)
        assert r.status_code == 400
        assert "entry_point" in r.json()["detail"]

    def test_disallowed_packages(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": VALID_MAIN,
            "requirements.txt": "crypto\nsubprocess32\n",
        })
        r = self._upload(admin_headers, z)
        assert r.status_code == 200
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert "crypto" in data["scan_result"]["rejected_packages"]
        assert "subprocess32" in data["scan_result"]["rejected_packages"]
        assert data["package_id"] == ""

    def test_ast_banned_import_subprocess(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": "import subprocess\nasync def run(i): return {}\n",
        })
        r = self._upload(admin_headers, z)
        assert r.status_code == 200
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert any("subprocess" in v for v in data["scan_result"]["violations"])
        assert data["package_id"] == ""

    def test_ast_banned_socket(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": "import socket\nasync def run(i): return {}\n",
        })
        r = self._upload(admin_headers, z)
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert any("socket" in v for v in data["scan_result"]["violations"])

    def test_ast_from_os_system(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": "from os import system\nasync def run(i): return {}\n",
        })
        r = self._upload(admin_headers, z)
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert any("system" in v for v in data["scan_result"]["violations"])

    def test_ast_eval_call(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": "async def run(i):\n    eval('1+1')\n    return {}\n",
        })
        r = self._upload(admin_headers, z)
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert any("eval" in v for v in data["scan_result"]["violations"])

    def test_ast_subclasses(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": "async def run(i):\n    x = ().__class__.__subclasses__()\n    return {}\n",
        })
        r = self._upload(admin_headers, z)
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert any("__subclasses__" in v for v in data["scan_result"]["violations"])

    def test_entry_function_missing(self, admin_headers):
        z = _build_zip({
            "manifest.json": json.dumps(VALID_MANIFEST),
            "main.py": "async def something_else(i): return {}\n",
        })
        r = self._upload(admin_headers, z)
        data = r.json()
        assert data["scan_result"]["verdict"] == "rejected"
        assert any("entry_function" in v and "run" in v for v in data["scan_result"]["violations"])


# ============================================================================
# PACKAGE STORAGE (list/get/delete + cross-user)
# ============================================================================
class TestPackageStorage:
    def test_list_includes_uploaded(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/external-agents/packages",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert isinstance(pkgs, list)
        pkg_id = getattr(TestExternalAgentUpload, "_pkg_id", None)
        if pkg_id:
            assert any(p["id"] == pkg_id for p in pkgs)
            # No raw blob in response
            assert all("package_b64" not in p for p in pkgs)

    def test_get_one_package(self, admin_headers):
        pkg_id = getattr(TestExternalAgentUpload, "_pkg_id", None)
        if not pkg_id:
            pytest.skip("No package uploaded")
        r = requests.get(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == pkg_id
        assert "package_b64" not in data
        assert data["manifest"]["name"] == "demo-agent"

    def test_cross_user_404(self, fresh_user):
        pkg_id = getattr(TestExternalAgentUpload, "_pkg_id", None)
        if not pkg_id:
            pytest.skip("No package uploaded")
        r = requests.get(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                         headers=fresh_user["headers"], timeout=15)
        assert r.status_code == 404

    def test_delete_package(self, admin_headers):
        pkg_id = getattr(TestExternalAgentUpload, "_pkg_id", None)
        if not pkg_id:
            pytest.skip("No package uploaded")
        r = requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                            headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Subsequent GET → 404
        r2 = requests.get(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                          headers=admin_headers, timeout=15)
        assert r2.status_code == 404


# ============================================================================
# ONBOARDING
# ============================================================================
class TestOnboarding:
    def test_onboarding_state_endpoint_works(self, fresh_user):
        r = requests.get(f"{BASE_URL}/api/onboarding/me",
                         headers=fresh_user["headers"], timeout=15)
        assert r.status_code == 200
        assert "onboarded" in r.json()
        assert isinstance(r.json()["onboarded"], bool)

    def test_complete_onboarding(self, fresh_user):
        r = requests.post(f"{BASE_URL}/api/onboarding/complete",
                          headers=fresh_user["headers"], timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        r2 = requests.get(f"{BASE_URL}/api/onboarding/me",
                          headers=fresh_user["headers"], timeout=15)
        assert r2.json()["onboarded"] is True


# ============================================================================
# WEBHOOKS — info, rotate, fire, HMAC, events
# ============================================================================
class TestWebhookInfo:
    def test_get_webhook_info(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/webhook",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["deployment_id"] == ADMIN_DEPLOYMENT_ID
        assert data["webhook_key"]
        assert data["webhook_secret"]
        assert data["signature_header"] == "X-Signature"
        assert data["signature_algorithm"] == "hmac-sha256"
        TestWebhookInfo._key = data["webhook_key"]
        TestWebhookInfo._secret = data["webhook_secret"]

    def test_cross_user_404(self, fresh_user):
        r = requests.get(f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/webhook",
                         headers=fresh_user["headers"], timeout=15)
        assert r.status_code == 404


class TestWebhookFire:
    def test_fire_with_correct_key(self, admin_headers):
        key = getattr(TestWebhookInfo, "_key", None)
        if not key:
            # Trigger webhook info first
            r = requests.get(f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/webhook",
                             headers=admin_headers, timeout=15)
            key = r.json()["webhook_key"]
            TestWebhookInfo._key = key
            TestWebhookInfo._secret = r.json()["webhook_secret"]
        payload = {"test": "hello", "n": 42}
        r = requests.post(
            f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}?key={key}",
            json=payload, timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["received"] is True
        assert data["executed"] is True
        assert data["event_id"]
        assert data["run_id"]
        assert isinstance(data["duration_ms"], int)
        TestWebhookFire._event_id = data["event_id"]

    def test_fire_no_key(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}",
                          json={"a": 1}, timeout=15)
        assert r.status_code == 401

    def test_fire_wrong_key(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}?key=bogus_key_value",
                          json={"a": 1}, timeout=15)
        assert r.status_code == 401

    def test_fire_unknown_deployment(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/nonexistent_deployment_xyz?key=any",
                          json={"a": 1}, timeout=15)
        assert r.status_code == 404

    def test_hmac_correct(self, admin_headers):
        key = getattr(TestWebhookInfo, "_key", None)
        secret = getattr(TestWebhookInfo, "_secret", None)
        if not key:
            pytest.skip("No webhook key cached")
        body = json.dumps({"hmac": "test"}).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        r = requests.post(
            f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}?key={key}",
            data=body,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["executed"] is True

    def test_hmac_wrong(self, admin_headers):
        key = getattr(TestWebhookInfo, "_key", None)
        if not key:
            pytest.skip("No webhook key cached")
        body = json.dumps({"hmac": "test"}).encode()
        r = requests.post(
            f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}?key={key}",
            data=body,
            headers={"X-Signature": "deadbeef" * 8, "Content-Type": "application/json"},
            timeout=15,
        )
        assert r.status_code == 401
        assert "signature" in r.json()["detail"].lower()


class TestWebhookEvents:
    def test_event_persisted(self, admin_headers):
        # Allow async write to complete
        time.sleep(1)
        r = requests.get(
            f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/webhook/events",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200
        events = r.json()["events"]
        assert len(events) >= 1
        ev = events[0]
        assert ev["deployment_id"] == ADMIN_DEPLOYMENT_ID
        assert ev["status"] in ("success", "failed")
        assert ev.get("run_id")


class TestWebhookRotate:
    def test_rotate_invalidates_old_key(self, admin_headers):
        # Get current key first
        r0 = requests.get(f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/webhook",
                          headers=admin_headers, timeout=15)
        old_key = r0.json()["webhook_key"]
        # Rotate
        r = requests.post(f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/webhook/rotate",
                          headers=admin_headers, timeout=15)
        assert r.status_code == 200
        new_key = r.json()["webhook_key"]
        assert new_key != old_key
        # Old key should now fail
        r_old = requests.post(
            f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}?key={old_key}",
            json={}, timeout=15,
        )
        assert r_old.status_code == 401
        # New key should work
        r_new = requests.post(
            f"{BASE_URL}/api/webhooks/{ADMIN_DEPLOYMENT_ID}?key={new_key}",
            json={"after": "rotate"}, timeout=30,
        )
        assert r_new.status_code == 200


# ============================================================================
# REAL RUNTIME via /deployments/{id}/run
# ============================================================================
class TestRealRuntime:
    def test_run_real_executes_main_py(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/deployments/{ADMIN_DEPLOYMENT_ID}/run",
            headers=admin_headers, timeout=45,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # The deployment has main.py setting RESULT to a dict
        # Response shape varies; check for indicators of real execution
        assert "run_id" in data or "id" in data or data.get("success") is not None
        # If output_preview present, ensure it contains expected fields from RESULT
        preview = data.get("output_preview") or data.get("output") or ""
        if preview:
            # main.py: RESULT = {'msg':'hello!','input_received':INPUT,'env_count':len(ENV)}
            assert "hello" in preview or "msg" in preview or "input_received" in preview, f"preview={preview}"
