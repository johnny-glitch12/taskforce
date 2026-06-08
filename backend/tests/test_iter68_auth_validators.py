"""
test_iter68_auth_validators — Username + password validation hardening (Prompt 25).

Covers:
  • lib.auth_validators.check_password — rule flags + score 0..4
  • lib.auth_validators.check_username — rule flags + reserved blocklist
  • lib.auth_validators.validate_signup — bulk validator combining both
  • POST /api/auth/register — 422 with structured details on bad password / reserved username
  • POST /api/auth/register — succeeds with valid payload, persists username + username_lower
  • POST /api/auth/login — accepts USERNAME (not just email)
  • POST /api/auth/login — generic "Invalid username or password" error
  • GET  /api/auth/check-username — available / taken / reserved / invalid / too_short responses
"""
from __future__ import annotations

import os
import sys
import uuid
import asyncio
import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.auth_validators import check_password, check_username, validate_signup, RESERVED_USERNAMES

API = os.environ.get("PUBLIC_API_BASE") or "http://localhost:8001"


# ─── Pure validator tests ──────────────────────────────
def test_check_password_strong():
    r = check_password("MyP@ssw0rd!Extra", username="someone", email="u@x.com")
    assert r["ok"] is True
    assert r["score"] == 4  # ≥12 chars + 4 char types
    assert r["errors"] == []


def test_check_password_blocks_lowercase_only():
    r = check_password("alllowercase", username="", email="")
    assert r["ok"] is False
    assert r["score"] == 1  # length met only
    assert any("uppercase" in e for e in r["errors"])
    assert any("number" in e for e in r["errors"])
    assert any("special character" in e for e in r["errors"])


def test_check_password_blocks_no_special():
    r = check_password("Password1", username="", email="")
    assert r["ok"] is False
    assert r["score"] == 3  # Good — 3 of 4 char types
    assert len(r["errors"]) == 1
    assert "special character" in r["errors"][0]


def test_check_password_blocks_matches_username():
    r = check_password("Operator123!", username="Operator123!", email="x@y.com")
    assert r["ok"] is False
    assert any("username or email" in e for e in r["errors"])


def test_check_password_blocks_matches_email_prefix():
    r = check_password("Johnny99!", username="johnny", email="Johnny99!@x.com")
    # password equals email local part case-insensitively → blocked
    assert r["ok"] is False
    assert any("username or email" in e for e in r["errors"])


def test_check_password_blocks_trailing_space():
    r = check_password(" MyP@ssw0rd!", username="", email="")
    assert r["ok"] is False
    assert any("whitespace" in e for e in r["errors"])


def test_check_password_score_progression():
    # weak/fair/good/strong staircase, all with length=8+
    assert check_password("alllowercase", "", "")["score"] == 1  # Weak
    assert check_password("Alllowercase", "", "")["score"] == 2  # Fair
    assert check_password("Alllowerc1se", "", "")["score"] == 3  # Good
    assert check_password("Alllowerc1se!", "", "")["score"] == 4  # Strong (≥12)


def test_check_username_format():
    assert check_username("abc")["ok"] is True
    assert check_username("ab")["ok"] is False  # too short
    assert check_username("1abc")["ok"] is False  # starts with digit
    assert check_username("_abc")["ok"] is False  # starts with underscore
    assert check_username("abc-def")["ok"] is False  # dash not allowed
    assert check_username("abc def")["ok"] is False  # space not allowed
    assert check_username("a" * 21)["ok"] is False  # too long


def test_check_username_reserved():
    for w in ("admin", "root", "system", "ROOT", "Admin"):
        r = check_username(w)
        assert r["ok"] is False
        assert any("reserved" in e.lower() for e in r["errors"])


def test_validate_signup_aggregates():
    r = validate_signup(username="admin", email="x@y.com", password="weak")
    assert r["ok"] is False
    assert len(r["errors"]) > 1  # both username + password issues


# ─── Endpoint tests ────────────────────────────────────
def test_check_username_endpoint_reasons():
    too_short = httpx.get(f"{API}/api/auth/check-username", params={"username": "ab"}, timeout=10).json()
    assert too_short == {"available": False, "reason": "too_short"}
    reserved = httpx.get(f"{API}/api/auth/check-username", params={"username": "admin"}, timeout=10).json()
    assert reserved["available"] is False and reserved["reason"] == "reserved"
    invalid = httpx.get(f"{API}/api/auth/check-username", params={"username": "1bad"}, timeout=10).json()
    assert invalid["available"] is False and invalid["reason"] == "invalid"
    ok = httpx.get(f"{API}/api/auth/check-username", params={"username": f"freshie_{uuid.uuid4().hex[:6]}"}, timeout=10).json()
    assert ok["available"] is True and ok["reason"] == "ok"


def test_register_422_on_bad_password():
    n = uuid.uuid4().hex[:8]
    r = httpx.post(f"{API}/api/auth/register", json={
        "email": f"qa-{n}@test.dev",
        "password": "alllowercase",
        "username": f"qa_{n}",
    }, timeout=10)
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["error"] == "validation_failed"
    assert isinstance(d["details"], list)
    assert any("uppercase" in e for e in d["details"])


def test_register_422_on_reserved_username():
    r = httpx.post(f"{API}/api/auth/register", json={
        "email": f"qa-{uuid.uuid4().hex[:8]}@test.dev",
        "password": "MyP@ssw0rd!Extra",
        "username": "admin",
    }, timeout=10)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert any("reserved" in e.lower() for e in d["details"])


def test_register_succeeds_with_valid_payload():
    n = uuid.uuid4().hex[:8]
    payload = {
        "email": f"qa-{n}@test.dev",
        "password": "MyP@ssw0rd!Extra",
        "username": f"qa_{n}",
        "name": "QA Bot",
    }
    r = httpx.post(f"{API}/api/auth/register", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    assert len(token) > 50

    # The created user can log in with USERNAME (not just email).
    login = httpx.post(f"{API}/api/auth/login", json={
        "email": payload["username"],  # username goes in the 'email' field for compat
        "password": payload["password"],
    }, timeout=10)
    assert login.status_code == 200

    # Cleanup
    from pymongo import MongoClient
    cli = MongoClient(os.environ["MONGO_URL"])
    cli[os.environ.get("DB_NAME", "taskforce")].users.delete_one({"email": payload["email"]})
    cli.close()


def test_register_username_case_insensitive_uniqueness():
    n = uuid.uuid4().hex[:8]
    base = f"qa_{n}"
    pw = "MyP@ssw0rd!Extra"
    r1 = httpx.post(f"{API}/api/auth/register", json={
        "email": f"first-{n}@test.dev", "password": pw, "username": base,
    }, timeout=10)
    assert r1.status_code == 200

    # Second registration with DIFFERENT casing should still collide.
    r2 = httpx.post(f"{API}/api/auth/register", json={
        "email": f"second-{n}@test.dev", "password": pw, "username": base.upper(),
    }, timeout=10)
    assert r2.status_code == 422
    d = r2.json()["detail"]
    assert any("taken" in e.lower() for e in d["details"])

    # Cleanup
    from pymongo import MongoClient
    cli = MongoClient(os.environ["MONGO_URL"])
    cli[os.environ.get("DB_NAME", "taskforce")].users.delete_many({"username_lower": base.lower()})
    cli.close()


def test_login_generic_error_no_enumeration():
    # Wrong password against a known user.
    r1 = httpx.post(f"{API}/api/auth/login", json={
        "email": "admin@nova.ai", "password": "definitely-wrong",
    }, timeout=10)
    assert r1.status_code == 401
    # Non-existent user.
    r2 = httpx.post(f"{API}/api/auth/login", json={
        "email": f"nobody-{uuid.uuid4().hex[:8]}@nope.dev", "password": "whatever",
    }, timeout=10)
    assert r2.status_code == 401
    # Same generic message in BOTH cases — prevents username enumeration.
    assert r1.json()["detail"] == r2.json()["detail"] == "Invalid username or password"
