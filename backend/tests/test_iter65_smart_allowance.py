"""
test_iter65_smart_allowance — tests for the Smart Allowance + cashback toast surface.

Backend changes under test:
  - GET /api/credits/balance now returns:
      • subscription_pct (0..100): % of monthly grant still available
      • cashback_lifetime: total cashback ever earned (for FE delta detection)
  - Existing fields (subscription, topup, total, subscription_max, etc.) intact.

Cashback grant flow (lib/cashback) is already covered by Phase 60 tests; this
file focuses on the surfaced fields so the FE can render the allowance ring
and the celebration toast.
"""
from __future__ import annotations

import os
import sys
import asyncio
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = os.environ.get("PUBLIC_API_BASE") or "http://localhost:8001"


@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API}/api/auth/login",
                   json={"email": "admin@nova.ai", "password": "admin123"}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def free_token():
    r = httpx.post(f"{API}/api/auth/login",
                   json={"email": "freeuser@test.com", "password": "test123"}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_balance_response_shape(admin_token):
    r = httpx.get(f"{API}/api/credits/balance",
                  headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    # Pre-existing keys
    for k in ("subscription", "topup", "total", "subscription_max",
              "monthly_grant", "reset_date", "tier", "unlimited"):
        assert k in j, f"missing key: {k}"
    # NEW keys for Smart Allowance + cashback toast
    assert "subscription_pct" in j
    assert "cashback_lifetime" in j
    assert isinstance(j["subscription_pct"], int)
    assert 0 <= j["subscription_pct"] <= 100
    assert isinstance(j["cashback_lifetime"], int)
    assert j["cashback_lifetime"] >= 0


def test_admin_unlimited_pct_is_100(admin_token):
    r = httpx.get(f"{API}/api/credits/balance",
                  headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    j = r.json()
    assert j["unlimited"] is True
    # Unlimited users render a full ring; backend reports 100.
    assert j["subscription_pct"] == 100


def test_free_user_pct_within_bounds(free_token):
    r = httpx.get(f"{API}/api/credits/balance",
                  headers={"Authorization": f"Bearer {free_token}"}, timeout=10)
    j = r.json()
    assert j["unlimited"] is False
    if j["subscription_max"] > 0:
        expected = max(0, min(100, round(j["subscription"] / j["subscription_max"] * 100)))
        assert j["subscription_pct"] == expected, \
            f"pct mismatch: got {j['subscription_pct']} expected {expected}"


def test_cashback_lifetime_grows_with_grant():
    """End-to-end: simulate a cashback grant via lib.cashback.accrue_and_grant
    and verify /api/credits/balance.cashback_lifetime reflects the new total."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from lib.cashback import accrue_and_grant

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "taskforce")]

    async def _run():
        u = await db.users.find_one({"email": "freeuser@test.com"})
        assert u, "free user must exist"
        before = int(u.get("cashback_earned_total") or 0)
        # Push the accumulator over the 100-cr threshold to force a grant.
        # We force-set the accumulator first so the test is deterministic
        # regardless of prior state.
        await db.users.update_one({"id": u["id"]}, {"$set": {"cashback_accumulator": 0}})
        result = await accrue_and_grant(db, u, 100)  # exactly one threshold
        assert result["cashback_granted"] == 5, \
            f"100 cr * 5% = 5 cr cashback; got {result}"
        u2 = await db.users.find_one({"id": u["id"]})
        after = int(u2.get("cashback_earned_total") or 0)
        assert after == before + 5, f"lifetime should grow by 5; was {before} now {after}"

    asyncio.run(_run())
    client.close()

    # Now verify the API surfaces the bumped total.
    r = httpx.post(f"{API}/api/auth/login",
                   json={"email": "freeuser@test.com", "password": "test123"}, timeout=10)
    tok = r.json()["token"]
    j = httpx.get(f"{API}/api/credits/balance",
                  headers={"Authorization": f"Bearer {tok}"}, timeout=10).json()
    assert j["cashback_lifetime"] >= 5
