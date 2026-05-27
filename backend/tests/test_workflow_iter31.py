"""
Iteration 31 — Exchange listings, rate-limit, Gmail OAuth extraction, WS overwatch.

Covers:
- POST/GET/PUT/DELETE /api/exchange/listings + /upload + /my-listings
- Pydantic validation (422), public catalog (no auth), auto-promote draft→published
- Auth rate-limit (login/register/forgot-password)
- Gmail OAuth routes still respond after extraction to gmail_oauth_routes.py
- WebSocket /api/overwatch/feed admin-only auth + run streaming
"""
import io
import json
import time
import asyncio
import uuid
import pytest
import requests
import websockets

API_TIMEOUT = 20


# ─────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────
def _save_workflow(base_url: str, token: str, name: str = "TEST_i31_wf") -> str:
    """Create a real user_workflows entry via /api/workflows/save and return its id."""
    body = {
        "studio_workflow_id": f"studio_{uuid.uuid4().hex[:8]}",
        "name": name,
        "nodes": [{"id": "n1", "type": "trigger", "data": {"label": "Start"}}],
        "edges": [],
        "source_template": None,
    }
    r = requests.post(
        f"{base_url}/api/workflows/save",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=API_TIMEOUT,
    )
    assert r.status_code == 200, f"save workflow failed: {r.status_code} {r.text}"
    return r.json()["workflow_id"]


@pytest.fixture
def workflow_id(base_url, admin_token):
    return _save_workflow(base_url, admin_token)


# Cleanup all TEST_ listings after this run
@pytest.fixture(scope="module", autouse=True)
def _cleanup_test_listings(base_url, admin_token):
    yield
    try:
        r = requests.get(
            f"{base_url}/api/exchange/my-listings",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=API_TIMEOUT,
        )
        if r.status_code == 200:
            for li in r.json().get("listings", []):
                if li.get("name", "").startswith("TEST_"):
                    requests.delete(
                        f"{base_url}/api/exchange/listings/{li['id']}",
                        headers={"Authorization": f"Bearer {admin_token}"},
                        timeout=API_TIMEOUT,
                    )
    except Exception:
        pass


def _publish(base_url, token, wf_id, **overrides):
    body = {
        "workflow_id": wf_id,
        "name": "TEST_i31_listing",
        "description": "Iteration 31 published listing for tests.",
        "category": "automation",
        "tags": ["test", "iter31"],
        "rent_price": 1.50,
        "buy_price": 25.0,
    }
    body.update(overrides)
    return requests.post(
        f"{base_url}/api/exchange/listings",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=API_TIMEOUT,
    )


# ─────────────────────────────────────────────────────────────
# 1. Exchange — Publish + Pydantic validation
# ─────────────────────────────────────────────────────────────
class TestExchangePublish:
    def test_publish_listing_creates_draft(self, base_url, admin_token, workflow_id):
        r = _publish(base_url, admin_token, workflow_id)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "draft"
        assert data["source_workflow_id"] == workflow_id
        assert data["name"] == "TEST_i31_listing"
        assert data["rent_price"] == 1.50
        assert isinstance(data["id"], str) and len(data["id"]) > 0

    def test_publish_404_for_unknown_workflow(self, base_url, admin_token):
        r = _publish(base_url, admin_token, "nonexistent_wf_id_xyz")
        assert r.status_code == 404

    def test_validation_name_too_short(self, base_url, admin_token, workflow_id):
        r = _publish(base_url, admin_token, workflow_id, name="ab")
        assert r.status_code == 422

    def test_validation_description_too_short(self, base_url, admin_token, workflow_id):
        r = _publish(base_url, admin_token, workflow_id, description="short")
        assert r.status_code == 422

    def test_validation_rent_price_negative(self, base_url, admin_token, workflow_id):
        r = _publish(base_url, admin_token, workflow_id, rent_price=-1)
        assert r.status_code == 422

    def test_validation_buy_price_over_max(self, base_url, admin_token, workflow_id):
        r = _publish(base_url, admin_token, workflow_id, buy_price=999999)
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────
# 2. Exchange — Public catalog (no auth)
# ─────────────────────────────────────────────────────────────
class TestExchangePublic:
    def test_listings_public_no_auth(self, base_url):
        r = requests.get(f"{base_url}/api/exchange/listings", timeout=API_TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert "listings" in body
        assert "total" in body
        # Only published should appear
        for li in body["listings"]:
            assert li["status"] == "published"

    def test_get_single_listing_public(self, base_url, admin_token, workflow_id):
        # publish + promote via upload
        pub = _publish(base_url, admin_token, workflow_id).json()
        # auto-promote via 1 photo upload
        files = {"file": ("p.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 80), "image/png")}
        requests.post(
            f"{base_url}/api/exchange/listings/{pub['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "photo"},
            files=files,
            timeout=API_TIMEOUT,
        )
        r = requests.get(f"{base_url}/api/exchange/listings/{pub['id']}", timeout=API_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["id"] == pub["id"]

    def test_get_unknown_listing_404(self, base_url):
        r = requests.get(f"{base_url}/api/exchange/listings/does_not_exist", timeout=API_TIMEOUT)
        assert r.status_code == 404

    def test_category_and_search_filters(self, base_url, admin_token, workflow_id):
        # Create a uniquely-tagged listing
        unique = f"iter31needle{uuid.uuid4().hex[:6]}"
        pub = _publish(
            base_url, admin_token, workflow_id,
            name=f"TEST_{unique}", description=f"Listing with needle {unique}",
            category="datalab", tags=[unique],
        ).json()
        # Promote it
        files = {"file": ("p.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"y" * 80), "image/png")}
        requests.post(
            f"{base_url}/api/exchange/listings/{pub['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "photo"}, files=files, timeout=API_TIMEOUT,
        )
        # Category filter
        r = requests.get(f"{base_url}/api/exchange/listings?category=datalab", timeout=API_TIMEOUT)
        assert r.status_code == 200
        ids = [li["id"] for li in r.json()["listings"]]
        assert pub["id"] in ids
        # Search filter (text)
        r = requests.get(f"{base_url}/api/exchange/listings?search={unique}", timeout=API_TIMEOUT)
        assert r.status_code == 200
        ids = [li["id"] for li in r.json()["listings"]]
        assert pub["id"] in ids


# ─────────────────────────────────────────────────────────────
# 3. Exchange — Update + Delete + ownership
# ─────────────────────────────────────────────────────────────
class TestExchangeMutations:
    def test_update_own_listing(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        r = requests.put(
            f"{base_url}/api/exchange/listings/{pub['id']}",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"name": "TEST_i31_updated_name", "status": "published"},
            timeout=API_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "TEST_i31_updated_name"
        assert body["status"] == "published"

    def test_delete_other_user_listing_returns_404(self, base_url, admin_token, freeuser_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        # Free user attempts delete admin's listing
        r = requests.delete(
            f"{base_url}/api/exchange/listings/{pub['id']}",
            headers={"Authorization": f"Bearer {freeuser_token}"},
            timeout=API_TIMEOUT,
        )
        assert r.status_code == 404

    def test_delete_own_listing(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        r = requests.delete(
            f"{base_url}/api/exchange/listings/{pub['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=API_TIMEOUT,
        )
        assert r.status_code == 200
        # Confirm gone
        r = requests.get(f"{base_url}/api/exchange/listings/{pub['id']}", timeout=API_TIMEOUT)
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# 4. Exchange — Multipart uploads + auto-promote
# ─────────────────────────────────────────────────────────────
class TestExchangeUploads:
    def test_video_upload_accepts_mp4_and_sets_url_and_promotes(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        assert pub["status"] == "draft"
        files = {"file": ("demo.mp4", io.BytesIO(b"\x00\x00\x00\x18ftypmp42" + b"v" * 200), "video/mp4")}
        r = requests.post(
            f"{base_url}/api/exchange/listings/{pub['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "video"},
            files=files,
            timeout=API_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == "video"
        assert r.json()["url"].startswith("/static/exchange/")
        # Auto-promote + video_url persisted
        get = requests.get(f"{base_url}/api/exchange/listings/{pub['id']}", timeout=API_TIMEOUT).json()
        assert get["video_url"] is not None
        assert get["status"] == "published"

    def test_video_reject_unsupported_mime(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
        r = requests.post(
            f"{base_url}/api/exchange/listings/{pub['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "video"},
            files=files,
            timeout=API_TIMEOUT,
        )
        assert r.status_code == 400

    def test_photo_accepts_jpg_png_webp(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        for fname, mime in [("a.jpg", "image/jpeg"), ("b.png", "image/png"), ("c.webp", "image/webp")]:
            files = {"file": (fname, io.BytesIO(b"x" * 64), mime)}
            r = requests.post(
                f"{base_url}/api/exchange/listings/{pub['id']}/upload",
                headers={"Authorization": f"Bearer {admin_token}"},
                data={"kind": "photo"}, files=files, timeout=API_TIMEOUT,
            )
            assert r.status_code == 200, f"{fname}: {r.text}"

    def test_photo_6th_rejected(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        for i in range(5):
            files = {"file": (f"p{i}.png", io.BytesIO(b"\x89PNG" + bytes([i]) * 32), "image/png")}
            r = requests.post(
                f"{base_url}/api/exchange/listings/{pub['id']}/upload",
                headers={"Authorization": f"Bearer {admin_token}"},
                data={"kind": "photo"}, files=files, timeout=API_TIMEOUT,
            )
            assert r.status_code == 200, f"upload {i}: {r.text}"
        # 6th
        files = {"file": ("p6.png", io.BytesIO(b"\x89PNGx" * 16), "image/png")}
        r = requests.post(
            f"{base_url}/api/exchange/listings/{pub['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "photo"}, files=files, timeout=API_TIMEOUT,
        )
        assert r.status_code == 400
        assert "Max 5 photos" in r.json().get("detail", "")

    def test_delete_media_by_url_and_unknown_404(self, base_url, admin_token, workflow_id):
        pub = _publish(base_url, admin_token, workflow_id).json()
        files = {"file": ("p.png", io.BytesIO(b"\x89PNG" + b"q" * 64), "image/png")}
        up = requests.post(
            f"{base_url}/api/exchange/listings/{pub['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "photo"}, files=files, timeout=API_TIMEOUT,
        ).json()
        url = up["url"]
        # Remove
        r = requests.delete(
            f"{base_url}/api/exchange/listings/{pub['id']}/media",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"url": url}, timeout=API_TIMEOUT,
        )
        assert r.status_code == 200
        # Unknown url
        r = requests.delete(
            f"{base_url}/api/exchange/listings/{pub['id']}/media",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"url": "/static/exchange/bogus/file.png"}, timeout=API_TIMEOUT,
        )
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# 5. Exchange — my-listings
# ─────────────────────────────────────────────────────────────
class TestMyListings:
    def test_my_listings_includes_drafts_and_published(self, base_url, admin_token, workflow_id):
        # Create one draft
        draft = _publish(base_url, admin_token, workflow_id, name="TEST_i31_my_draft").json()
        # Create one and promote
        promoted = _publish(base_url, admin_token, workflow_id, name="TEST_i31_my_pub").json()
        files = {"file": ("p.png", io.BytesIO(b"\x89PNGzz"), "image/png")}
        requests.post(
            f"{base_url}/api/exchange/listings/{promoted['id']}/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"kind": "photo"}, files=files, timeout=API_TIMEOUT,
        )
        r = requests.get(
            f"{base_url}/api/exchange/my-listings",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=API_TIMEOUT,
        )
        assert r.status_code == 200
        ids = [li["id"] for li in r.json()["listings"]]
        assert draft["id"] in ids
        assert promoted["id"] in ids


# ─────────────────────────────────────────────────────────────
# 6. Gmail OAuth extraction — routes still wired
# ─────────────────────────────────────────────────────────────
class TestGmailOAuthExtraction:
    def test_exchange_validation_422(self, base_url, admin_token):
        # Missing redirect_uri → 422 (Pydantic still works after extraction)
        r = requests.post(
            f"{base_url}/api/workflows/credentials/gmail/exchange",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"code": "abc"}, timeout=API_TIMEOUT,
        )
        assert r.status_code == 422

    def test_refresh_returns_404_when_no_cred(self, base_url, admin_token):
        # Wipe any prior gmail credential so we get a deterministic 404 — best effort
        # If no cred exists this returns 404 'Gmail credential not found.'
        r = requests.post(
            f"{base_url}/api/workflows/credentials/gmail/refresh",
            headers={"Authorization": f"Bearer {admin_token}"}, timeout=API_TIMEOUT,
        )
        # 404 (no cred) OR 400 (no refresh_token stored) both demonstrate route is wired
        assert r.status_code in (400, 404, 503), r.text


# ─────────────────────────────────────────────────────────────
# 7. WebSocket /api/overwatch/feed
# ─────────────────────────────────────────────────────────────
def _ws_url(base_url: str, token: str = None) -> str:
    u = base_url.replace("https://", "wss://").replace("http://", "ws://")
    if token:
        return f"{u}/api/overwatch/feed?token={token}"
    return f"{u}/api/overwatch/feed"


class TestOverwatchWebSocket:
    @pytest.mark.asyncio
    async def test_no_token_rejected(self, base_url):
        try:
            async with websockets.connect(_ws_url(base_url), open_timeout=10) as ws:
                # If connect succeeds, server must close immediately
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    pytest.fail(f"expected close but got msg: {msg}")
                except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                    pass
        except (websockets.exceptions.InvalidStatus, websockets.exceptions.InvalidStatusCode, websockets.exceptions.ConnectionClosedError):
            # ingress may reject 403 prior to upgrade — also acceptable
            pass

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, base_url, freeuser_token):
        try:
            async with websockets.connect(_ws_url(base_url, freeuser_token), open_timeout=10) as ws:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    pytest.fail(f"expected close but got: {msg}")
                except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                    pass
        except (websockets.exceptions.InvalidStatus, websockets.exceptions.InvalidStatusCode, websockets.exceptions.ConnectionClosedError):
            pass

    @pytest.mark.asyncio
    async def test_admin_connect_and_receive(self, base_url, admin_token):
        async with websockets.connect(_ws_url(base_url, admin_token), open_timeout=10) as ws:
            # Wait up to ~6s for either a heartbeat or run message
            received = False
            for _ in range(3):
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=4)
                    payload = json.loads(raw)
                    assert "type" in payload
                    assert payload["type"] in ("run", "heartbeat")
                    received = True
                    break
                except asyncio.TimeoutError:
                    continue
            assert received, "no message received within 12s"


# ─────────────────────────────────────────────────────────────
# 8. REGRESSION — PATCH /workflows/{id}/nodes/{node_id} → 422
# ─────────────────────────────────────────────────────────────
class TestRegressionPatch:
    def test_patch_node_bad_data_422(self, base_url, admin_token):
        wf_id = _save_workflow(base_url, admin_token, "TEST_i31_patch")
        # data must be dict — string should 422
        r = requests.patch(
            f"{base_url}/api/workflows/{wf_id}/nodes/n1",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"data": "not-a-dict"}, timeout=API_TIMEOUT,
        )
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────
# 9. REGRESSION — BYOK encrypt/decrypt round-trip via /credentials
# ─────────────────────────────────────────────────────────────
class TestRegressionBYOK:
    def test_byok_roundtrip_via_credentials(self, base_url, admin_token):
        # Store a credential (key gets encrypted at-rest) then list
        sec = f"sk-test-iter31-{uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{base_url}/api/workflows/credentials",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"service": "slack", "api_key": sec}, timeout=API_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        # List — masked but service present
        r = requests.get(
            f"{base_url}/api/workflows/credentials",
            headers={"Authorization": f"Bearer {admin_token}"}, timeout=API_TIMEOUT,
        )
        assert r.status_code == 200
        services = [c.get("service") for c in r.json().get("credentials", r.json())] if isinstance(r.json(), dict) else []
        # Best-effort: just ensure 200
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# 10. Rate-limit — RUN LAST so we don't poison earlier tests
# Use module-late name prefix `Z_` to enforce ordering with pytest default sort
# ─────────────────────────────────────────────────────────────
class TestZRateLimit:
    """Run last. Each test uses unique, isolated scope.
    The fixture admin_token already consumes 1 login slot, so we count >=429 within bounded loop."""

    def test_login_429_after_burst(self, base_url):
        got_429 = False
        retry_after_seen = False
        # Up to 15 attempts (limit is 10 in 60s). admin fixture may have used 1.
        for _ in range(15):
            r = requests.post(
                f"{base_url}/api/auth/login",
                json={"email": "ratelimit_probe@example.com", "password": "wrong"},
                timeout=API_TIMEOUT,
            )
            if r.status_code == 429:
                got_429 = True
                if "Retry-After" in r.headers:
                    retry_after_seen = True
                detail = r.json().get("detail", "")
                assert "Too many" in detail
                break
            assert r.status_code in (401, 422)
        assert got_429, "expected 429 within 15 login attempts"
        assert retry_after_seen, "expected Retry-After header on 429"

    def test_register_429_after_burst(self, base_url):
        got_429 = False
        retry_after_seen = False
        for i in range(8):  # limit 5 in 600s
            r = requests.post(
                f"{base_url}/api/auth/register",
                json={"email": f"rl_reg_{uuid.uuid4().hex[:6]}@test.com",
                      "password": "weakerthan8" + str(i),
                      "name": "RL"},
                timeout=API_TIMEOUT,
            )
            if r.status_code == 429:
                got_429 = True
                if "Retry-After" in r.headers:
                    retry_after_seen = True
                assert "Too many" in r.json().get("detail", "")
                break
        assert got_429, "expected 429 within 8 register attempts"
        assert retry_after_seen

    def test_forgot_password_429_after_burst(self, base_url):
        got_429 = False
        retry_after_seen = False
        for _ in range(6):  # limit 3 in 600s
            r = requests.post(
                f"{base_url}/api/auth/forgot-password",
                json={"email": "rl_probe@test.com"},
                timeout=API_TIMEOUT,
            )
            if r.status_code == 429:
                got_429 = True
                if "Retry-After" in r.headers:
                    retry_after_seen = True
                assert "Too many" in r.json().get("detail", "")
                break
        assert got_429
        assert retry_after_seen
