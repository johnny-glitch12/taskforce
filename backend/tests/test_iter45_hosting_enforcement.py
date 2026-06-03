"""
Iter45 — Hosting quota enforcement on exchange.publish + hosting-subscription
janitor (expire_lapsed_subscriptions).

Validates:
  - PUT /api/exchange/listings/{id} with status:'published' returns 402 when
    the creator has NO hosting subscription.
  - Same call returns 200 + flips the listing to 'published' AND bumps
    agents_used by 1 when the creator has an active sub under cap.
  - A SECOND publish hitting the cap returns 403 with reason='agent_cap'.
  - Transitioning a published listing back to 'draft' (or deleting it)
    decrements agents_used + pulls listing_id from agents_published.
  - expire_lapsed_subscriptions flips cancelled rows past their period_end
    to 'expired'.
  - Admin users bypass quota enforcement but still get a counter bump.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

sys.path.insert(0, "/app/backend")
from routes import hosting as hosting_mod  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"
USER_EMAIL = "freeuser@test.com"
USER_PASS = "test123"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


def _run(coro_factory):
    """Per-call Motor client (Motor binds to constructing loop)."""
    import asyncio as _aio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def _main():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            return await coro_factory(db)
        finally:
            client.close()
    return _aio.run(_main())


@pytest.fixture(scope="module")
def token():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert t, "admin login must succeed"
    return t


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def user_auth():
    """Non-admin user — used for the quota-blocked tests since admin bypasses."""
    t = _login(USER_EMAIL, USER_PASS)
    assert t, "freeuser login must succeed"
    return {"Authorization": f"Bearer {t}"}


def _user_id_for(email: str) -> str:
    return _run(lambda db: db.users.find_one({"email": email}, {"id": 1}))["id"]


def _seed_active_sub(tier: str = "starter", email: str = ADMIN_EMAIL) -> str:
    """Insert an active hosting subscription for the given user at the given tier.
    Returns sub_id. Supersedes any prior active row first."""
    async def _flow(db):
        user = await db.users.find_one({"email": email}, {"id": 1})
        creator_id = user["id"]
        await db.hosting_subscriptions.update_many(
            {"creator_id": creator_id, "status": "active"},
            {"$set": {"status": "superseded"}},
        )
        sub_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        await db.hosting_subscriptions.insert_one({
            "id": sub_id,
            "creator_id": creator_id,
            "creator_email": email,
            "tier": tier,
            "status": "active",
            "stripe_session_id": "manual_iter45",
            "payment_id": "manual_iter45",
            "amount": hosting_mod.HOSTING_TIERS[tier]["price"],
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "executions_used": 0,
            "agents_used": 0,
            "agents_published": [],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
        return sub_id
    return _run(_flow)


def _clear_subs(email: str = None):
    async def _flow(db):
        q = {"creator_email": email} if email else {}
        await db.hosting_subscriptions.delete_many(q)
    _run(_flow)


def _make_draft_listing(auth_headers) -> str:
    """Create a draft listing via /exchange/listings/direct. Returns listing_id."""
    body = {
        "name": f"iter45-{uuid.uuid4().hex[:6]}",
        "description": "Iter45 enforcement test listing.",
        "category": "automation",
        "tags": ["test"],
        "rent_price": 1.0,
        "buy_price": 10.0,
        "avatar_icon": "rocket",
        "avatar_color": "#22d3ee",
        "required_integrations": [],
        "trigger_type": "manual",
        "engine": "gemini-flash",
        "files": [{"path": "main.py", "language": "python",
                   "content": "def run(input):\n    return {'ok': True}\n"}],
        "nodes": [{"id": "n1", "type": "noop"}],
        "edges": [],
        "language": "python",
    }
    r = requests.post(f"{BASE_URL}/api/exchange/listings/direct",
                      headers=auth_headers, json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _delete_listing(auth_headers, listing_id: str):
    requests.delete(f"{BASE_URL}/api/exchange/listings/{listing_id}",
                    headers=auth_headers, timeout=10)


# ── Tests ───────────────────────────────────────────────────────────────────
def test_publish_blocked_without_subscription(user_auth):
    """Non-admin user without a hosting subscription — 402 NO_HOSTING_PLAN on publish."""
    _clear_subs(email=USER_EMAIL)
    listing_id = _make_draft_listing(user_auth)
    try:
        r = requests.put(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=user_auth, json={"status": "published"}, timeout=10,
        )
        assert r.status_code == 402, r.text
        body = r.json()
        detail = body.get("detail", body)
        assert detail.get("error") == "NO_HOSTING_PLAN", detail
        assert "/hosting" in detail.get("upgrade_url", "")
    finally:
        _delete_listing(user_auth, listing_id)


def test_publish_succeeds_under_cap_and_increments(auth):
    """With an active starter sub (cap=1, used=0) publish succeeds AND bumps counter."""
    sub_id = _seed_active_sub("starter")
    listing_id = _make_draft_listing(auth)
    try:
        r = requests.put(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=auth, json={"status": "published"}, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "published"
        sub = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
        assert sub["agents_used"] == 1
        assert listing_id in sub["agents_published"]
    finally:
        _delete_listing(auth, listing_id)
        _clear_subs()


def test_publish_blocked_when_cap_hit(user_auth):
    """Starter cap=1: first publish OK, second publish 403 agent_cap (non-admin)."""
    sub_id = _seed_active_sub("starter", email=USER_EMAIL)
    a_id = _make_draft_listing(user_auth)
    b_id = _make_draft_listing(user_auth)
    try:
        r1 = requests.put(
            f"{BASE_URL}/api/exchange/listings/{a_id}",
            headers=user_auth, json={"status": "published"}, timeout=10,
        )
        assert r1.status_code == 200, r1.text
        r2 = requests.put(
            f"{BASE_URL}/api/exchange/listings/{b_id}",
            headers=user_auth, json={"status": "published"}, timeout=10,
        )
        assert r2.status_code == 403, r2.text
        detail = r2.json().get("detail", {})
        assert detail.get("error") == "agent_cap"
        assert detail.get("max_agents") == 1
        # B should still be a draft.
        b = _run(lambda db: db.exchange_listings.find_one({"id": b_id}))
        assert b["status"] == "draft"
    finally:
        _delete_listing(user_auth, a_id)
        _delete_listing(user_auth, b_id)
        _clear_subs(email=USER_EMAIL)


def test_delete_published_releases_quota(auth):
    """Deleting a published listing decrements agents_used + pulls from set."""
    sub_id = _seed_active_sub("pro")  # cap=3
    listing_id = _make_draft_listing(auth)
    try:
        r = requests.put(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=auth, json={"status": "published"}, timeout=10,
        )
        assert r.status_code == 200
        sub = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
        assert sub["agents_used"] == 1
        # Now delete.
        d = requests.delete(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=auth, timeout=10,
        )
        assert d.status_code == 200
        sub2 = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
        assert sub2["agents_used"] == 0
        assert listing_id not in (sub2.get("agents_published") or [])
    finally:
        _clear_subs()


def test_delist_releases_quota(auth):
    """PUT status=draft on a published listing also releases the slot."""
    sub_id = _seed_active_sub("pro")
    listing_id = _make_draft_listing(auth)
    try:
        r = requests.put(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=auth, json={"status": "published"}, timeout=10,
        )
        assert r.status_code == 200
        sub = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
        assert sub["agents_used"] == 1
        r2 = requests.put(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=auth, json={"status": "draft"}, timeout=10,
        )
        assert r2.status_code == 200
        sub2 = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
        assert sub2["agents_used"] == 0
    finally:
        _delete_listing(auth, listing_id)
        _clear_subs()


def test_expire_lapsed_subscriptions_helper():
    """Insert a cancelled sub with period_end in the past; janitor flips it to 'expired'."""
    async def _seed(db):
        user = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1})
        creator_id = user["id"]
        # Cancelled sub past its period end.
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        sub_id = uuid.uuid4().hex
        await db.hosting_subscriptions.insert_one({
            "id": sub_id,
            "creator_id": creator_id,
            "creator_email": ADMIN_EMAIL,
            "tier": "starter",
            "status": "cancelled",
            "stripe_session_id": "iter45_janitor",
            "payment_id": "iter45_janitor",
            "amount": 9.0,
            "current_period_start": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "current_period_end": past,
            "executions_used": 0,
            "agents_used": 0,
            "agents_published": [],
            "cancelled_at": past,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "updated_at": past,
        })
        # Active sub also past period end.
        sub_id2 = uuid.uuid4().hex
        await db.hosting_subscriptions.insert_one({
            "id": sub_id2,
            "creator_id": creator_id + "_other",  # different creator to keep test idempotent
            "creator_email": "other@test.com",
            "tier": "pro",
            "status": "active",
            "stripe_session_id": "iter45_janitor2",
            "payment_id": "iter45_janitor2",
            "amount": 29.0,
            "current_period_start": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "current_period_end": past,
            "executions_used": 0,
            "agents_used": 0,
            "agents_published": [],
            "created_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "updated_at": past,
        })
        # And a NEW sub (period_end in the future) — must NOT be touched.
        sub_id3 = uuid.uuid4().hex
        future = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
        await db.hosting_subscriptions.insert_one({
            "id": sub_id3,
            "creator_id": creator_id + "_fresh",
            "creator_email": "fresh@test.com",
            "tier": "starter",
            "status": "active",
            "stripe_session_id": "iter45_janitor3",
            "payment_id": "iter45_janitor3",
            "amount": 9.0,
            "current_period_start": datetime.now(timezone.utc).isoformat(),
            "current_period_end": future,
            "executions_used": 0,
            "agents_used": 0,
            "agents_published": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return sub_id, sub_id2, sub_id3
    sub_id, sub_id2, sub_id3 = _run(_seed)
    # Run the janitor.
    flipped = _run(lambda db: hosting_mod.expire_lapsed_subscriptions(db))
    assert flipped >= 2
    # Assert correct states.
    a = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
    b = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id2}))
    c = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id3}))
    assert a["status"] == "expired"
    assert "expired_at" in a
    assert b["status"] == "expired"
    assert c["status"] == "active", "fresh sub must not be expired"
    # Cleanup
    _run(lambda db: db.hosting_subscriptions.delete_many(
        {"id": {"$in": [sub_id, sub_id2, sub_id3]}},
    ))


def test_publish_blocked_when_sub_expired(user_auth):
    """Expired sub should be treated as 'no subscription' — publish 402 (non-admin)."""
    sub_id = _seed_active_sub("starter", email=USER_EMAIL)
    _run(lambda db: db.hosting_subscriptions.update_one(
        {"id": sub_id}, {"$set": {"status": "expired"}},
    ))
    listing_id = _make_draft_listing(user_auth)
    try:
        r = requests.put(
            f"{BASE_URL}/api/exchange/listings/{listing_id}",
            headers=user_auth, json={"status": "published"}, timeout=10,
        )
        assert r.status_code == 402, r.text
    finally:
        _delete_listing(user_auth, listing_id)
        _clear_subs(email=USER_EMAIL)


def test_decrement_agents_helper():
    """Direct call to decrement_agents — idempotent removal from $addToSet."""
    sub_id = _seed_active_sub("growth")
    listing_a = "list-a-iter45"
    listing_b = "list-b-iter45"

    async def _setup(db):
        user = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1})
        creator_id = user["id"]
        # Manually push 2 listings + agents_used=2
        await db.hosting_subscriptions.update_one(
            {"id": sub_id},
            {"$set": {"agents_used": 2, "agents_published": [listing_a, listing_b]}},
        )
        return creator_id
    creator_id = _run(_setup)

    # First decrement removes one
    _run(lambda db: hosting_mod.decrement_agents(db, creator_id, listing_a))
    sub = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
    assert sub["agents_used"] == 1
    assert sub["agents_published"] == [listing_b]
    # Second decrement of the SAME listing — idempotent, no change
    _run(lambda db: hosting_mod.decrement_agents(db, creator_id, listing_a))
    sub2 = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
    assert sub2["agents_used"] == 1
    _clear_subs()


def test_admin_role_bypasses_quota_but_counter_increments(auth):
    """Admin should be allowed to publish even at-cap, but the counter still bumps."""
    sub_id = _seed_active_sub("starter")  # cap=1
    a_id = _make_draft_listing(auth)
    b_id = _make_draft_listing(auth)
    try:
        r1 = requests.put(
            f"{BASE_URL}/api/exchange/listings/{a_id}",
            headers=auth, json={"status": "published"}, timeout=10,
        )
        assert r1.status_code == 200
        # Admin attempts a SECOND publish — should succeed (bypass cap).
        r2 = requests.put(
            f"{BASE_URL}/api/exchange/listings/{b_id}",
            headers=auth, json={"status": "published"}, timeout=10,
        )
        assert r2.status_code == 200, r2.text
        sub = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
        assert sub["agents_used"] == 2
    finally:
        _delete_listing(auth, a_id)
        _delete_listing(auth, b_id)
        _clear_subs()
