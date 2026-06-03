"""Iter44 P1 — Promo Codes regression. Verifies admin can create a promo code,
user can redeem once, second redeem returns 409."""
import os
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": pw}, timeout=15)
    return r.json().get("token") or r.json().get("access_token") if r.status_code == 200 else None


def test_promo_create_redeem_and_duplicate():
    token = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert token
    hdrs = {"Authorization": f"Bearer {token}"}
    code = f"TEST{uuid.uuid4().hex[:6].upper()}"

    # Create
    create = requests.post(f"{BASE_URL}/api/promo/codes", headers=hdrs, json={
        "code": code, "kind": "credits", "value": 50, "max_redemptions": 5,
    }, timeout=10)
    assert create.status_code in (200, 201), create.text

    # Redeem first time
    r1 = requests.post(f"{BASE_URL}/api/promo/redeem", headers=hdrs,
                       json={"code": code}, timeout=10)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1.get("granted") == 50, body1

    # Redeem second time — must reject
    r2 = requests.post(f"{BASE_URL}/api/promo/redeem", headers=hdrs,
                       json={"code": code}, timeout=10)
    assert r2.status_code == 409, r2.text


def test_promo_redeem_invalid_code():
    token = _login(ADMIN_EMAIL, ADMIN_PASS)
    hdrs = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/api/promo/redeem", headers=hdrs,
                     json={"code": f"DOESNOTEXIST_{uuid.uuid4().hex[:6]}"}, timeout=10)
    assert r.status_code in (400, 404), r.text
