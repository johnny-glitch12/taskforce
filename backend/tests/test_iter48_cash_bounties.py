"""
Iter48 — Prompt 9 P2: Cash Bounties via Stripe Connect.

Validates the cash bounty + stripe-connect endpoints end-to-end (without
actually paying the test Checkout Session).
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ORIGIN = BASE_URL  # frontend lives at same host
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"
USER_EMAIL = "freeuser@test.com"
USER_PASS = "test123"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    return r.json().get("token") if r.status_code == 200 else None


def _run(coro_factory):
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
def admin_auth():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert t, "admin login must work"
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def user_auth():
    t = _login(USER_EMAIL, USER_PASS)
    assert t, "freeuser login must work"
    return {"Authorization": f"Bearer {t}"}


def _clear_test_bounties():
    async def _flow(db):
        await db.bounties.delete_many({"poster_email": {"$in": [ADMIN_EMAIL, USER_EMAIL]},
                                       "reward_type": "cash"})
        await db.payment_transactions.delete_many({"type": "bounty",
                                                   "user_email": {"$in": [ADMIN_EMAIL, USER_EMAIL]}})
    _run(_flow)


def _cash_body(amount=25, origin=None):
    return {
        "title": f"Cash bounty test {uuid.uuid4().hex[:6]}",
        "description": "A description that is long enough to pass validation rules.",
        "category": "automation",
        "required_integrations": ["slack"],
        "input_expectations": "channel url",
        "output_expectations": "summary",
        "example_use_case": "catch up on a thread",
        "reward_type": "cash",
        "cash_amount_usd": amount,
        "deadline_days": 7,
        "max_submissions": 5,
        "origin_url": origin or ORIGIN,
    }


# ── Tests ────────────────────────────────────────────────────────────────────
def test_create_cash_bounty_returns_checkout_url(user_auth):
    _clear_test_bounties()
    r = requests.post(f"{BASE_URL}/api/bounties", headers=user_auth,
                      json=_cash_body(25), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bounty"]["status"] == "pending_payment"
    assert body["bounty"]["escrow_status"] == "pending"
    assert body["bounty"]["reward_type"] == "cash"
    assert body["bounty"]["reward_amount"] == 25.0
    assert "checkout_url" in body and "stripe.com" in body["checkout_url"]
    assert body["session_id"].startswith("cs_test_")

    # payment_transactions row exists
    tx = _run(lambda db: db.payment_transactions.find_one({"session_id": body["session_id"]}))
    assert tx is not None
    assert tx["type"] == "bounty"
    assert tx["bounty_id"] == body["bounty"]["id"]

    # Stash for follow-up tests
    pytest.cash_bounty = body["bounty"]
    pytest.cash_session_id = body["session_id"]


def test_cash_min_amount_rejected(user_auth):
    r = requests.post(f"{BASE_URL}/api/bounties", headers=user_auth,
                      json=_cash_body(5), timeout=15)
    assert r.status_code == 422, r.text


def test_cash_missing_origin_rejected(user_auth):
    body = _cash_body(25)
    body.pop("origin_url", None)
    r = requests.post(f"{BASE_URL}/api/bounties", headers=user_auth, json=body, timeout=15)
    assert r.status_code == 422, r.text


def test_pending_payment_bounty_hidden_from_public_list():
    b = pytest.cash_bounty
    r = requests.get(f"{BASE_URL}/api/bounties", timeout=15)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json().get("items", [])]
    assert b["id"] not in ids, "pending_payment bounty must not be public"


def test_my_posted_includes_pending_payment(user_auth):
    b = pytest.cash_bounty
    r = requests.get(f"{BASE_URL}/api/bounties/my-posted", headers=user_auth, timeout=15)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json().get("items", [])]
    assert b["id"] in ids


def test_activate_before_paid_returns_402(user_auth):
    b = pytest.cash_bounty
    r = requests.post(f"{BASE_URL}/api/bounties/{b['id']}/activate",
                      headers=user_auth, timeout=20)
    assert r.status_code == 402, r.text


def test_activate_by_non_poster_returns_403(admin_auth):
    b = pytest.cash_bounty
    r = requests.post(f"{BASE_URL}/api/bounties/{b['id']}/activate",
                      headers=admin_auth, timeout=20)
    assert r.status_code == 403, r.text


def test_payment_status_returns_type_and_bounty_id(user_auth):
    sid = pytest.cash_session_id
    r = requests.get(f"{BASE_URL}/api/payments/status/{sid}",
                     headers=user_auth, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("type") == "bounty"
    assert body.get("bounty_id") == pytest.cash_bounty["id"]


def test_cancel_pending_payment_cash_bounty(user_auth):
    b = pytest.cash_bounty
    r = requests.post(f"{BASE_URL}/api/bounties/{b['id']}/cancel",
                      headers=user_auth, timeout=15)
    assert r.status_code == 200, r.text
    # Validate persisted state
    doc = _run(lambda db: db.bounties.find_one({"id": b["id"]}))
    assert doc["status"] == "cancelled"
    assert doc["escrow_status"] == "refunded"


def test_list_stats_include_cash_paid_out():
    r = requests.get(f"{BASE_URL}/api/bounties", timeout=15)
    assert r.status_code == 200
    stats = r.json().get("stats", {})
    assert "credits_paid_out" in stats
    assert "cash_paid_out" in stats
    assert isinstance(stats["credits_paid_out"], int)
    assert isinstance(stats["cash_paid_out"], (int, float))


# ── Stripe Connect ───────────────────────────────────────────────────────────
def test_stripe_connect_account_before_onboard(admin_auth):
    # Clear any prior account for admin so the "before" assertion is meaningful
    _run(lambda db: db.connect_accounts.delete_many({"user_email": ADMIN_EMAIL}))
    r = requests.get(f"{BASE_URL}/api/stripe-connect/account",
                     headers=admin_auth, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("account") is None
    assert body.get("ready_for_payout") is False


def test_stripe_connect_onboard_creates_and_is_idempotent(admin_auth):
    payload = {"return_url": f"{ORIGIN}/payouts?ok=1",
               "refresh_url": f"{ORIGIN}/payouts?refresh=1"}
    r1 = requests.post(f"{BASE_URL}/api/stripe-connect/onboard",
                       headers=admin_auth, json=payload, timeout=30)
    assert r1.status_code == 200, r1.text
    url1 = r1.json().get("url", "")
    assert url1.startswith("https://connect.stripe.com/"), url1
    doc1 = _run(lambda db: db.connect_accounts.find_one({"user_email": ADMIN_EMAIL}))
    assert doc1 is not None
    acct_id_1 = doc1.get("stripe_account_id")
    assert acct_id_1, "stripe_account_id must be persisted"

    # Second call must reuse same account
    r2 = requests.post(f"{BASE_URL}/api/stripe-connect/onboard",
                       headers=admin_auth, json=payload, timeout=30)
    assert r2.status_code == 200, r2.text
    doc2 = _run(lambda db: db.connect_accounts.find_one({"user_email": ADMIN_EMAIL}))
    assert doc2["stripe_account_id"] == acct_id_1, "must be idempotent"


def test_stripe_connect_account_after_onboard(admin_auth):
    r = requests.get(f"{BASE_URL}/api/stripe-connect/account",
                     headers=admin_auth, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    acct = body.get("account")
    assert acct is not None, "expected non-null account after onboard"
    assert acct.get("stripe_account_id"), "stripe_account_id required"
    assert "charges_enabled" in acct
    assert "payouts_enabled" in acct
    assert "details_submitted" in acct
    assert body.get("ready_for_payout") is False  # nothing submitted in test mode


# ── Regression sanity ───────────────────────────────────────────────────────
def test_regression_credit_bounty_still_works(user_auth):
    """Quick check that the credit bounty path still creates+returns 200."""
    body = {
        "title": "Credit regression check ok",
        "description": "Twenty characters minimum required for validation.",
        "category": "automation",
        "reward_type": "credits",
        "reward_amount": 100,
        "deadline_days": 5,
    }
    # Ensure user has credits
    _run(lambda db: db.users.update_one({"email": USER_EMAIL},
                                        {"$set": {"topup_credits": 5000}}))
    r = requests.post(f"{BASE_URL}/api/bounties", headers=user_auth, json=body, timeout=15)
    assert r.status_code == 200, r.text
    bid = r.json()["bounty"]["id"]
    # Clean up
    requests.post(f"{BASE_URL}/api/bounties/{bid}/cancel", headers=user_auth, timeout=10)


def test_cleanup():
    _clear_test_bounties()
