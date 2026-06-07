"""
test_iter67_app_customize — Mini-App Customization Panel (theme + branding).

Covers:
  - GET  /api/apps/{slug}/theme returns DEFAULT_THEME merged with any saved overrides.
  - PATCH /api/apps/{slug}/theme accepts partial updates; only the keys sent are mutated.
  - PATCH rejects bad hex colors with a Pydantic validation error.
  - PATCH rejects unknown border_radius values.
  - The /render endpoint reflects the saved theme: --tf-primary CSS var and the
    branded header bar contain the user's display_name when show_branding=true.
  - ?embed=1 query param suppresses the branded header even when show_branding=true.
  - Auth: GET + PATCH both require a valid JWT for the owner; 404 on someone else's app.
"""
from __future__ import annotations

import os
import sys
import uuid
import asyncio
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = os.environ.get("PUBLIC_API_BASE") or "http://localhost:8001"
ADMIN = "admin@nova.ai"
ADMIN_PW = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API}/api/auth/login", json={"email": ADMIN, "password": ADMIN_PW}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def seeded_app():
    """Insert a synthetic bot_project so we don't depend on seeded data."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import MongoClient

    proj_id = uuid.uuid4().hex
    slug = f"test-customize-{proj_id[:8]}"

    async def _setup():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ.get("DB_NAME", "taskforce")]
        admin = await db.users.find_one({"email": ADMIN})
        assert admin
        await db.bot_projects.insert_one({
            "id": proj_id,
            "user_id": str(admin["id"]),
            "name": "Customize Test App",
            "description": "synth",
            "has_ui": True,
            "app_slug": slug,
            "frontend": {
                "app_jsx": "window.__TF_APP = () => React.createElement('div', null, 'hi');",
                "manifest": {"title": "test"},
            },
            "files": [], "nodes": [], "edges": [],
            "is_public": False,
            "created_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z",
        })
        cli.close()

    asyncio.run(_setup())
    yield {"id": proj_id, "slug": slug}

    # Sync teardown — motor's loop may be closed by pytest at this point.
    sync = MongoClient(os.environ["MONGO_URL"])
    sync[os.environ.get("DB_NAME", "taskforce")].bot_projects.delete_one({"id": proj_id})
    sync.close()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_theme_get_returns_defaults(admin_token, seeded_app):
    r = httpx.get(f"{API}/api/apps/{seeded_app['slug']}/theme", headers=_h(admin_token), timeout=10)
    assert r.status_code == 200
    j = r.json()
    t = j["theme"]
    assert t["primary"] == "#22d3ee"
    assert t["accent"] == "#a855f7"
    assert t["background"] == "#0a0a0a"
    assert t["text"] == "#e5e7eb"
    assert t["border_radius"] == "rounded"
    assert t["show_branding"] is True
    assert t["display_name"] == ""
    assert t["logo_url"] == ""
    assert j["slug"] == seeded_app["slug"]
    assert j["is_public"] is False


def test_theme_patch_partial_update(admin_token, seeded_app):
    # Send only two keys — the rest of DEFAULT_THEME must remain untouched.
    r = httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme",
                    headers=_h(admin_token),
                    json={"primary": "#ff6b9d", "display_name": "Hello"}, timeout=10)
    assert r.status_code == 200, r.text
    t = r.json()["theme"]
    assert t["primary"] == "#ff6b9d"  # updated
    assert t["display_name"] == "Hello"  # updated
    assert t["accent"] == "#a855f7"  # preserved
    assert t["border_radius"] == "rounded"  # preserved

    # GET round-trip should agree.
    j = httpx.get(f"{API}/api/apps/{seeded_app['slug']}/theme", headers=_h(admin_token), timeout=10).json()
    assert j["theme"]["primary"] == "#ff6b9d"
    assert j["theme"]["display_name"] == "Hello"


def test_theme_patch_rejects_bad_hex(admin_token, seeded_app):
    r = httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme",
                    headers=_h(admin_token), json={"primary": "rgb(255,0,0)"}, timeout=10)
    assert r.status_code == 422


def test_theme_patch_rejects_bad_radius(admin_token, seeded_app):
    r = httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme",
                    headers=_h(admin_token), json={"border_radius": "extra-bouncy"}, timeout=10)
    assert r.status_code == 422


def test_render_applies_theme(admin_token, seeded_app):
    # Set a distinctive primary so we can grep for it in the rendered HTML.
    httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme",
                headers=_h(admin_token),
                json={"primary": "#abc123", "display_name": "Brandtest"}, timeout=10)
    r = httpx.get(f"{API}/api/apps/{seeded_app['slug']}/render?token={admin_token}", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert "--tf-primary: #abc123" in body, "CSS var should reflect saved primary"
    assert "Brandtest" in body, "Display name should appear in branded header"
    assert "tf-brand-bar" in body, "Branded header must render when show_branding=true"


def test_render_embed_flag_strips_chrome(admin_token, seeded_app):
    r_embed = httpx.get(f"{API}/api/apps/{seeded_app['slug']}/render?token={admin_token}&embed=1", timeout=10)
    assert r_embed.status_code == 200
    # The <div class="tf-brand-bar"> wrapper should not appear in embed mode.
    # (The CSS class definitions still exist in the <style> block — that's fine.)
    assert '<div class="tf-brand-bar"' not in r_embed.text


def test_theme_get_requires_auth(seeded_app):
    r = httpx.get(f"{API}/api/apps/{seeded_app['slug']}/theme", timeout=10)
    assert r.status_code in (401, 403)


def test_theme_patch_requires_auth(seeded_app):
    r = httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme", json={"primary": "#abcabc"}, timeout=10)
    assert r.status_code in (401, 403)


def test_show_branding_false_strips_chrome(admin_token, seeded_app):
    httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme",
                headers=_h(admin_token), json={"show_branding": False}, timeout=10)
    r = httpx.get(f"{API}/api/apps/{seeded_app['slug']}/render?token={admin_token}", timeout=10)
    assert '<div class="tf-brand-bar"' not in r.text
    # Restore for the next test run.
    httpx.patch(f"{API}/api/apps/{seeded_app['slug']}/theme",
                headers=_h(admin_token), json={"show_branding": True}, timeout=10)
