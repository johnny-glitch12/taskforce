"""
Iteration 58 — Vibe 5-stage pipeline + Hosted Mini-Apps regression tests.

Covers:
  - /api/vibe/generate Celery dispatch (queued return, no blocking)
  - /api/vibe/build-status polling shape
  - /api/vibe/resume-build pause/resume gates
  - /api/my-apps, /api/apps/{slug}, /api/apps/{slug}/render
  - /api/apps/{id}/run sandbox + run history + cross-tenant 403
  - /api/apps/{id}/redesign
  - /api/admin/runtime/status owner-only gate
  - Regression: existing /vibe/chat, /vibe/models, /vibe/sessions, /vibe/recommend-model, /vibe/generate-legacy
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = ("admin@nova.ai", "admin123")
DEV_ADMIN = ("benjamin@taskforce.ai", "benjamin-J7VBJ4rL")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_token():
    return _login(*OWNER)


@pytest.fixture(scope="module")
def dev_token():
    return _login(*DEV_ADMIN)


@pytest.fixture(scope="module")
def owner_headers(owner_token):
    return {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def dev_headers(dev_token):
    return {"Authorization": f"Bearer {dev_token}", "Content-Type": "application/json"}


# ── Regression: existing endpoints ─────────────────────
class TestRegressionExisting:
    def test_models_list(self, owner_headers):
        r = requests.get(f"{BASE_URL}/api/vibe/models", headers=owner_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "models" in data and len(data["models"]) >= 6
        assert data["default"] == "gemini-2.5-flash"

    def test_sessions_list(self, owner_headers):
        r = requests.get(f"{BASE_URL}/api/vibe/sessions", headers=owner_headers, timeout=10)
        assert r.status_code == 200
        assert "sessions" in r.json()

    def test_vibe_chat_works(self, owner_headers):
        r = requests.post(f"{BASE_URL}/api/vibe/chat", headers=owner_headers,
                          json={"message": "hi quick chat", "model": "gemini-2.5-flash"}, timeout=60)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "session_id" in d and "response" in d and "credits_used" in d

    def test_recommend_model(self, owner_headers):
        r = requests.post(f"{BASE_URL}/api/vibe/recommend-model", headers=owner_headers,
                          json={"prompt": "build a slack notification bot"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["model"] in {"gemini-2.5-flash", "gemini-2.5-pro", "gpt-4o", "gpt-4o-mini",
                              "claude-sonnet", "claude-haiku"}


# ── Pipeline: dispatch + status ────────────────────────
class TestVibePipeline:
    @pytest.fixture(scope="class")
    def session_id(self, owner_headers):
        # Bootstrap a session via chat
        r = requests.post(f"{BASE_URL}/api/vibe/chat", headers=owner_headers,
                          json={"message": "I want a tool that uppercases input text", "model": "gemini-2.5-flash"},
                          timeout=60)
        assert r.status_code == 200
        return r.json()["session_id"]

    def test_generate_returns_queued_fast(self, owner_headers, session_id):
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/vibe/generate", headers=owner_headers,
                          json={"session_id": session_id,
                                "message": "Build a text capitalizer agent that converts input to uppercase. Include UI.",
                                "model": "gemini-2.5-flash"}, timeout=15)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["status"] == "queued"
        assert d["session_id"] == session_id
        assert "task_id" in d
        assert "poll_url" in d and session_id in d["poll_url"]
        assert elapsed < 5, f"queued response took {elapsed:.1f}s (must be <3-5s)"

    def test_build_status_polling(self, owner_headers, session_id):
        # Poll up to 180s for completion
        deadline = time.time() + 180
        last = None
        while time.time() < deadline:
            r = requests.get(f"{BASE_URL}/api/vibe/build-status/{session_id}",
                             headers=owner_headers, timeout=10)
            assert r.status_code == 200
            last = r.json()
            if last.get("status") in ("complete", "failed", "paused"):
                break
            time.sleep(2)
        assert last is not None
        assert last["status"] in ("complete", "failed", "paused"), f"never settled: {last.get('status')}"
        # Stage progress shape
        progress = last.get("progress", [])
        if last["status"] == "complete":
            stages = {p.get("stage") for p in progress}
            # Expect at least architect/planner/builder/ui_builder
            assert "architect" in stages
            assert "builder" in stages
            for p in progress:
                assert p.get("status") in {"running", "done", "skipped", "failed", "paused"}
            assert last.get("project_id")
            proj = last.get("project")
            assert proj is not None
            if proj.get("has_ui"):
                assert proj.get("app_slug")
                assert "frontend" in proj
        # Pass session info to next class
        pytest.shared_session_id = session_id
        pytest.shared_last_status = last


# ── Apps endpoints ─────────────────────────────────────
class TestAppsEndpoints:
    @pytest.fixture(scope="class")
    def app_slug(self, owner_headers):
        # Find an existing UI-enabled app from /my-apps
        r = requests.get(f"{BASE_URL}/api/my-apps", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        apps = r.json().get("apps", [])
        if not apps:
            pytest.skip("No UI mini-app available; pipeline must complete with has_ui=true first")
        # Prefer the text-capitalizer one if present
        chosen = next((a for a in apps if "capital" in (a.get("name") or "").lower()), apps[0])
        assert chosen.get("slug"), "app has no slug"
        return chosen["slug"], chosen["id"]

    def test_my_apps_lists_user_apps(self, owner_headers):
        r = requests.get(f"{BASE_URL}/api/my-apps", headers=owner_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "apps" in d
        for a in d["apps"]:
            assert "id" in a and "slug" in a and "manifest" in a and "run_count" in a

    def test_my_apps_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/my-apps", timeout=10)
        assert r.status_code == 401

    def test_get_app_by_slug(self, owner_headers, app_slug):
        slug, _ = app_slug
        r = requests.get(f"{BASE_URL}/api/apps/{slug}", headers=owner_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == slug
        assert "frontend" in d
        assert d["frontend"].get("app_jsx"), "app_jsx is empty"
        assert "window.__TF_APP" in d["frontend"]["app_jsx"]

    def test_get_app_404_for_unknown(self, owner_headers):
        r = requests.get(f"{BASE_URL}/api/apps/does-not-exist-xyz", headers=owner_headers, timeout=10)
        assert r.status_code == 404

    def test_get_app_cross_tenant_404(self, dev_headers, app_slug):
        slug, _ = app_slug
        r = requests.get(f"{BASE_URL}/api/apps/{slug}", headers=dev_headers, timeout=10)
        # Dev admin is not the owner of this app → 404 (privacy by obscurity)
        assert r.status_code == 404

    def test_render_html_no_auth(self, app_slug):
        slug, _ = app_slug
        r = requests.get(f"{BASE_URL}/api/apps/{slug}/render", timeout=10)
        assert r.status_code == 200
        html = r.text
        assert "babel" in html.lower()
        assert "react" in html.lower()
        assert "tfApi" in html
        assert "window.__TF_APP" in html or "__TF_APP" in html

    def test_render_404_for_unknown(self):
        r = requests.get(f"{BASE_URL}/api/apps/does-not-exist-xyz/render", timeout=10)
        assert r.status_code == 404

    def test_run_app_sandbox(self, owner_headers, app_slug):
        slug, app_id = app_slug
        r = requests.post(f"{BASE_URL}/api/apps/{app_id}/run", headers=owner_headers,
                          json={"input": {"text": "hello world"}}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # The text capitalizer agent should succeed; other agents may fail safely
        assert "success" in d
        assert "credits_used" in d
        assert "duration_ms" in d
        if "capital" in slug.lower() and d.get("success"):
            out = d.get("output") or {}
            # Output should contain uppercased text somewhere
            joined = " ".join(str(v) for v in out.values())
            assert "HELLO" in joined.upper()

    def test_run_app_cross_tenant_forbidden(self, dev_headers, app_slug):
        _, app_id = app_slug
        r = requests.post(f"{BASE_URL}/api/apps/{app_id}/run", headers=dev_headers,
                          json={"input": {"text": "test"}}, timeout=15)
        assert r.status_code == 403

    def test_runs_history(self, owner_headers, app_slug):
        _, app_id = app_slug
        r = requests.get(f"{BASE_URL}/api/apps/{app_id}/runs", headers=owner_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "runs" in d and isinstance(d["runs"], list)
        assert "count" in d

    def test_runs_history_cross_tenant_404(self, dev_headers, app_slug):
        _, app_id = app_slug
        r = requests.get(f"{BASE_URL}/api/apps/{app_id}/runs", headers=dev_headers, timeout=10)
        assert r.status_code == 404


# ── Resume-build pause gate ────────────────────────────
class TestResumeBuild:
    def test_resume_non_paused_returns_409(self, owner_headers):
        # Use the session that completed in TestVibePipeline
        sid = getattr(pytest, "shared_session_id", None)
        if not sid:
            pytest.skip("No prior session to test resume")
        r = requests.post(f"{BASE_URL}/api/vibe/resume-build/{sid}", headers=owner_headers, timeout=10)
        # If completed, returns 409
        assert r.status_code in (409, 200)
        if r.status_code == 409:
            assert "not paused" in r.text.lower()

    def test_resume_unknown_session_404(self, owner_headers):
        r = requests.post(f"{BASE_URL}/api/vibe/resume-build/no-such-sid-xyz",
                          headers=owner_headers, timeout=10)
        assert r.status_code == 404


# ── Runtime status gate ────────────────────────────────
class TestRuntimeStatus:
    def test_owner_can_view(self, owner_headers):
        r = requests.get(f"{BASE_URL}/api/admin/runtime/status", headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        runtime = d.get("runtime") or {}
        assert runtime.get("active") == "celery"
        ch = runtime.get("celery_health") or d.get("celery_health") or {}
        assert ch.get("ok") is True
        assert "latency_ms" in ch
        tasks = (runtime.get("celery") or {}).get("tasks") or d.get("tasks") or []
        names = " ".join(str(t) for t in tasks)
        assert "tfai.vibe_build" in names or "vibe_build" in names

    def test_dev_admin_forbidden(self, dev_headers):
        r = requests.get(f"{BASE_URL}/api/admin/runtime/status", headers=dev_headers, timeout=10)
        assert r.status_code == 403
        body = r.json()
        # Detail or error field carries the OWNER_ONLY marker
        flat = str(body)
        assert "OWNER" in flat.upper() or "owner" in flat.lower()

    def test_anonymous_unauthorized(self):
        r = requests.get(f"{BASE_URL}/api/admin/runtime/status", timeout=10)
        assert r.status_code == 401


# ── Redesign endpoint ──────────────────────────────────
class TestRedesign:
    def test_redesign_unknown_app_404(self, owner_headers):
        r = requests.post(f"{BASE_URL}/api/apps/no-such-app-zzz/redesign",
                          headers=owner_headers,
                          json={"prompt": "make it blue"}, timeout=10)
        assert r.status_code == 404

    def test_redesign_validation_min_length(self, owner_headers):
        r = requests.post(f"{BASE_URL}/api/apps/anything/redesign",
                          headers=owner_headers,
                          json={"prompt": "x"}, timeout=10)
        assert r.status_code == 422  # pydantic min_length=5
