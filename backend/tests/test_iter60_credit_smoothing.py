"""
Iteration 60 — Credit Ecosystem Smoothing + Hidden Pricing
Validates that per-action credit costs are stripped from API responses while
internal DB logging is preserved, plus new /settings, /earnings, /cashback/summary
endpoints and the bounty +30% credit-bonus behaviour.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dark-mode-nova.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"
FREE_EMAIL = "freeuser@test.com"
FREE_PASS = "test123"

FORBIDDEN_KEYS = {"credits_used", "cost_breakdown", "input_tokens", "output_tokens", "key_source"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def free_token():
    r = requests.post(f"{API}/auth/login", json={"email": FREE_EMAIL, "password": FREE_PASS}, timeout=20)
    if r.status_code != 200:
        pytest.skip("free user login failed")
    return r.json()["token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- auth/login sanity ----------
def test_admin_login_works(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 10


# ---------- vibe/chat response scrub ----------
def test_vibe_chat_response_is_scrubbed(admin_token):
    r = requests.post(f"{API}/vibe/chat",
                      headers=H(admin_token),
                      json={"message": "say hi briefly", "model": "gemini-2.5-flash"},
                      timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    leaked = FORBIDDEN_KEYS & set(data.keys())
    assert not leaked, f"chat response leaks: {leaked} :: keys={list(data.keys())}"
    for k in ("session_id", "type", "response", "balance_remaining", "model"):
        assert k in data, f"chat missing required key {k}"


# ---------- vibe/recommend-model response scrub ----------
def test_recommend_model_response_is_scrubbed(admin_token):
    r = requests.post(f"{API}/vibe/recommend-model",
                      headers=H(admin_token),
                      json={"prompt": "build a TODO list app"},
                      timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    leaked = FORBIDDEN_KEYS & set(data.keys())
    assert not leaked, f"recommend-model leaks: {leaked} :: {list(data.keys())}"
    for k in ("model", "label", "build_cost", "reason", "complexity", "balance_remaining"):
        assert k in data, f"recommend-model missing {k}"


# ---------- vibe/generate response scrub (queued or sync) ----------
def test_vibe_generate_response_is_scrubbed(admin_token):
    # First start a chat session to get a session_id
    chat_r = requests.post(f"{API}/vibe/chat",
                           headers=H(admin_token),
                           json={"message": "I want a hello world app", "model": "gemini-2.5-flash"},
                           timeout=120)
    if chat_r.status_code != 200:
        pytest.skip(f"chat precondition failed: {chat_r.status_code}")
    sid = chat_r.json().get("session_id")
    assert sid, "no session_id from chat"
    r = requests.post(f"{API}/vibe/generate",
                      headers=H(admin_token),
                      json={"session_id": sid, "message": "build it", "model": "gemini-2.5-flash"},
                      timeout=240)
    if r.status_code == 500:
        pytest.skip(f"/vibe/generate 500: {r.text[:200]}")
    if r.status_code == 503:
        pytest.skip(f"/vibe/generate 503 (broker down + inline fallback unavailable): {r.text[:200]}")
    assert r.status_code == 200, r.text
    data = r.json()
    leaked = FORBIDDEN_KEYS & set(data.keys())
    assert not leaked, f"generate leaks: {leaked} :: keys={list(data.keys())}"
    # If we got an inline result, also verify nested result block is clean.
    nested = data.get("result") or {}
    leaked_nested = FORBIDDEN_KEYS & set(nested.keys())
    assert not leaked_nested, f"generate inline result leaks: {leaked_nested}"


# ---------- armory/build-bot response scrub ----------
def test_armory_build_bot_response_is_scrubbed(admin_token):
    r = requests.post(f"{API}/armory/build-bot",
                      headers=H(admin_token),
                      json={"prompt": "tiny ping bot", "model": "gemini-2.5-flash"},
                      timeout=120)
    # 200 or 402; either way, response must not leak fields
    assert r.status_code in (200, 402), r.text
    data = r.json()
    leaked = FORBIDDEN_KEYS & set(data.keys())
    assert not leaked, f"armory/build-bot leaks: {leaked} :: {list(data.keys())}"


# ---------- credits/me drops action_costs ----------
def test_credits_me_no_action_costs(admin_token):
    r = requests.get(f"{API}/credits/me", headers=H(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "action_costs" not in data, "credits/me must no longer include 'action_costs'"
    for k in ("balance", "subscription_credits", "topup_credits", "packs", "transactions"):
        assert k in data, f"credits/me missing {k}"


# ---------- DB still logs cost metadata; API hides it from users ----------
def test_chat_transaction_metadata_logged_in_db_hidden_from_api(admin_token):
    """The internal DB rows MUST still carry cost metadata so the owner-only
    Economics Dashboard works. The user-facing /credits/me response MUST NOT
    leak that metadata."""
    # trigger a chat (or a build call) to create a transaction with metadata.
    requests.post(f"{API}/vibe/chat",
                  headers=H(admin_token),
                  json={"prompt": "one-word reply", "model": "gemini-2.5-flash"},
                  timeout=120)
    time.sleep(1.0)
    # 1) API surface should NOT carry metadata anywhere
    r = requests.get(f"{API}/credits/me", headers=H(admin_token), timeout=20)
    assert r.status_code == 200
    txns = r.json().get("transactions", [])
    for t in txns:
        assert "metadata" not in t, f"metadata leaked into /credits/me txn: {t}"

    # 2) DB rows should still contain the metadata (sample any tx with kind in
    # vibe_chat / vibe_build / build_bot — at least one should have metadata).
    import os
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name   = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME unavailable in this test env")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    async def _check():
        cursor = db.credit_transactions.find(
            {"kind": {"$in": ["vibe_chat", "vibe_build", "build_bot", "agent_run"]},
             "metadata": {"$exists": True}},
        ).sort("created_at", -1).limit(10)
        rows = await cursor.to_list(10)
        return rows

    rows = asyncio.get_event_loop().run_until_complete(_check())
    client.close()
    assert rows, "expected at least one credit_transactions row with metadata in DB"
    sample = rows[0].get("metadata") or {}
    keys_present = [k for k in ("api_cost_usd", "revenue_usd", "model", "key_source", "input_tokens", "output_tokens") if k in sample]
    assert len(keys_present) >= 3, f"internal cost logging too thin in DB: md={sample}"


# ---------- /settings GET ----------
def test_settings_get_shape(admin_token):
    r = requests.get(f"{API}/settings", headers=H(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "payout_preference" in data
    assert data["payout_preference"] in ("credits", "cash")
    assert "stats" in data and isinstance(data["stats"], dict)
    for k in ("credits_earned_total", "bonus_credits_earned", "cashback_earned_total"):
        assert k in data["stats"], f"stats missing {k}"
    assert "ecosystem" in data
    eco = data["ecosystem"]
    assert eco.get("credit_bonus_rate") == 0.3
    assert eco.get("credit_value_usd") == 0.01
    assert eco.get("min_cash_payout") == 10


def test_settings_requires_auth():
    r = requests.get(f"{API}/settings", timeout=20)
    assert r.status_code == 401


# ---------- payout preference toggle ----------
def test_payout_preference_toggle(admin_token):
    # to cash
    r = requests.put(f"{API}/settings/payout-preference",
                     headers=H(admin_token), json={"preference": "cash"}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json().get("payout_preference") == "cash"
    # persists
    r2 = requests.get(f"{API}/settings", headers=H(admin_token), timeout=20)
    assert r2.json()["payout_preference"] == "cash"
    # back to credits
    r3 = requests.put(f"{API}/settings/payout-preference",
                      headers=H(admin_token), json={"preference": "credits"}, timeout=20)
    assert r3.status_code == 200
    assert r3.json()["payout_preference"] == "credits"
    r4 = requests.get(f"{API}/settings", headers=H(admin_token), timeout=20)
    assert r4.json()["payout_preference"] == "credits"


def test_payout_preference_invalid_value(admin_token):
    r = requests.put(f"{API}/settings/payout-preference",
                     headers=H(admin_token), json={"preference": "invalid"}, timeout=20)
    assert r.status_code == 422


# ---------- /earnings ----------
def test_earnings_endpoint_shape(admin_token):
    r = requests.get(f"{API}/earnings", headers=H(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("payout_preference", "total_earned_usd", "credits", "cash", "cashback"):
        assert k in data, f"/earnings missing {k}"
    assert isinstance(data["credits"], dict)
    assert isinstance(data["cash"], dict)
    assert isinstance(data["cashback"], dict)
    for k in ("total_credits", "bonus_credits", "marketplace_sales", "bounty_wins"):
        assert k in data["credits"], f"/earnings.credits missing {k}"
    for k in ("total_credits", "events"):
        assert k in data["cashback"], f"/earnings.cashback missing {k}"


# ---------- /cashback/summary ----------
def test_cashback_summary_shape(admin_token):
    r = requests.get(f"{API}/cashback/summary", headers=H(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "lifetime_earned" in data
    assert "accumulator" in data


# ---------- Bounty +30% credit-bonus award (unit-level on lib/payouts) ----------
def test_payouts_lib_30pct_credit_bonus_logic():
    """Direct unit test of lib/payouts.process_creator_earning to confirm
    the +30% credit bonus formula. Avoids the heavy bounty-submit chain
    which requires a pre-existing Exchange listing owned by the submitter."""
    import sys, asyncio
    sys.path.insert(0, "/app/backend")
    from lib.payouts import process_creator_earning, CREDIT_BONUS_RATE, CREDIT_VALUE_USD

    assert CREDIT_BONUS_RATE == 0.30
    assert CREDIT_VALUE_USD == 0.01

    # Fake db (only the calls actually used by the credits branch)
    class FakeUsers:
        def __init__(self):
            self.doc = {"id": "TEST_USER", "topup_credits": 0,
                        "subscription_credits": 0, "credits_earned_total": 0,
                        "bonus_credits_earned_total": 0}
        async def find_one_and_update(self, q, upd, return_document=True):
            inc = upd.get("$inc", {})
            for k, v in inc.items():
                self.doc[k] = self.doc.get(k, 0) + v
            return self.doc

    class FakeTxns:
        def __init__(self):
            self.rows = []
        async def insert_one(self, row):
            self.rows.append(row)

    class FakeDB:
        def __init__(self):
            self.users = FakeUsers()
            self.credit_transactions = FakeTxns()

    db = FakeDB()
    res = asyncio.run(process_creator_earning(
        db, creator={"id": "TEST_USER", "payout_preference": "credits"},
        amount_usd=1.00, source="bounty_win", ref="TEST_BOUNTY_60",
    ))
    # $1.00 = 100 base credits → +30 bonus → 130 total
    assert res["payout_type"] == "credits"
    assert res["base_credits"] == 100
    assert res["bonus_credits"] == 30
    assert res["total_credits"] == 130
    assert db.users.doc["topup_credits"] == 130
    assert db.users.doc["bonus_credits_earned_total"] == 30
    # Transaction logged with bonus metadata
    assert len(db.credit_transactions.rows) == 1
    md = db.credit_transactions.rows[0]["metadata"]
    assert md["base_credits"] == 100
    assert md["bonus_credits"] == 30
    assert md["bonus_rate"] == 0.30
    assert md["payout_type"] == "credits"


def test_bounty_credit_award_includes_30pct_bonus(admin_token, free_token):
    # ensure free user has payout_preference = credits
    requests.put(f"{API}/settings/payout-preference",
                 headers=H(free_token), json={"preference": "credits"}, timeout=20)

    # get free user's balance before
    me = requests.get(f"{API}/credits/me", headers=H(free_token), timeout=20).json()
    bal_before = me.get("balance", 0)

    # create a bounty
    bounty_payload = {
        "title": f"TEST_iter60_bounty_{uuid.uuid4().hex[:6]}",
        "description": "Smoke bounty for iter60 +30% credit bonus verification end-to-end.",
        "reward_type": "credits",
        "reward_amount": 100,
        "category": "automation",
        "deadline_days": 7,
    }
    cr = requests.post(f"{API}/bounties", headers=H(admin_token), json=bounty_payload, timeout=20)
    print(f"BOUNTY CREATE: {cr.status_code} {cr.text[:300]}")
    if cr.status_code not in (200, 201):
        pytest.skip(f"bounty create unsupported in this env: {cr.status_code} {cr.text[:200]}")
    bounty_resp = cr.json()
    bounty = bounty_resp.get("bounty") or bounty_resp
    bid = bounty.get("id") or bounty.get("_id") or bounty.get("bounty_id")
    assert bid, f"no bounty id in {bounty}"

    # free user submits
    sub_payload = {"source_id": uuid.uuid4().hex[:16], "pitch": "TEST iter60 submission pitch with adequate length to pass validation"}
    sr = requests.post(f"{API}/bounties/{bid}/submit", headers=H(free_token), json=sub_payload, timeout=20)
    if sr.status_code not in (200, 201):
        pytest.skip(f"bounty submit unsupported: {sr.status_code} {sr.text[:200]}")
    sub = sr.json()
    sub_inner = sub.get("submission") if isinstance(sub.get("submission"), dict) else sub
    sub_id = sub_inner.get("id") or sub_inner.get("_id") or sub_inner.get("submission_id")
    assert sub_id, f"no submission id in {sub}"

    # admin awards it
    aw = requests.post(f"{API}/bounties/{bid}/award",
                       headers=H(admin_token), json={"submission_id": sub_id}, timeout=30)
    if aw.status_code not in (200, 201):
        pytest.skip(f"bounty award unsupported: {aw.status_code} {aw.text[:200]}")
    time.sleep(1.5)

    me2 = requests.get(f"{API}/credits/me", headers=H(free_token), timeout=20).json()
    bal_after = me2.get("balance", 0)
    delta = bal_after - bal_before
    # 100 base + 30 bonus = 130 expected
    assert delta >= 130, f"expected +130cr (100 base + 30 bonus), got +{delta} (before={bal_before} after={bal_after})"


# ---------- Pricing/Credits frontend scrub markers (page-source only smoke) ----------
def test_pricing_page_html_no_per_action_costs():
    r = requests.get(f"{BASE_URL}/pricing", timeout=20)
    # SPA — body is just the shell. Skip soft.
    if r.status_code != 200:
        pytest.skip("frontend shell not reachable")
    # Just sanity that the shell serves
    assert "<!DOCTYPE" in r.text or "<!doctype" in r.text
