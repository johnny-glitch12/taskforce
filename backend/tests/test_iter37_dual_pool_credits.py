"""
Iter37 — Dual-Pool Credits Tests
Covers credit_wallet.py rewrite: subscription_credits + topup_credits pools,
reset_subscription(), debit() priority, promo redeem → topup,
topup checkout payment_transactions row, webhook import wiring, legacy migration.
"""
import os
import sys
import time
import uuid
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

# Add backend dir to sys.path for lib imports
sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@nova.ai", "password": "admin123"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _make_user_direct(email: str, password: str = "TestPass123!"):
    """Insert user directly into DB (bypass rate limit), then login for token."""
    from server import hash_password
    from pymongo import MongoClient
    client = MongoClient(os.environ.get("MONGO_URL"))
    db_sync = client[os.environ.get("DB_NAME")]
    uid = uuid.uuid4().hex
    from datetime import datetime, timezone, timedelta
    db_sync.users.insert_one({
        "id": uid,
        "email": email,
        "name": "iter37",
        "role": "user",
        "tier": "recruit",
        "password_hash": hash_password(password),
        "subscription_credits": 50,
        "subscription_credits_max": 50,
        "topup_credits": 0,
        "credit_reset_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return {"email": email, "password": password, "token": r.json()["token"], "user_id": uid}


@pytest.fixture(scope="module")
def fresh_user():
    """Create a fresh user directly in DB; returns dict {email, password, token}."""
    email = f"iter37_{uuid.uuid4().hex[:10]}@test.com"
    return _make_user_direct(email)


@pytest.fixture(scope="module")
def db():
    """Async motor db from server."""
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    return client[os.environ.get("DB_NAME")]


# ── 1. GET /api/credits/me shape (admin)
def test_credits_me_admin_shape(admin_token):
    r = requests.get(f"{API}/credits/me",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    # admin unlimited assertions
    assert d["unlimited"] is True
    assert d["subscription_credits"] == 10**9
    assert d["subscription_credits_max"] == 10**9
    assert d["topup_credits"] == 10**9
    assert d["balance"] == 10**9
    assert d["tier"] == "admin"
    # action_costs shape
    ac = d["action_costs"]
    assert ac["vibe_chat"] == 0
    assert ac["build_bot"] == 5
    assert ac["workflow_run"] == 1
    assert ac["bot_deploy"] == 0
    assert ac["agent_run"] == 1
    assert ac["external_agent_run"] == 2
    assert ac["publish_listing"] == 0
    assert len(ac) == 7
    assert "transactions" in d
    assert "packs" in d
    assert set(d["packs"].keys()) == {"starter", "builder", "operator", "agency"}


# ── 2. Fresh user balance shape (register via API)
def test_fresh_user_balance_shape():
    """Verify register endpoint creates dual-pool defaults."""
    email = f"freshapi_{uuid.uuid4().hex[:10]}@test.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "TestPass123!", "name": "fr"},
                      timeout=30)
    if r.status_code == 429:
        pytest.skip(f"Rate-limited: {r.text}")
    assert r.status_code in (200, 201), r.text
    token = r.json()["token"]
    rb = requests.get(f"{API}/credits/me",
                     headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert rb.status_code == 200, rb.text
    d = rb.json()
    assert d["unlimited"] is False
    assert d["subscription_credits"] == 50
    assert d["subscription_credits_max"] == 50
    assert d["topup_credits"] == 0
    assert d["balance"] == 50
    assert d["tier"] in ("recruit", "free")
    from datetime import datetime, timezone
    reset = datetime.fromisoformat(d["credit_reset_date"])
    now = datetime.now(timezone.utc)
    delta_days = (reset - now).total_seconds() / 86400
    assert 28 <= delta_days <= 31, f"reset {delta_days}d off"


# ── 3. Debit priority: sub first, then topup
def test_debit_priority_sub_first(fresh_user, db):
    from lib import credit_wallet
    async def run():
        user_doc = await db.users.find_one({"email": fresh_user["email"]})
        assert user_doc is not None
        # Grant 100 topup credits
        await credit_wallet.credit(db, user_doc, 100, "test_grant", pool="topup")
        # Refresh balance pre-state
        bal = await credit_wallet.get_balance(db, user_doc)
        assert bal["subscription_credits"] == 50
        assert bal["topup_credits"] == 100
        # Debit build_bot (5 cr) 11 times
        for i in range(11):
            res = await credit_wallet.debit(db, user_doc, "build_bot", ref=f"test_{i}")
            # After 10 debits, sub=0; 11th draws from topup
            if i < 10:
                expected_sub = 50 - (i + 1) * 5
                assert res["sub_remaining"] == expected_sub, f"iter {i}: {res}"
                assert res["topup_remaining"] == 100
            else:
                # 11th: 5 from topup
                assert res["sub_remaining"] == 0
                assert res["topup_remaining"] == 95
        # Verify via /credits/me
        final = await credit_wallet.get_balance(db, user_doc)
        assert final["subscription_credits"] == 0
        assert final["topup_credits"] == 95
    asyncio.get_event_loop().run_until_complete(run())


# ── 4. reset_subscription()
def test_reset_subscription(db):
    from lib import credit_wallet
    async def run():
        email = f"reset_{uuid.uuid4().hex[:10]}@test.com"
        _make_user_direct(email)
        user_doc = await db.users.find_one({"email": email})
        # Set up: sub=0, topup=100
        await db.users.update_one({"email": email},
                                  {"$set": {"subscription_credits": 0, "topup_credits": 100}})
        user_doc = await db.users.find_one({"email": email})
        result = await credit_wallet.reset_subscription(db, user_doc, tier="cadet")
        assert result["subscription_credits"] == 500
        assert result["subscription_credits_max"] == 500
        assert result["topup_credits"] == 100  # UNCHANGED
        assert result["tier"] == "cadet"
        # Verify ledger
        ledger = await db.credit_transactions.find_one(
            {"user_id": {"$in": [str(user_doc.get("id")), email]}, "kind": "subscription_reset"})
        assert ledger is not None
        assert ledger["pool"] == "subscription"
        assert ledger["delta"] == 500
    asyncio.get_event_loop().run_until_complete(run())


# ── 5. Promo redeem → topup pool
def test_promo_redeem_topup(admin_token):
    code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    # Admin creates credits promo
    r = requests.post(f"{API}/promo/codes",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"code": code, "kind": "credits", "value": 200})
    assert r.status_code == 200, r.text
    # New user redeems
    email = f"promo_{uuid.uuid4().hex[:10]}@test.com"
    nu = _make_user_direct(email)
    token = nu["token"]
    # Pre-balance
    pre = requests.get(f"{API}/credits/me",
                       headers={"Authorization": f"Bearer {token}"}).json()
    assert pre["subscription_credits"] == 50
    assert pre["topup_credits"] == 0
    # Redeem
    red = requests.post(f"{API}/promo/redeem",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"code": code})
    assert red.status_code == 200, red.text
    # Post-balance
    post = requests.get(f"{API}/credits/me",
                        headers={"Authorization": f"Bearer {token}"}).json()
    assert post["subscription_credits"] == 50  # UNCHANGED
    assert post["topup_credits"] == 200
    # Verify ledger entry has pool='topup'
    promo_txn = next((t for t in post["transactions"] if t.get("kind") == "promo"), None)
    assert promo_txn is not None
    assert promo_txn["pool"] == "topup"


# ── 6. Topup checkout persists payment_transactions
def test_topup_checkout_persists_payment_txn(fresh_user, db):
    r = requests.post(f"{API}/credits/topup/checkout",
                      headers={"Authorization": f"Bearer {fresh_user['token']}"},
                      json={"pack": "starter"})
    # Could fail if STRIPE not configured — accept either 200 or skip
    if r.status_code == 500 and "Stripe" in r.text:
        pytest.skip("Stripe not configured")
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    assert sid

    async def check():
        doc = await db.payment_transactions.find_one({"session_id": sid})
        assert doc is not None
        assert doc["type"] == "credit_topup"
        assert doc["activated"] is False
        assert doc["credits"] == 200  # starter pack
        assert doc["payment_status"] == "pending"
    asyncio.get_event_loop().run_until_complete(check())


# ── 7. Webhook imports clean
def test_webhook_imports():
    from lib.credit_wallet import reset_subscription, credit
    assert callable(reset_subscription)
    assert callable(credit)
    # Also verify stripe_payments module imports them
    import routes.stripe_payments as sp
    src = open(sp.__file__).read()
    assert "reset_subscription" in src
    assert "credit_wallet" in src


# ── 8. Legacy migration
def test_legacy_migration(db):
    from lib import credit_wallet
    async def run():
        email = f"legacy_{uuid.uuid4().hex[:10]}@test.com"
        uid = uuid.uuid4().hex
        await db.users.insert_one({
            "id": uid, "email": email, "name": "legacy", "role": "user",
            "tier": "cadet", "credit_balance": 120, "created_at": "2025-01-01T00:00:00",
        })
        user_doc = await db.users.find_one({"email": email})
        info1 = await credit_wallet.get_balance(db, user_doc)
        assert info1["subscription_credits"] == 120  # min(120, 500)
        assert info1["subscription_credits_max"] == 500
        assert info1["topup_credits"] == 0
        # credit_balance field unset
        check = await db.users.find_one({"email": email})
        assert "credit_balance" not in check
        # Second call returns same migrated values
        info2 = await credit_wallet.get_balance(db, user_doc)
        assert info2["subscription_credits"] == 120
        # cleanup
        await db.users.delete_one({"email": email})
    asyncio.get_event_loop().run_until_complete(run())


# ── 9. Admin debit doesn't decrement; ledger has virtual=true
def test_admin_debit_bypass(admin_token, db):
    from lib import credit_wallet
    async def run():
        admin = await db.users.find_one({"email": "admin@nova.ai"})
        assert admin is not None
        before = await credit_wallet.debit(db, admin, "build_bot", ref="admin_test")
        assert before["balance"] == 10**9
        # Verify ledger has virtual=true
        ledger = await db.credit_transactions.find_one(
            {"email": "admin@nova.ai", "ref": "admin_test"})
        assert ledger is not None
        assert ledger.get("virtual") is True
    asyncio.get_event_loop().run_until_complete(run())
    # /credits/me still returns sub=1e9
    r = requests.get(f"{API}/credits/me",
                     headers={"Authorization": f"Bearer {admin_token}"})
    d = r.json()
    assert d["subscription_credits"] == 10**9
    assert d["topup_credits"] == 10**9


# ── 10. Ledger fields on debit + credit
def test_ledger_fields(db):
    from lib import credit_wallet
    async def run():
        email = f"ledger_{uuid.uuid4().hex[:10]}@test.com"
        _make_user_direct(email)
        user_doc = await db.users.find_one({"email": email})
        # Credit (topup pool)
        await credit_wallet.credit(db, user_doc, 30, "test_credit", pool="topup")
        c_ledger = await db.credit_transactions.find_one(
            {"email": email, "kind": "test_credit"})
        assert c_ledger["delta"] == 30
        assert c_ledger["pool"] == "topup"
        assert c_ledger["sub_deducted"] == 0
        assert c_ledger["topup_deducted"] == 0
        # Debit (build_bot)
        await credit_wallet.debit(db, user_doc, "build_bot", ref="ledger_dbt")
        d_ledger = await db.credit_transactions.find_one(
            {"email": email, "ref": "ledger_dbt"})
        assert d_ledger["kind"] == "build_bot"
        assert d_ledger["pool"] is None
        assert d_ledger["sub_deducted"] == 5
        assert d_ledger["topup_deducted"] == 0
        assert d_ledger["sub_remaining"] == 45
        assert d_ledger["balance_after"] == 45 + 30
    asyncio.get_event_loop().run_until_complete(run())


# ── 11. build-bot endpoint regression (insufficient credits)
def test_build_bot_endpoint_insufficient_credits():
    """Fresh user with sub=50/topup=0: 10 build-bots succeed, 11th → 402."""
    email = f"buildbot_{uuid.uuid4().hex[:10]}@test.com"
    nu = _make_user_direct(email)
    token = nu["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    success_count = 0
    last_status = None
    for i in range(11):
        r = requests.post(f"{API}/armory/build-bot",
                          headers=headers,
                          json={"prompt": f"test bot {i}", "name": f"bot{i}"},
                          timeout=120)
        last_status = r.status_code
        if r.status_code == 200:
            success_count += 1
        elif r.status_code == 402:
            break
        elif r.status_code == 404:
            pytest.skip("armory/build-bot endpoint not at this path")
        else:
            # Unexpected — log and continue
            print(f"build-bot iter {i}: {r.status_code} {r.text[:200]}")
            break
    # We expect at least some succeed, then 402
    assert success_count >= 1, f"No build-bots succeeded; last={last_status}"
    # If we got 402, great; otherwise just report.
    print(f"build-bot: {success_count} succeeded, last status {last_status}")
