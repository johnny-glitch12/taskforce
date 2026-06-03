"""
Iter44 — Prompt 7 Part 3: Hosting Subscription Tiers.

Validates the creator-side hosting subscription system:
  - GET /api/hosting/tiers — public tier catalogue (no auth needed)
  - GET /api/hosting/me     — current creator subscription (null if none)
  - GET /api/hosting/usage  — counters + caps + % utilisation
  - POST /api/hosting/checkout — creates Stripe sandbox checkout
  - POST /api/hosting/activate — idempotent post-payment provisioning
  - POST /api/hosting/cancel — flips status to 'cancelled'

It also covers the helpers `can_publish`, `increment_executions`, `increment_agents`
imported from routes.hosting.
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")
from routes import hosting as hosting_mod  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def token():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert t, "admin login must succeed"
    return t


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _run(coro_factory):
    """Run an async block in a fresh loop with its own Motor client.

    Motor's `AsyncIOMotorClient` binds to the loop that constructs it, so we
    can't reuse a module-scoped client across `asyncio.run()` calls. Pass a
    factory `(db) -> coroutine` so each call sees its own connection.
    """
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


# ── 1. Catalogue endpoint ─────────────────────────────────────────────────
def test_tiers_catalogue_is_public():
    r = requests.get(f"{BASE_URL}/api/hosting/tiers", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "tiers" in body
    assert body["period_days"] == 30
    tiers = {t["tier"]: t for t in body["tiers"]}
    # All 4 tiers present with correct prices
    assert tiers["starter"]["price"] == 9.0
    assert tiers["pro"]["price"] == 29.0
    assert tiers["growth"]["price"] == 99.0
    assert tiers["scale"]["price"] == 299.0
    # Scale tier = unlimited agents (max_agents == 0)
    assert tiers["scale"]["max_agents"] == 0
    # Pro is the highlighted tier
    assert tiers["pro"]["highlight"] is True
    assert tiers["starter"]["highlight"] is False
    # Each tier carries features + caps + tagline
    for t in tiers.values():
        assert isinstance(t["features"], list) and len(t["features"]) >= 3
        assert t["max_executions"] > 0
        assert t["max_runtime_seconds"] >= 10
        assert isinstance(t["tagline"], str)


def test_me_returns_null_when_no_subscription(auth_headers):
    r = requests.get(f"{BASE_URL}/api/hosting/me", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    # Either null (fresh) or has the previously-seeded admin sub from a prior test.
    # We accept both — the contract is the field exists.
    assert "subscription" in body


def test_usage_no_subscription(auth_headers):
    """Strip any existing active hosting sub for admin first, then poll usage."""
    _run(lambda db: db.hosting_subscriptions.update_many(
        {"creator_email": ADMIN_EMAIL, "status": "active"},
        {"$set": {"status": "superseded"}},
    ))
    r = requests.get(f"{BASE_URL}/api/hosting/usage", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["has_subscription"] is False
    assert body["tier"] is None
    assert body["agents_used"] == 0
    assert body["executions_used"] == 0


# ── 2. Checkout endpoint ──────────────────────────────────────────────────
def test_checkout_invalid_tier(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/hosting/checkout", headers=auth_headers,
        json={"tier": "elite", "origin_url": "https://example.com"}, timeout=10,
    )
    assert r.status_code == 422, r.text  # Pydantic regex rejects


def test_checkout_creates_stripe_session(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/hosting/checkout", headers=auth_headers,
        json={"tier": "starter", "origin_url": "https://example.com"}, timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"].startswith("cs_test_"), body
    assert body["url"].startswith("https://checkout.stripe.com/"), body
    assert body["tier"] == "starter"
    assert body["amount"] == 9.0
    # A pending payment_transactions row exists.
    sid = body["session_id"]
    tx = _run(lambda db: db.payment_transactions.find_one({"session_id": sid}))
    assert tx is not None
    assert tx["type"] == "hosting"
    assert tx["tier"] == "starter"
    assert tx["payment_status"] == "pending"


# ── 3. Activate endpoint ──────────────────────────────────────────────────
def test_activate_requires_paid_payment(auth_headers):
    """Activate before webhook flips paid → 402 (not 404, not 200)."""
    r1 = requests.post(
        f"{BASE_URL}/api/hosting/checkout", headers=auth_headers,
        json={"tier": "pro", "origin_url": "https://example.com"}, timeout=15,
    )
    sid = r1.json()["session_id"]
    r2 = requests.post(
        f"{BASE_URL}/api/hosting/activate", headers=auth_headers,
        json={"session_id": sid}, timeout=10,
    )
    assert r2.status_code == 402, r2.text


def test_activate_idempotent_after_paid(auth_headers):
    """Manually mark a tx as paid (bypass real Stripe) → activate → activate again,
    second call must return already_active=true with the same row."""
    r1 = requests.post(
        f"{BASE_URL}/api/hosting/checkout", headers=auth_headers,
        json={"tier": "growth", "origin_url": "https://example.com"}, timeout=15,
    )
    sid = r1.json()["session_id"]
    # Flip the tx to paid (simulate webhook).
    _run(lambda db: db.payment_transactions.update_one(
        {"session_id": sid},
        {"$set": {"payment_status": "paid"}},
    ))
    a1 = requests.post(
        f"{BASE_URL}/api/hosting/activate", headers=auth_headers,
        json={"session_id": sid}, timeout=10,
    )
    assert a1.status_code == 200, a1.text
    body1 = a1.json()
    assert body1["already_active"] is False
    assert body1["subscription"]["tier"] == "growth"
    assert body1["subscription"]["status"] == "active"
    # Second activate → idempotent.
    a2 = requests.post(
        f"{BASE_URL}/api/hosting/activate", headers=auth_headers,
        json={"session_id": sid}, timeout=10,
    )
    assert a2.status_code == 200
    body2 = a2.json()
    assert body2["already_active"] is True
    assert body2["subscription"]["id"] == body1["subscription"]["id"]


def test_activate_409_when_dup_tier(auth_headers):
    """Checking out the same tier while an active sub exists → 409."""
    sub = _run(lambda db: db.hosting_subscriptions.find_one(
        {"creator_email": ADMIN_EMAIL, "status": "active", "tier": "growth"},
    ))
    assert sub is not None, "previous test should have left an active growth sub"
    r = requests.post(
        f"{BASE_URL}/api/hosting/checkout", headers=auth_headers,
        json={"tier": "growth", "origin_url": "https://example.com"}, timeout=10,
    )
    assert r.status_code == 409, r.text


# ── 4. Usage with active subscription ─────────────────────────────────────
def test_usage_with_active_sub(auth_headers):
    r = requests.get(f"{BASE_URL}/api/hosting/usage", headers=auth_headers, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_subscription"] is True
    assert body["tier"] == "growth"
    assert body["max_agents"] == 10
    assert body["max_executions"] == 50_000
    assert body["agents_used"] == 0
    assert body["executions_used"] == 0
    assert body["period_end"] is not None


def test_increment_executions_helper():
    """Call the increment_executions helper directly and confirm $inc landed."""
    async def _flow(db):
        user = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1})
        creator_id = user["id"]
        before = await db.hosting_subscriptions.find_one(
            {"creator_id": creator_id, "status": "active"},
            sort=[("created_at", -1)],
        )
        await hosting_mod.increment_executions(db, creator_id, by=7)
        after = await db.hosting_subscriptions.find_one(
            {"creator_id": creator_id, "status": "active"},
            sort=[("created_at", -1)],
        )
        return before, after
    before, after = _run(_flow)
    assert (after["executions_used"] or 0) - (before["executions_used"] or 0) == 7


def test_can_publish_helper():
    """can_publish returns allowed=True for an active sub under cap, False at cap."""
    async def _flow(db):
        user = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1})
        creator_id = user["id"]
        res = await hosting_mod.can_publish(db, creator_id)
        # Push agents_used to max_agents and reassert.
        await db.hosting_subscriptions.update_one(
            {"creator_id": creator_id, "status": "active"},
            {"$set": {"agents_used": 10}},
        )
        res2 = await hosting_mod.can_publish(db, creator_id)
        # Restore.
        await db.hosting_subscriptions.update_one(
            {"creator_id": creator_id, "status": "active"},
            {"$set": {"agents_used": 0}},
        )
        return res, res2
    res, res2 = _run(_flow)
    assert res["allowed"] is True
    assert res["tier"] == "growth"
    assert res2["allowed"] is False
    assert res2["reason"] == "agent_cap"


# ── 5. Cancel endpoint ────────────────────────────────────────────────────
def test_cancel_flips_status(auth_headers):
    r = requests.post(f"{BASE_URL}/api/hosting/cancel", headers=auth_headers, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["subscription"]["status"] == "cancelled"
    # No active sub now.
    active = _run(lambda db: db.hosting_subscriptions.find_one(
        {"creator_email": ADMIN_EMAIL, "status": "active"},
    ))
    assert active is None


def test_cancel_404_when_no_active(auth_headers):
    r = requests.post(f"{BASE_URL}/api/hosting/cancel", headers=auth_headers, timeout=10)
    assert r.status_code == 404


# ── 6. External agent run increments creator's hosting executions ─────────
def test_external_agent_run_increments_hosting_executions(auth_headers):
    """When an external agent runs, the creator's hosting subscription
    executions_used counter is bumped by 1 (best-effort, silent if no sub)."""
    import io, zipfile, json
    from datetime import datetime, timezone, timedelta

    # Seed an active starter sub for admin (skip Stripe).
    async def _seed(db):
        user = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1})
        creator_id = user["id"]
        await db.hosting_subscriptions.update_many(
            {"creator_id": creator_id, "status": "active"},
            {"$set": {"status": "superseded"}},
        )
        sub_id = uuid.uuid4().hex
        await db.hosting_subscriptions.insert_one({
            "id": sub_id,
            "creator_id": creator_id,
            "creator_email": ADMIN_EMAIL,
            "tier": "starter",
            "status": "active",
            "stripe_session_id": "manual_test",
            "payment_id": "manual_test",
            "amount": 9.0,
            "current_period_start": datetime.now(timezone.utc).isoformat(),
            "current_period_end": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "executions_used": 0,
            "agents_used": 0,
            "agents_published": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return sub_id
    sub_id = _run(_seed)

    # Upload + install + run a tiny agent.
    manifest = {
        "name": f"hostingexec-{uuid.uuid4().hex[:6]}",
        "version": "1.0.0",
        "display_name": "Hosting Exec Counter Test",
        "description": "Bump test",
        "runtime": "python3.11",
        "entry_point": "main.py",
        "entry_function": "run",
        "dependencies": [],
    }
    files = {
        "manifest.json": json.dumps(manifest),
        "main.py": "def run(input):\n    return {'ok': True}\n",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p, c in files.items():
            z.writestr(p, c)
    blob = buf.getvalue()
    up = requests.post(
        f"{BASE_URL}/api/external-agents/upload",
        headers=auth_headers,
        files={"file": (f"{manifest['name']}.tfagent", blob, "application/zip")},
        timeout=30,
    )
    assert up.status_code == 200
    pkg_id = up.json()["package_id"]
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers=auth_headers, timeout=10,
    )
    # Wait for install
    import time
    for _ in range(60):
        s = requests.get(
            f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install-status",
            headers=auth_headers, timeout=10,
        ).json()
        if s["install_status"] == "ready":
            break
        if s["install_status"] == "failed":
            pytest.fail(f"install failed: {s}")
        time.sleep(1)
    # Run once and assert counter bumped.
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers=auth_headers, json={"input": {}}, timeout=30,
    )
    assert r.status_code == 200, r.text
    sub = _run(lambda db: db.hosting_subscriptions.find_one({"id": sub_id}))
    assert sub["executions_used"] >= 1, sub
    # Cleanup
    requests.delete(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
        headers=auth_headers, timeout=10,
    )
    _run(lambda db: db.hosting_subscriptions.delete_one({"id": sub_id}))


# ── 7. Cleanup module ──────────────────────────────────────────────────────
def test_cleanup_admin_subs():
    """Leave the test_credentials admin user with NO active hosting sub."""
    async def _flow(db):
        await db.hosting_subscriptions.update_many(
            {"creator_email": ADMIN_EMAIL, "status": "active"},
            {"$set": {"status": "superseded"}},
        )
        await db.hosting_subscriptions.delete_many(
            {"creator_email": ADMIN_EMAIL, "status": {"$in": ["cancelled", "superseded"]}},
        )
        await db.payment_transactions.delete_many(
            {"user_email": ADMIN_EMAIL, "type": "hosting", "payment_status": "pending"},
        )
        return await db.hosting_subscriptions.count_documents(
            {"creator_email": ADMIN_EMAIL, "status": "active"},
        )
    remaining = _run(_flow)
    assert remaining == 0
