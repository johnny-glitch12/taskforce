"""
Prompt 22 — backend regression for the new waitlist `source` field.

The Academy "Notify Me" form posts {email, source:"academy"} to /api/waitlist.
"""
import os
import requests

API = (os.environ.get("E2E_API_URL") or os.environ.get(
    "REACT_APP_BACKEND_URL", "http://localhost:8001"
).rstrip("/") + "/api")


def test_waitlist_accepts_source_field():
    r = requests.post(
        f"{API}/waitlist",
        json={"email": "iter63-academy@example.com", "source": "academy"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == "iter63-academy@example.com"
    assert "id" in data


def test_waitlist_legacy_payload_still_works():
    """Source is optional — pre-existing landing forms must continue to work."""
    r = requests.post(
        f"{API}/waitlist",
        json={"email": "iter63-legacy@example.com"},
        timeout=10,
    )
    assert r.status_code == 200, r.text


def test_waitlist_count_endpoint():
    r = requests.get(f"{API}/waitlist/count", timeout=5)
    assert r.status_code == 200
    assert "count" in r.json()
