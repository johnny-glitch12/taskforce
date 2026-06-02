"""
Iter39 E2E backend coverage:
 - Auth + admin role
 - /api/credits/me, /api/credits/topup/checkout
 - /api/promo/codes (mint/list/delete) admin gate + redemption (with double-redeem rejection)
 - /api/newsletter/{subscribe|subscribers|unsubscribe}
 - /api/deployments/me, /free (404 path), /checkout (Stripe paid)
 - /api/armory/build-bot auth gate
 - /api/exchange/listings (public + admin create + 422 validation)
 - BYOK whitelist + roundtrip + Stripe probe
"""
import os, time, uuid, json
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

ADMIN = {"email": "admin@nova.ai", "password": "admin123"}


# ───── fixtures ─────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_token():
    email = f"TEST_iter39_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Test12345!", "name": "Iter39 Test"
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()["token"], email


@pytest.fixture(scope="module")
def user_h(user_token):
    return {"Authorization": f"Bearer {user_token[0]}"}


# ───── auth + role ─────
def test_admin_login_returns_admin_role(admin_token):
    # Decode JWT payload portion
    import base64
    p = admin_token.split(".")[1]
    p += "=" * (-len(p) % 4)
    payload = json.loads(base64.urlsafe_b64decode(p))
    assert payload.get("role") == "admin", payload


# ───── credits ─────
def test_credits_me_admin_unlimited(admin_h):
    r = requests.get(f"{BASE}/credits/me", headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("unlimited") is True
    assert d.get("tier") == "admin"
    assert d.get("balance") == 1_000_000_000
    ac = d.get("action_costs") or {}
    assert ac.get("build_bot") == 5
    assert ac.get("workflow_run") == 1
    assert ac.get("bot_deploy") == 0
    packs = d.get("packs") or {}
    for k in ("starter", "builder", "operator", "agency"):
        assert k in packs and packs[k].get("credits") and packs[k].get("price")


def test_credits_topup_checkout_creates_stripe_session(admin_h):
    r = requests.post(f"{BASE}/credits/topup/checkout",
                      headers=admin_h, json={"pack": "starter"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("session_id") and d.get("url")
    assert "stripe.com" in d["url"]


# ───── promo codes ─────
PROMO_CODE = f"TEST_{uuid.uuid4().hex[:6].upper()}"


def test_promo_admin_mint(admin_h):
    r = requests.post(f"{BASE}/promo/codes", headers=admin_h, json={
        "code": PROMO_CODE, "kind": "credits", "value": 100, "max_redemptions": 5
    }, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["code"] == PROMO_CODE
    assert d["kind"] == "credits"
    assert d["active"] is True


def test_promo_list_admin(admin_h):
    r = requests.get(f"{BASE}/promo/codes", headers=admin_h, timeout=15)
    assert r.status_code == 200
    codes = [c["code"] for c in r.json().get("codes", [])]
    assert PROMO_CODE in codes


def test_promo_non_admin_403(user_h):
    r = requests.post(f"{BASE}/promo/codes", headers=user_h, json={
        "code": f"TEST_HACK_{uuid.uuid4().hex[:4]}", "kind": "credits", "value": 50
    }, timeout=15)
    assert r.status_code == 403, r.text


def test_promo_user_redeems_and_double_redeem_blocked(user_h):
    r1 = requests.post(f"{BASE}/promo/redeem", headers=user_h,
                       json={"code": PROMO_CODE}, timeout=15)
    assert r1.status_code == 200, r1.text
    d = r1.json()
    assert d.get("granted") == 100
    # second time → 409
    r2 = requests.post(f"{BASE}/promo/redeem", headers=user_h,
                       json={"code": PROMO_CODE}, timeout=15)
    assert r2.status_code == 409, r2.text


def test_promo_delete_disables(admin_h):
    r = requests.delete(f"{BASE}/promo/codes/{PROMO_CODE}", headers=admin_h, timeout=15)
    assert r.status_code == 200
    # Listing still shows it but inactive
    lst = requests.get(f"{BASE}/promo/codes", headers=admin_h).json().get("codes", [])
    match = [c for c in lst if c["code"] == PROMO_CODE]
    assert match and match[0]["active"] is False


# ───── newsletter ─────
NEWS_EMAIL = f"TEST_iter39_{uuid.uuid4().hex[:6]}@example.com"


def test_newsletter_subscribe_public():
    r = requests.post(f"{BASE}/newsletter/subscribe",
                      json={"email": NEWS_EMAIL, "source": "test"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True


def test_newsletter_subscribe_idempotent():
    r = requests.post(f"{BASE}/newsletter/subscribe",
                      json={"email": NEWS_EMAIL}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("already_subscribed") is True


def test_newsletter_subscribers_admin_only(admin_h, user_h):
    r_user = requests.get(f"{BASE}/newsletter/subscribers", headers=user_h, timeout=15)
    assert r_user.status_code == 403
    r_admin = requests.get(f"{BASE}/newsletter/subscribers", headers=admin_h, timeout=15)
    assert r_admin.status_code == 200
    emails = [s["email"] for s in r_admin.json().get("subscribers", [])]
    assert NEWS_EMAIL.lower() in emails


def test_newsletter_unsubscribe():
    r = requests.delete(f"{BASE}/newsletter/unsubscribe",
                        params={"email": NEWS_EMAIL}, timeout=15)
    assert r.status_code == 200


# ───── deployments ─────
def test_deployments_me_admin(admin_h):
    r = requests.get(f"{BASE}/deployments/me", headers=admin_h, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json().get("deployments"), list)


def test_deployments_free_404_on_missing_listing(admin_h):
    r = requests.post(f"{BASE}/deployments/free", headers=admin_h,
                      json={"listing_id": "DOES_NOT_EXIST_" + uuid.uuid4().hex[:6], "mode": "free"},
                      timeout=15)
    assert r.status_code == 404


def test_deployments_checkout_creates_stripe_for_paid_listing(admin_h):
    # Create a paid listing via direct publish
    payload = {
        "name": f"TEST_paid_{uuid.uuid4().hex[:6]}",
        "description": "iter39 paid listing for deployment checkout test — non-trivial description.",
        "category": "automation",
        "rent_price": 10, "buy_price": 100,
        "avatar_icon": "Bot", "avatar_color": "indigo",
        "trigger_type": "manual", "engine": "gemini-flash",
        "required_integrations": [],
        "files": [], "nodes": [], "edges": [],
    }
    cr = requests.post(f"{BASE}/exchange/listings/direct", headers=admin_h,
                       json=payload, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    lid = cr.json().get("listing", {}).get("id") or cr.json().get("id")
    assert lid

    r = requests.post(f"{BASE}/deployments/checkout", headers=admin_h,
                      json={"listing_id": lid, "mode": "rent"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("session_id") and "stripe.com" in d.get("url", "")


# ───── armory build-bot auth gate ─────
def test_armory_build_bot_requires_auth():
    r = requests.post(f"{BASE}/armory/build-bot", json={"prompt": "x"}, timeout=10)
    assert r.status_code in (401, 403), r.text


# ───── exchange ─────
def test_exchange_listings_public():
    r = requests.get(f"{BASE}/exchange/listings", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, (list, dict))


def test_exchange_direct_invalid_trigger_422(admin_h):
    r = requests.post(f"{BASE}/exchange/listings/direct", headers=admin_h, json={
        "name": "TEST_bad_trigger", "description": "x" * 80,
        "category": "automation",
        "rent_price": 0, "buy_price": 0,
        "avatar_icon": "Bot", "avatar_color": "indigo",
        "trigger_type": "INVALID_TRIGGER_XYZ", "engine": "gemini-flash",
        "required_integrations": [], "files": [], "nodes": [], "edges": [],
    }, timeout=15)
    assert r.status_code == 422, r.text


# ───── BYOK ─────
def test_byok_stripe_roundtrip_and_probe(user_h):
    payload = {"service": "stripe", "api_key": "sk_test_FAKE_iter39_" + uuid.uuid4().hex[:8]}
    r = requests.post(f"{BASE}/workflows/credentials", headers=user_h, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    g = requests.get(f"{BASE}/workflows/credentials", headers=user_h, timeout=15).json()
    creds = g.get("credentials") or g.get("items") or g
    items = creds if isinstance(creds, list) else creds.get("credentials", [])
    stripe = next((c for c in items if c.get("service") == "stripe"), None)
    assert stripe is not None
    assert "FAKE_iter39" not in json.dumps(stripe)  # masked
    # Probe
    p = requests.post(f"{BASE}/workflows/credentials/stripe/test", headers=user_h, timeout=20)
    assert p.status_code == 200, p.text
    pd = p.json()
    assert "ok" in pd and "status_code" in pd and "latency_ms" in pd
    assert pd["ok"] is False  # fake key


def test_byok_whitelist_rejects_invalid_service(user_h):
    r = requests.post(f"{BASE}/workflows/credentials", headers=user_h,
                      json={"service": "invalid_service_xyz", "api_key": "x"}, timeout=15)
    assert r.status_code in (400, 422), r.text


@pytest.mark.parametrize("svc", ["stripe", "openai", "github", "telegram", "slack"])
def test_byok_probes_structured_response(user_h, svc):
    # Seed a fake credential (best-effort)
    requests.post(f"{BASE}/workflows/credentials", headers=user_h,
                  json={"service": svc, "api_key": "FAKE_" + svc}, timeout=15)
    r = requests.post(f"{BASE}/workflows/credentials/{svc}/test", headers=user_h, timeout=25)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("ok", "status_code", "detail", "latency_ms"):
        assert k in d, f"{svc} probe missing key {k}: {d}"
