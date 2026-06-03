"""
Iter38 — Signup bonus + IP tracking + anti-abuse cap + Admin Overwatch
        + vibe_chat cost upgrade (0→1).
"""
import os
import secrets
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# --- helpers ----------------------------------------------------------------

def _mk_email(tag: str) -> str:
    return f"iter38_{tag}_{secrets.token_hex(3)}@test.com"


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def db(loop):
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@nova.ai", "password": "admin123"}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- Module 1: SIGNUP BONUS + IP TRACKING -----------------------------------

class TestSignupBonus:

    def test_register_grants_50_bonus_and_tracks_ip(self, loop, db):
        email = _mk_email("bonus")
        ip = "203.0.113.42"
        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "testpass123", "name": "Bonus User"},
            headers={"X-Forwarded-For": ip},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == email
        token = data["token"]

        # /credits/me should reflect 50+50 = 100
        cr = requests.get(f"{BASE_URL}/api/credits/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert cr.status_code == 200
        body = cr.json()
        assert body["balance"] == 100, body
        assert body["subscription_credits"] == 50
        assert body["topup_credits"] == 50
        assert body["subscription_credits_max"] == 50
        assert body["tier"] == "recruit"
        assert body["credit_reset_date"], "credit_reset_date must be set"

        # DB verifies user.registration_ip + last_login_ip + ledger entry
        async def _check():
            user = await db.users.find_one({"email": email}, {"_id": 0})
            assert user["registration_ip"] == ip
            assert user["last_login_ip"] == ip
            assert user["tier"] == "recruit"
            txn = await db.credit_transactions.find_one(
                {"email": email, "kind": "signup_bonus"}, {"_id": 0})
            assert txn is not None
            assert txn["delta"] == 50
            assert txn["pool"] == "topup"
            assert "welcome bonus" in txn["note"]
            return user["id"]
        uid = loop.run_until_complete(_check())
        assert uid

    def test_login_updates_last_login_ip(self, loop, db):
        email = _mk_email("loginip")
        # register from IP A
        requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "testpass123", "name": "x"},
                      headers={"X-Forwarded-For": "10.0.0.1"}, timeout=15)
        # login from IP B (comma list → first wins)
        ip_b = "198.51.100.7"
        rl = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": email, "password": "testpass123"},
                           headers={"X-Forwarded-For": f"{ip_b}, 10.10.10.10"}, timeout=15)
        assert rl.status_code == 200, rl.text

        async def _check():
            u = await db.users.find_one({"email": email}, {"_id": 0})
            assert u["last_login_ip"] == ip_b
            assert u["registration_ip"] == "10.0.0.1"
            assert u.get("last_login_at")
        loop.run_until_complete(_check())


# --- Module 2: ANTI-ABUSE CAP -----------------------------------------------

class TestAntiAbuseCap:
    """Pre-seed users via direct DB insert (to avoid /register's 5/600s rate limit),
    then issue ONE register from same IP to hit the 429 cap path."""

    def test_4th_register_from_same_ip_returns_429(self, loop, db):
        abuse_ip = f"192.0.2.{secrets.randbelow(200)+10}"
        now = datetime.now(timezone.utc).isoformat()

        async def _seed():
            docs = []
            for i in range(3):
                docs.append({
                    "id": f"iter38-seed-{secrets.token_hex(4)}",
                    "email": f"iter38_seed_{i}_{secrets.token_hex(3)}@test.com",
                    "password_hash": "x", "name": f"seed{i}", "role": "user",
                    "registration_ip": abuse_ip,
                    "last_login_ip": abuse_ip,
                    "created_at": now,
                    "subscription_credits": 50, "subscription_credits_max": 50,
                    "topup_credits": 0, "tier": "recruit",
                    "credit_reset_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                })
            await db.users.insert_many(docs)
            return [d["id"] for d in docs]
        seeded_ids = loop.run_until_complete(_seed())

        # 4th register from same IP → 429
        r4 = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": _mk_email("cap"), "password": "testpass123", "name": "blocked"},
            headers={"X-Forwarded-For": abuse_ip}, timeout=15,
        )
        assert r4.status_code == 429, f"expected 429 got {r4.status_code}: {r4.text}"
        detail = r4.json().get("detail", "")
        assert "Too many accounts" in detail, detail

        # cleanup
        async def _clean():
            await db.users.delete_many({"id": {"$in": seeded_ids}})
        loop.run_until_complete(_clean())

    def test_cap_resets_after_24h_window(self, loop, db):
        """Seed 3 accounts older than 24h on a fresh IP — registration should succeed."""
        abuse_ip = f"192.0.2.{secrets.randbelow(200)+220}"
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()

        async def _seed():
            ids = []
            for i in range(3):
                d = {
                    "id": f"iter38-old-{secrets.token_hex(4)}",
                    "email": f"iter38_old_{i}_{secrets.token_hex(3)}@test.com",
                    "password_hash": "x", "name": f"old{i}", "role": "user",
                    "registration_ip": abuse_ip, "last_login_ip": abuse_ip,
                    "created_at": old_ts,
                    "subscription_credits": 50, "subscription_credits_max": 50,
                    "topup_credits": 0, "tier": "recruit",
                    "credit_reset_date": old_ts,
                }
                await db.users.insert_one(d)
                ids.append(d["id"])
            return ids
        seeded = loop.run_until_complete(_seed())

        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": _mk_email("oldwindow"), "password": "testpass123", "name": "ok"},
            headers={"X-Forwarded-For": abuse_ip}, timeout=15,
        )
        assert r.status_code == 200, f"expected 200 (old records don't count) got {r.status_code}: {r.text}"

        async def _clean():
            await db.users.delete_many({"id": {"$in": seeded}})
        loop.run_until_complete(_clean())


# --- Module 3: ADMIN OVERWATCH ----------------------------------------------

class TestAdminOverwatch:

    def test_list_requires_admin(self):
        # Unauthenticated → 401/403
        r = requests.get(f"{BASE_URL}/api/admin/ip-abuse", timeout=15)
        assert r.status_code in (401, 403), r.status_code

        # Non-admin user → 403
        email = _mk_email("nonadmin")
        rr = requests.post(f"{BASE_URL}/api/auth/register",
                           json={"email": email, "password": "testpass123", "name": "n"},
                           headers={"X-Forwarded-For": "172.16.0.99"}, timeout=15)
        if rr.status_code == 200:
            tok = rr.json()["token"]
            r2 = requests.get(f"{BASE_URL}/api/admin/ip-abuse",
                              headers={"Authorization": f"Bearer {tok}"}, timeout=15)
            assert r2.status_code == 403
            assert "Admin only" in r2.json().get("detail", "")

    def test_admin_lists_ip_groups(self, loop, db, admin_headers):
        abuse_ip = f"203.0.113.{secrets.randbelow(200)+50}"
        now = datetime.now(timezone.utc).isoformat()

        async def _seed():
            ids = []
            for i in range(3):
                d = {
                    "id": f"iter38-grp-{secrets.token_hex(4)}",
                    "email": f"iter38_grp_{i}_{secrets.token_hex(3)}@test.com",
                    "password_hash": "x", "name": f"g{i}", "role": "user",
                    "registration_ip": abuse_ip, "last_login_ip": abuse_ip,
                    "created_at": now,
                    "subscription_credits": 50, "subscription_credits_max": 50,
                    "topup_credits": 0, "tier": "recruit",
                }
                await db.users.insert_one(d)
                ids.append(d["id"])
            return ids
        seeded = loop.run_until_complete(_seed())

        r = requests.get(f"{BASE_URL}/api/admin/ip-abuse?min_accounts=3",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "groups" in body and "banned_ips" in body and "policy" in body
        assert body["policy"]["max_accounts_per_ip_24h"] == 3

        match = next((g for g in body["groups"] if g["ip"] == abuse_ip), None)
        assert match is not None, f"expected group for {abuse_ip} in {body['groups'][:5]}"
        assert match["count"] >= 3
        assert len(match["accounts"]) >= 3
        a0 = match["accounts"][0]
        for f in ("id", "email", "name", "created_at", "tier"):
            assert f in a0, f"missing {f} in account row"

        # min_accounts clamping (0 → 2). Just verify no 5xx and ints.
        r2 = requests.get(f"{BASE_URL}/api/admin/ip-abuse?min_accounts=0",
                          headers=admin_headers, timeout=15)
        assert r2.status_code == 200

        async def _clean():
            await db.users.delete_many({"id": {"$in": seeded}})
        loop.run_until_complete(_clean())

    def test_flag_unflag_ban_unban(self, loop, db, admin_headers):
        # Create a target user
        email = _mk_email("targetact")
        rr = requests.post(f"{BASE_URL}/api/auth/register",
                           json={"email": email, "password": "testpass123", "name": "t"},
                           headers={"X-Forwarded-For": f"172.16.{secrets.randbelow(200)+1}.1"}, timeout=15)
        assert rr.status_code == 200, rr.text
        uid = rr.json()["user"]["id"]

        def _act(action):
            return requests.post(
                f"{BASE_URL}/api/admin/ip-abuse/action",
                json={"user_id": uid, "action": action},
                headers={**admin_headers, "Content-Type": "application/json"}, timeout=15)

        async def _state():
            return await db.users.find_one({"id": uid}, {"_id": 0})

        r = _act("flag")
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True, "action": "flag", "user_id": uid}
        s = loop.run_until_complete(_state())
        assert s["flagged_for_abuse"] is True

        assert _act("unflag").status_code == 200
        s = loop.run_until_complete(_state())
        assert s["flagged_for_abuse"] is False

        assert _act("ban").status_code == 200
        s = loop.run_until_complete(_state())
        assert s["banned"] is True

        # Co-traveller: banned user's IP should appear in banned_ips
        list_r = requests.get(f"{BASE_URL}/api/admin/ip-abuse?min_accounts=2",
                              headers=admin_headers, timeout=15)
        assert list_r.status_code == 200
        assert s["registration_ip"] in list_r.json()["banned_ips"]

        assert _act("unban").status_code == 200
        s = loop.run_until_complete(_state())
        assert s["banned"] is False

        # invalid action → 422 (Pydantic pattern)
        rinv = _act("delete")
        assert rinv.status_code == 422, rinv.status_code

        # non-existent user → 404
        rmiss = requests.post(
            f"{BASE_URL}/api/admin/ip-abuse/action",
            json={"user_id": "does-not-exist-xxxxx", "action": "flag"},
            headers={**admin_headers, "Content-Type": "application/json"}, timeout=15)
        assert rmiss.status_code == 404


# --- Module 4: VIBE_CHAT cost & action_costs map ----------------------------

class TestActionCosts:

    def test_action_costs_in_credits_me(self):
        # Use admin (always has /credits/me access). action_costs is independent of role.
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@nova.ai", "password": "admin123"}, timeout=15)
        tok = r.json()["token"]
        cr = requests.get(f"{BASE_URL}/api/credits/me",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert cr.status_code == 200
        body = cr.json()
        ac = body.get("action_costs") or {}
        assert ac.get("vibe_chat") == 1, f"vibe_chat expected 1 got {ac.get('vibe_chat')}"
        assert ac.get("build_bot") == 5
        assert ac.get("workflow_run") == 1
        assert ac.get("bot_deploy") == 0
        assert ac.get("agent_run") == 1
        assert ac.get("external_agent_run") == 2
        assert ac.get("publish_listing") == 0


# --- Module 5: MongoDB indexes ----------------------------------------------

class TestIndexes:

    def test_users_collection_has_ip_indexes(self, loop, db):
        async def _check():
            idxs = await db.users.list_indexes().to_list(50)
            keys = []
            for ix in idxs:
                keys.extend(list(ix.get("key", {}).keys()))
            return keys
        keys = loop.run_until_complete(_check())
        assert "registration_ip" in keys, keys
        assert "last_login_ip" in keys, keys


# --- Module 6: Regression auth ----------------------------------------------

class TestAuthRegression:

    def test_admin_login_and_me(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@nova.ai", "password": "admin123"}, timeout=15)
        assert r.status_code == 200
        tok = r.json()["token"]
        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert me.status_code == 200
        assert me.json()["role"] == "admin"

    def test_forgot_password_still_works(self):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"email": "freeuser@test.com"}, timeout=15)
        # 200 even if email doesn't exist (intentional). 429 if rate-limited from prior tests.
        assert r.status_code in (200, 429), r.status_code
