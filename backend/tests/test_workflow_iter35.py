"""
Iteration 35 tests — Task Force AI

Covers:
- 12 new BYOK services (instagram, stripe, telegram, discord, notion, gsheets,
  twilio, github, openai, anthropic, postgres, mongodb): POST credentials,
  GET roundtrip, DELETE cleanup.
- integration_handlers error paths (missing creds, SSRF, missing fields, write-
  protection on postgres, etc.) — no real outbound API calls.
- workflow_handlers dispatcher behavioural change: handle_action / handle_database
  / handle_llm route to real handlers (status='error' for missing BYOK) rather
  than the old skipped/not_executed_v1 pass-through.
- POST /api/exchange/listings/direct happy path + validation paths.
- Regression smoke: armory/build-bot still works.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import workflow_handlers, integration_handlers  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

NEW_BYOK_SERVICES = [
    "instagram", "stripe", "telegram", "discord", "notion", "gsheets",
    "twilio", "github", "openai", "anthropic", "postgres", "mongodb",
]


# Use a SINGLE shared event loop for the whole module so motor's cached
# executor is not closed between tests.
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─────────────────────────────────────────────────────────────
# BYOK credential round-trip for the 12 new services
# ─────────────────────────────────────────────────────────────
class TestBYOKCredentials:
    @pytest.mark.parametrize("service", NEW_BYOK_SERVICES)
    def test_create_get_delete_credential(self, base_url, admin_client, service):
        # CREATE
        payload = {"service": service, "api_key": f"TEST_key_{service}_{uuid.uuid4().hex[:6]}",
                   "extra": {"note": "iter35 test"}}
        r = admin_client.post(f"{base_url}/api/workflows/credentials", json=payload)
        assert r.status_code == 200, f"{service}: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("success") is True
        assert body.get("service") == service

        # GET — must be listed AND api_key must be masked / contain only original
        # tail (roundtrip via decrypt happens on _load_byok path; the GET endpoint
        # already returns the stored shape). We accept either masked or raw.
        r = admin_client.get(f"{base_url}/api/workflows/credentials")
        assert r.status_code == 200, r.text
        creds = {c["service"]: c for c in r.json().get("credentials", [])}
        assert service in creds, f"{service} not present in GET list"

        # DELETE cleanup
        r = admin_client.delete(f"{base_url}/api/workflows/credentials/{service}")
        assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Handler-level direct unit tests (call handlers as functions)
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def db(event_loop):
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    # Construct AsyncIOMotorClient inside the loop we'll reuse for all tests.
    async def _mk():
        return AsyncIOMotorClient(mongo_url)
    client = event_loop.run_until_complete(_mk())
    return client[db_name]


@pytest.fixture(scope="module")
def ctx(db):
    # Use a synthetic user_id that has NO byok creds.
    return {"db": db, "user_id": f"TEST_no_creds_{uuid.uuid4().hex[:8]}"}


def _arun(coro, event_loop):
    """Run async handler on the shared module event loop."""
    return event_loop.run_until_complete(coro)


class TestIntegrationHandlersErrorPaths:
    def test_telegram_missing_creds(self, ctx, event_loop):
        out = _arun(integration_handlers.action_telegram(
            {"chat_id": "123", "text": "hi"}, None, ctx), event_loop)
        assert out["status"] == "error"
        assert "Telegram BYOK missing" in out["log"]

    def test_discord_ssrf_block(self, ctx, event_loop):
        out = _arun(integration_handlers.action_discord(
            {"webhook_url": "http://localhost/foo"}, None, ctx), event_loop)
        assert out["status"] == "error"
        assert "SSRF" in out["log"]

    def test_github_missing_repo(self, db, event_loop):
        # Seed a fake github creds row so the missing-repo check is the one that fires.
        user_id = f"TEST_gh_repo_{uuid.uuid4().hex[:6]}"
        async def _seed():
            from lib.byok_crypto import encrypt_key
            await db.byok_credentials.insert_one({
                "user_id": user_id, "service": "github",
                "api_key": encrypt_key("ghp_fake"), "extra": {},
            })
            try:
                return await integration_handlers.action_github({}, None, {"db": db, "user_id": user_id})
            finally:
                await db.byok_credentials.delete_many({"user_id": user_id})
        out = _arun(_seed(), event_loop)
        assert out["status"] == "error"
        assert "repo" in out["log"].lower()

    def test_postgres_select_only(self, db, event_loop):
        # Even with creds present, DELETE should be blocked BEFORE connect attempt.
        user_id = f"TEST_pg_{uuid.uuid4().hex[:6]}"
        async def _seed():
            from lib.byok_crypto import encrypt_key
            await db.byok_credentials.insert_one({
                "user_id": user_id, "service": "postgres",
                "api_key": encrypt_key("postgres://u:p@127.0.0.1:5432/x"),
                "extra": {},
            })
            try:
                return await integration_handlers.db_postgres(
                    {"query": "DELETE FROM users", "allow_write": False},
                    None, {"db": db, "user_id": user_id})
            finally:
                await db.byok_credentials.delete_many({"user_id": user_id})
        out = _arun(_seed(), event_loop)
        assert out["status"] == "error"
        assert "SELECT" in out["log"]

    def test_llm_openai_missing(self, ctx, event_loop):
        out = _arun(integration_handlers.llm_openai({"prompt": "hi"}, None, ctx), event_loop)
        assert out["status"] == "error"
        assert "OpenAI BYOK missing" in out["log"]


# ─────────────────────────────────────────────────────────────
# Dispatcher behavioural change: no more pass-through skipped
# ─────────────────────────────────────────────────────────────
class TestDispatcherNoMorePassthrough:
    @pytest.mark.parametrize("service", [
        "discord", "stripe", "telegram", "notion", "github", "twilio",
        "instagram", "gsheets",
    ])
    def test_action_dispatch_returns_error_not_skipped(self, ctx, service, event_loop):
        node = {"type": "action", "data": {"service": service}}
        out = _arun(workflow_handlers.handle_action(node, None, ctx), event_loop)
        assert out["status"] == "error", f"{service} expected error, got {out}"
        assert not out.get("not_executed_v1"), f"{service} still pass-through!"

    def test_database_postgres_dispatch(self, ctx, event_loop):
        node = {"type": "database", "data": {"service": "postgres", "query": "SELECT 1"}}
        out = _arun(workflow_handlers.handle_database(node, None, ctx), event_loop)
        assert out["status"] == "error"
        assert "Postgres DSN missing" in out["log"]
        assert not out.get("not_executed_v1")

    def test_database_mongodb_dispatch(self, ctx, event_loop):
        node = {"type": "database", "data": {"service": "mongodb", "db": "x", "collection": "y"}}
        out = _arun(workflow_handlers.handle_database(node, None, ctx), event_loop)
        # No URI in creds + node has no uri → error
        assert out["status"] == "error"
        assert not out.get("not_executed_v1")

    def test_llm_openai_provider_no_byok(self, ctx, event_loop):
        node = {"type": "llm", "data": {"provider": "openai", "prompt": "hi"}}
        out = _arun(workflow_handlers.handle_llm(node, None, ctx), event_loop)
        assert out["status"] == "error"
        assert "OpenAI BYOK missing" in out["log"]

    def test_llm_platform_gemini_fallback(self, ctx, event_loop):
        # No provider field → platform Gemini path. EMERGENT_LLM_KEY is set.
        node = {"type": "llm", "data": {"prompt": "Say OK in one word."}}
        out = _arun(workflow_handlers.handle_llm(node, "test input", ctx), event_loop)
        # Either ok with response OR error from upstream; accept both but
        # error must NOT be 'Emergent LLM Key not configured.'
        if out["status"] == "error":
            assert "Emergent LLM Key not configured" not in out["log"], out
        else:
            assert out["status"] == "ok"
            assert "llm_response" in (out.get("output") or {})


# ─────────────────────────────────────────────────────────────
# POST /api/exchange/listings/direct
# ─────────────────────────────────────────────────────────────
class TestDirectPublishEndpoint:
    @pytest.fixture(scope="class")
    def created(self, base_url, admin_client):
        payload = {
            "name": f"TEST_direct_{uuid.uuid4().hex[:6]}",
            "description": "Direct publish test bot for iter35 regression run.",
            "category": "automation",
            "tags": ["test", "iter35"],
            "rent_price": 1.5,
            "buy_price": 25,
            "files": [
                {"path": "main.py", "content": "print(1)", "language": "python"},
                {"path": "../../etc/passwd", "content": "evil", "language": "text"},
            ],
            "nodes": [{"id": "n1", "type": "trigger"}, {"id": "n2", "type": "action"}],
            "edges": [{"source": "n1", "target": "n2"}],
            "language": "python",
        }
        r = admin_client.post(f"{base_url}/api/exchange/listings/direct", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        yield body, payload
        # Teardown — best effort
        listing_id = body.get("id")
        project_id = body.get("project_id")
        if listing_id:
            admin_client.delete(f"{base_url}/api/exchange/listings/{listing_id}")
        if project_id:
            admin_client.delete(f"{base_url}/api/armory/bot-projects/{project_id}")

    def test_direct_happy_path(self, created):
        body, payload = created
        assert body["status"] == "draft"
        assert body["id"]
        assert body["project_id"]
        assert body.get("source_project_id") == body["project_id"]
        assert body["name"] == payload["name"]
        assert body["node_count"] == 2
        assert body["edge_count"] == 1

    def test_direct_path_traversal_dropped(self, created, base_url, admin_client):
        body, _ = created
        project_id = body["project_id"]
        r = admin_client.get(f"{base_url}/api/armory/bot-projects/{project_id}")
        assert r.status_code == 200, r.text
        proj = r.json()
        file_paths = [f["path"] for f in proj.get("files", [])]
        assert "main.py" in file_paths
        # Path traversal entry must have been silently dropped
        assert all(".." not in p for p in file_paths)
        assert "../../etc/passwd" not in file_paths

    def test_direct_in_bot_projects_list(self, created, base_url, admin_client):
        body, payload = created
        r = admin_client.get(f"{base_url}/api/armory/bot-projects")
        assert r.status_code == 200, r.text
        projects = r.json().get("projects", r.json())
        if isinstance(projects, dict):
            projects = projects.get("projects", [])
        matched = [p for p in projects if p.get("id") == body["project_id"]]
        assert matched, f"Project {body['project_id']} not in bot-projects list"
        proj = matched[0]
        assert proj["name"] == payload["name"]
        # commit_history is stripped on list endpoint — fetch detail to verify
        rd = admin_client.get(f"{base_url}/api/armory/bot-projects/{body['project_id']}")
        assert rd.status_code == 200
        assert len(rd.json().get("commit_history", [])) == 1

    def test_direct_validation_short_description(self, base_url, admin_client):
        r = admin_client.post(f"{base_url}/api/exchange/listings/direct", json={
            "name": "TEST_validation_x", "description": "short",
            "category": "auto", "tags": [], "rent_price": 0, "buy_price": 0,
            "files": [], "nodes": [], "edges": [],
        })
        assert r.status_code == 422

    def test_direct_validation_empty_name(self, base_url, admin_client):
        r = admin_client.post(f"{base_url}/api/exchange/listings/direct", json={
            "name": "", "description": "Long enough description here for validator.",
            "category": "auto", "tags": [], "rent_price": 0, "buy_price": 0,
        })
        assert r.status_code == 422

    def test_direct_unauthenticated(self, base_url):
        r = requests.post(f"{base_url}/api/exchange/listings/direct", json={
            "name": "TEST_no_auth", "description": "Long enough description here for validator.",
            "category": "auto", "tags": [], "rent_price": 0, "buy_price": 0,
        }, timeout=15)
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────
# Smoke: armory/build-bot still works
# ─────────────────────────────────────────────────────────────
class TestBuildBotSmoke:
    def test_build_bot_smoke(self, base_url, admin_client):
        r = admin_client.post(f"{base_url}/api/armory/build-bot",
                              json={"prompt": "build a simple calculator"}, timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        project = body.get("project") or {}
        files = project.get("files") or body.get("files", [])
        nodes = project.get("nodes") or body.get("nodes", [])
        assert len(files) >= 3, f"only {len(files)} files"
        assert len(nodes) >= 3, f"only {len(nodes)} nodes"
        # Cleanup bot-project if returned
        pid = body.get("project_id") or body.get("id")
        if pid:
            admin_client.delete(f"{base_url}/api/armory/bot-projects/{pid}")
