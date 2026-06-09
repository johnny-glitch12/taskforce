"""Security Audit Log Dashboard tests - admin-only endpoints."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-memory-hub-5.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@nova.ai", "password": "admin123"}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def csdrop_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@csdrop.com", "password": "nova_csdrop_2026"}, timeout=15)
    assert r.status_code == 200
    return r.json()["token"]


# --- /api/security/stats ---
def test_security_stats_no_auth():
    r = requests.get(f"{BASE_URL}/api/security/stats", timeout=15)
    assert r.status_code == 401

def test_security_stats_non_admin(csdrop_token):
    r = requests.get(f"{BASE_URL}/api/security/stats", headers={"Authorization": f"Bearer {csdrop_token}"}, timeout=15)
    assert r.status_code == 403

def test_security_stats_admin(admin_token):
    r = requests.get(f"{BASE_URL}/api/security/stats", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ["total_audits", "blocked", "safe", "suspicious", "unsafe"]:
        assert k in data
        assert isinstance(data[k], int)


# --- /api/security/events ---
def test_security_events_no_auth():
    r = requests.get(f"{BASE_URL}/api/security/events", timeout=15)
    assert r.status_code == 401

def test_security_events_non_admin(csdrop_token):
    r = requests.get(f"{BASE_URL}/api/security/events", headers={"Authorization": f"Bearer {csdrop_token}"}, timeout=15)
    assert r.status_code == 403

def test_security_events_admin(admin_token):
    r = requests.get(f"{BASE_URL}/api/security/events?limit=10", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "events" in data
    assert "total" in data
    assert isinstance(data["events"], list)

def test_security_events_filter_verdict(admin_token):
    r = requests.get(f"{BASE_URL}/api/security/events?verdict=SAFE", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    for ev in data["events"]:
        assert ev.get("verdict") == "SAFE"
