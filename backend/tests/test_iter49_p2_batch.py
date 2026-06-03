"""
Iter49 P2 batch tests:
  1. Scheduled executions (PUT/GET schedule, tick_scheduled_runs)
  2. Reviews & ratings (CRUD + reply + aggregates)
  3. Creator earnings (summary/ledger/CSV)
  4. Public API keys (mint/list/revoke)
  5. Public API auth + rate limit
"""
import os
import re
import time
import uuid
import asyncio
import pytest
import requests

ADMIN_DEPLOYMENT_ID = "9736667a4a2a4acca927acfb8de48a9c"


# ────────────────────────── 1. Scheduled executions ──────────────────────────
class TestSchedules:
    def test_get_schedule_owner(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "schedule" in d
        assert isinstance(d.get("presets"), list)
        assert len(d["presets"]) == 4
        ids = {p["id"] for p in d["presets"]}
        assert ids == {"hourly", "6h", "daily", "weekly"}

    def test_get_schedule_nonowner(self, base_url, freeuser_client):
        r = freeuser_client.get(f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule")
        assert r.status_code == 404

    def test_put_schedule_daily_then_disable(self, base_url, admin_client):
        # enable daily
        r = admin_client.put(
            f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule",
            json={"enabled": True, "preset": "daily"},
        )
        assert r.status_code == 200, r.text
        s = r.json()["schedule"]
        assert s["enabled"] is True
        assert s["preset"] == "daily"
        assert s["interval_minutes"] == 60 * 24
        assert s["next_run_at"]
        # disable
        r2 = admin_client.put(
            f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule",
            json={"enabled": False},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["schedule"]["enabled"] is False

    def test_put_schedule_no_preset_when_enabled(self, base_url, admin_client):
        r = admin_client.put(
            f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule",
            json={"enabled": True},
        )
        assert r.status_code == 422

    def test_put_schedule_invalid_preset(self, base_url, admin_client):
        r = admin_client.put(
            f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule",
            json={"enabled": True, "preset": "every_minute"},
        )
        assert r.status_code == 422

    def test_tick_scheduled_runs_direct(self, admin_client, base_url):
        """Set next_run_at to past, call tick_scheduled_runs directly."""
        from motor.motor_asyncio import AsyncIOMotorClient
        from datetime import datetime, timezone, timedelta
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from routes.schedules import tick_scheduled_runs

        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]

        async def run_check():
            # First, ensure schedule is enabled with daily
            admin_client.put(
                f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule",
                json={"enabled": True, "preset": "daily"},
            )
            # Force next_run_at to past
            past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            await db.user_bot_deployments.update_one(
                {"id": ADMIN_DEPLOYMENT_ID},
                {"$set": {"schedule.next_run_at": past}},
            )
            dispatched = await tick_scheduled_runs(db)
            doc = await db.user_bot_deployments.find_one({"id": ADMIN_DEPLOYMENT_ID})
            sched = doc.get("schedule", {})
            return dispatched, sched

        dispatched, sched = asyncio.get_event_loop().run_until_complete(run_check())
        # Either dispatched >= 1 OR auto-disabled due to limit. Either is acceptable per spec.
        assert dispatched >= 1 or sched.get("enabled") is False, f"dispatched={dispatched} sched={sched}"
        if dispatched >= 1:
            assert sched.get("last_run_id"), sched
            # next_run_at must be in future
            from datetime import datetime as dt
            nr = dt.fromisoformat(sched["next_run_at"])
            assert nr > dt.now(timezone.utc), sched

        # cleanup
        admin_client.put(
            f"{base_url}/api/deployments/{ADMIN_DEPLOYMENT_ID}/schedule",
            json={"enabled": False},
        )


# ────────────────────────── 2. Reviews ──────────────────────────
@pytest.fixture(scope="module")
def test_listing(base_url, freeuser_client):
    """Create a listing OWNED BY freeuser so admin can review it."""
    # Try minimal payload first
    payload = {
        "name": "TEST_iter49_review_listing",
        "description": "An agent for iter49 review testing flows.",
        "category": "data",
        "tags": ["test", "iter49"],
        "rent_price": 9.99,
        "buy_price": 99.0,
    }
    r = freeuser_client.post(f"{base_url}/api/exchange/listings/direct", json=payload)
    if r.status_code not in (200, 201):
        pytest.skip(f"listing create failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    listing = data.get("listing") or data
    lid = listing.get("id")
    if not lid:
        pytest.skip(f"no listing id: {data}")
    yield lid
    freeuser_client.delete(f"{base_url}/api/exchange/listings/{lid}")


class TestReviews:
    def test_create_review_admin(self, base_url, admin_client, test_listing):
        # Clean prior review if any
        admin_client.delete(f"{base_url}/api/exchange/listings/{test_listing}/reviews/my-review")
        r = admin_client.post(
            f"{base_url}/api/exchange/listings/{test_listing}/reviews",
            json={"stars": 5, "comment": "great agent works well"},
        )
        # If duplicate from prior run, delete and retry
        if r.status_code == 409:
            mine = admin_client.get(f"{base_url}/api/exchange/listings/{test_listing}/reviews/my-review").json()
            if mine.get("review", {}).get("id"):
                admin_client.delete(f"{base_url}/api/exchange/reviews/{mine['review']['id']}")
            r = admin_client.post(
                f"{base_url}/api/exchange/listings/{test_listing}/reviews",
                json={"stars": 5, "comment": "great agent works well"},
            )
        assert r.status_code == 200, r.text
        rev = r.json()["review"]
        assert rev["stars"] == 5
        assert "id" in rev

    def test_list_reviews_aggregate(self, base_url, admin_client, test_listing):
        r = admin_client.get(f"{base_url}/api/exchange/listings/{test_listing}/reviews")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "aggregate" in d and "histogram" in d
        assert d["aggregate"]["reviews_count"] >= 1
        assert set(d["histogram"].keys()) == {"1", "2", "3", "4", "5"}

    def test_owner_cannot_review_own(self, base_url, freeuser_client, test_listing):
        r = freeuser_client.post(
            f"{base_url}/api/exchange/listings/{test_listing}/reviews",
            json={"stars": 4, "comment": "self review attempt"},
        )
        assert r.status_code == 403

    def test_duplicate_review(self, base_url, admin_client, test_listing):
        r = admin_client.post(
            f"{base_url}/api/exchange/listings/{test_listing}/reviews",
            json={"stars": 4, "comment": "second time attempt"},
        )
        assert r.status_code == 409

    def test_short_comment_422(self, base_url, freeuser_client, test_listing):
        # Use another fresh listing owned by admin so freeuser can review
        # Instead just try short on the same listing with a NEW user not avail — use freeuser; will hit 403 for own listing.
        # We test the 422 with admin on a separate path: create a new listing by admin and have freeuser review.
        # Simpler: validate the schema by creating with stars only
        r = freeuser_client.post(
            f"{base_url}/api/exchange/listings/{test_listing}/reviews",
            json={"stars": 5, "comment": "short"},
        )
        # Either 422 (pydantic) or 403 (own listing). Spec says 422 — but owner check may run first.
        # The reviews route: schema validation happens before handler, so should be 422.
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"

    def test_reply_flow(self, base_url, admin_client, freeuser_client, test_listing):
        # Get the review id by admin
        my = admin_client.get(f"{base_url}/api/exchange/listings/{test_listing}/reviews/my-review").json()
        rid = my["review"]["id"]
        # Non-owner (admin is reviewer, not listing owner) can't reply
        r1 = admin_client.post(
            f"{base_url}/api/exchange/reviews/{rid}/reply",
            json={"content": "thanks for the kind review"},
        )
        assert r1.status_code == 403
        # Owner (freeuser) replies
        r2 = freeuser_client.post(
            f"{base_url}/api/exchange/reviews/{rid}/reply",
            json={"content": "thanks for the kind review"},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["review"]["owner_reply"]
        # Second reply 409
        r3 = freeuser_client.post(
            f"{base_url}/api/exchange/reviews/{rid}/reply",
            json={"content": "another reply"},
        )
        assert r3.status_code == 409

    def test_delete_review_by_author(self, base_url, admin_client, test_listing):
        my = admin_client.get(f"{base_url}/api/exchange/listings/{test_listing}/reviews/my-review").json()
        rid = my["review"]["id"]
        r = admin_client.delete(f"{base_url}/api/exchange/reviews/{rid}")
        assert r.status_code == 200, r.text
        # Aggregate should drop
        agg = admin_client.get(f"{base_url}/api/exchange/listings/{test_listing}/reviews").json()
        assert agg["aggregate"]["reviews_count"] == 0


# ────────────────────────── 3. Creator earnings ──────────────────────────
class TestCreatorEarnings:
    def test_summary_shape(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/creator/earnings/summary?days=30")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["window_days"] == 30
        w = d["window"]
        for k in ("usd_total", "stripe_usd", "cash_bounty_usd", "credit_bounty_total", "deploy_runs"):
            assert k in w, f"missing {k} in window: {w}"
        lt = d["lifetime"]
        for k in ("usd_total", "stripe_usd", "cash_bounty_usd", "credit_bounty_total"):
            assert k in lt, f"missing {k} in lifetime: {lt}"

    def test_summary_days_clamping(self, base_url, admin_client):
        r0 = admin_client.get(f"{base_url}/api/creator/earnings/summary?days=0")
        assert r0.status_code == 422
        r366 = admin_client.get(f"{base_url}/api/creator/earnings/summary?days=366")
        assert r366.status_code == 422

    def test_ledger(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/creator/earnings/ledger?limit=50")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("items", "total", "limit", "skip"):
            assert k in d
        assert d["limit"] == 50

    def test_export_csv(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/creator/earnings/export.csv")
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "created_at,kind,label,amount,currency,ref" in r.text


# ────────────────────────── 4. Public API keys ──────────────────────────
class TestApiKeys:
    minted_key = None
    minted_id = None
    plaintext = None

    def test_mint_key_format(self, base_url, admin_client):
        r = admin_client.post(f"{base_url}/api/keys", json={"name": "TEST_iter49"})
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("id", "name", "key", "key_prefix", "warning"):
            assert k in d
        # tfai_ + 64 hex
        assert re.match(r"^tfai_[a-f0-9]{64}$", d["key"]), d["key"]
        TestApiKeys.minted_key = d["key"]
        TestApiKeys.minted_id = d["id"]

    def test_list_keys_no_secrets(self, base_url, admin_client):
        r = admin_client.get(f"{base_url}/api/keys")
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert any(k["id"] == TestApiKeys.minted_id for k in items)
        for k in items:
            assert "key_hash" not in k
            assert "key" not in k  # no plaintext

    def test_mint_empty_name_defaults(self, base_url, admin_client):
        r = admin_client.post(f"{base_url}/api/keys", json={"name": "   "})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Untitled key"
        # cleanup
        admin_client.delete(f"{base_url}/api/keys/{r.json()['id']}")

    def test_revoke_key(self, base_url, admin_client):
        # mint a fresh key to revoke
        m = admin_client.post(f"{base_url}/api/keys", json={"name": "TEST_revoke_me"}).json()
        r = admin_client.delete(f"{base_url}/api/keys/{m['id']}")
        assert r.status_code == 200, r.text
        # revoke twice → 404
        r2 = admin_client.delete(f"{base_url}/api/keys/{m['id']}")
        assert r2.status_code == 404


# ────────────────────────── 5. Public API auth + rate limit ──────────────────────────
class TestPublicAPI:
    def test_missing_key(self, base_url):
        r = requests.post(
            f"{base_url}/api/public/v1/deployments/{ADMIN_DEPLOYMENT_ID}/run",
            json={}, timeout=15,
        )
        assert r.status_code == 401
        body = r.json()
        # FastAPI wraps detail
        detail = body.get("detail") or {}
        if isinstance(detail, dict):
            assert detail.get("error") == "MISSING_API_KEY"

    def test_invalid_key(self, base_url):
        r = requests.post(
            f"{base_url}/api/public/v1/deployments/{ADMIN_DEPLOYMENT_ID}/run",
            headers={"X-API-Key": "tfai_invalidkey"},
            json={}, timeout=15,
        )
        assert r.status_code == 401
        detail = r.json().get("detail") or {}
        if isinstance(detail, dict):
            assert detail.get("error") == "INVALID_API_KEY"

    def test_valid_key_run(self, base_url, admin_client):
        # mint a fresh key for these tests
        m = admin_client.post(f"{base_url}/api/keys", json={"name": "TEST_iter49_pub"}).json()
        key = m["key"]
        key_id = m["id"]
        try:
            r = requests.post(
                f"{base_url}/api/public/v1/deployments/{ADMIN_DEPLOYMENT_ID}/run",
                headers={"X-API-Key": key},
                json={"input": {}}, timeout=60,
            )
            assert r.status_code == 200, r.text
            d = r.json()
            assert "run_id" in d
            assert "success" in d
            assert "duration_ms" in d
        finally:
            admin_client.delete(f"{base_url}/api/keys/{key_id}")

    def test_run_wrong_owner(self, base_url, freeuser_client):
        """Free user's key cannot access admin's deployment."""
        m = freeuser_client.post(f"{base_url}/api/keys", json={"name": "TEST_free"}).json()
        try:
            key = m["key"]
            r = requests.post(
                f"{base_url}/api/public/v1/deployments/{ADMIN_DEPLOYMENT_ID}/run",
                headers={"X-API-Key": key},
                json={}, timeout=15,
            )
            assert r.status_code == 404
            detail = r.json().get("detail") or {}
            if isinstance(detail, dict):
                assert detail.get("error") == "DEPLOYMENT_NOT_FOUND"
        finally:
            freeuser_client.delete(f"{base_url}/api/keys/{m['id']}")

    def test_list_runs(self, base_url, admin_client):
        m = admin_client.post(f"{base_url}/api/keys", json={"name": "TEST_iter49_runs"}).json()
        try:
            r = requests.get(
                f"{base_url}/api/public/v1/deployments/{ADMIN_DEPLOYMENT_ID}/runs?limit=10",
                headers={"X-API-Key": m["key"]}, timeout=15,
            )
            assert r.status_code == 200, r.text
            d = r.json()
            for k in ("items", "total", "limit", "skip"):
                assert k in d
        finally:
            admin_client.delete(f"{base_url}/api/keys/{m['id']}")

    def test_rate_limit(self, base_url, admin_client):
        """61st call within 60s window should 429.
        Use the lightweight GET /runs to avoid running real bots.
        """
        m = admin_client.post(f"{base_url}/api/keys", json={"name": "TEST_iter49_rl"}).json()
        try:
            key = m["key"]
            url = f"{base_url}/api/public/v1/deployments/{ADMIN_DEPLOYMENT_ID}/runs?limit=1"
            session = requests.Session()
            session.headers.update({"X-API-Key": key})
            statuses = []
            for i in range(61):
                try:
                    s = session.get(url, timeout=10).status_code
                except Exception:
                    s = 0
                statuses.append(s)
                if s == 429:
                    break
            assert 429 in statuses, f"expected 429 within 61 calls, got: {statuses[-5:]}"
        finally:
            admin_client.delete(f"{base_url}/api/keys/{m['id']}")
