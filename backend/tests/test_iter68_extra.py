"""
test_iter68_extra — Additional Prompt 25 coverage requested by E1:
  • /api/auth/check-username rate limiting (10/min, 11th → 429)
  • Register 422 details for 'my user' (space), 'a' (too short)
  • Register success → DB has username_lower = lowercase
  • Login by username works (not just email)
"""
from __future__ import annotations

import os
import sys
import uuid
import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = os.environ.get("PUBLIC_API_BASE") or "http://localhost:8001"
PW = "MyP@ssw0rd!Extra"


def _delete(emails=None, usernames=None):
    from pymongo import MongoClient
    cli = MongoClient(os.environ["MONGO_URL"])
    db = cli[os.environ.get("DB_NAME", "taskforce")]
    if emails:
        db.users.delete_many({"email": {"$in": emails}})
    if usernames:
        db.users.delete_many({"username_lower": {"$in": [u.lower() for u in usernames]}})
    cli.close()


def test_check_username_rate_limit_429():
    """11 rapid requests from same IP hit the 10/min cap → 429."""
    statuses = []
    for i in range(13):
        r = httpx.get(f"{API}/api/auth/check-username",
                      params={"username": f"probe_{uuid.uuid4().hex[:6]}"}, timeout=5)
        statuses.append(r.status_code)
    assert 429 in statuses, f"Expected 429 after >10 reqs, got: {statuses}"


def test_register_422_space_in_username():
    n = uuid.uuid4().hex[:8]
    r = httpx.post(f"{API}/api/auth/register", json={
        "email": f"qa-space-{n}@test.dev",
        "password": PW,
        "username": "my user",
    }, timeout=10)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["error"] == "validation_failed"
    # Should error on format (letters/numbers/underscore only)
    assert any("letters" in e.lower() or "underscore" in e.lower() for e in d["details"])


def test_register_422_username_too_short():
    n = uuid.uuid4().hex[:8]
    r = httpx.post(f"{API}/api/auth/register", json={
        "email": f"qa-short-{n}@test.dev",
        "password": PW,
        "username": "a",
    }, timeout=10)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert any("3-20" in e or "characters" in e.lower() for e in d["details"])


def test_register_persists_username_lower_in_db():
    from pymongo import MongoClient
    n = uuid.uuid4().hex[:8]
    username = f"qa_DB_{n}"
    email = f"qa-db-{n}@test.dev"
    try:
        r = httpx.post(f"{API}/api/auth/register", json={
            "email": email, "password": PW, "username": username,
        }, timeout=10)
        assert r.status_code == 200, r.text

        cli = MongoClient(os.environ["MONGO_URL"])
        doc = cli[os.environ.get("DB_NAME", "taskforce")].users.find_one({"email": email})
        cli.close()
        assert doc is not None
        assert doc.get("username") == username
        assert doc.get("username_lower") == username.lower()
    finally:
        _delete(emails=[email])


def test_login_with_username_string():
    """Register a fresh user, then login using their USERNAME (not email)."""
    n = uuid.uuid4().hex[:6]
    username = f"qa_log_{n}"
    email = f"qa-login-{n}@test.dev"
    try:
        r = httpx.post(f"{API}/api/auth/register", json={
            "email": email, "password": PW, "username": username,
        }, timeout=10)
        assert r.status_code == 200, r.text

        login = httpx.post(f"{API}/api/auth/login", json={
            "email": username,  # username string in the 'email' field
            "password": PW,
        }, timeout=10)
        assert login.status_code == 200
        body = login.json()
        assert "token" in body
        assert body["user"]["email"] == email
    finally:
        _delete(emails=[email])


def test_admin_legacy_email_login_still_works():
    """Phase 68 legacy admin user (no username field) still logs in via email."""
    r = httpx.post(f"{API}/api/auth/login", json={
        "email": "admin@nova.ai", "password": "admin123",
    }, timeout=10)
    assert r.status_code == 200, r.text
    assert "token" in r.json()
