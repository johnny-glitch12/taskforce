"""
Iter35 — Usage Monitor backend endpoints
Covers:
- POST /api/deployments/{id}/run (now persists deployment_runs)
- GET /api/deployments/{id}/runs (pagination, owner-only)
- GET /api/deployments/{id}/analytics (totals, latency, daily, quota, errors)
- Regression: /api/auth/login, /api/credits/me, /api/deployments/me,
  /api/exchange/listings (public), /api/exchange/listings/direct (admin)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-memory-hub-5.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_deployment_id(admin_headers):
    """Reuse existing admin deployment or create one via a free listing."""
    r = requests.get(f"{BASE_URL}/api/deployments/me", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    deps = r.json().get("deployments", [])
    if deps:
        return deps[0]["id"]
    # create a free listing (admin) + deploy
    listing_payload = {
        "name": f"TEST_iter35_{uuid.uuid4().hex[:6]}",
        "tagline": "test", "description": "test", "category": "general",
        "rent_price": 0, "buy_price": 0, "status": "published",
        "nodes_snapshot": [], "edges_snapshot": [],
    }
    lr = requests.post(f"{BASE_URL}/api/exchange/listings/direct",
                       headers=admin_headers, json=listing_payload, timeout=20)
    assert lr.status_code in (200, 201), lr.text
    lid = lr.json().get("listing", lr.json()).get("id") or lr.json().get("id")
    dr = requests.post(f"{BASE_URL}/api/deployments/free", headers=admin_headers,
                       json={"listing_id": lid, "mode": "free"}, timeout=20)
    assert dr.status_code == 200, dr.text
    return dr.json()["deployment_id"]


# ───────────── Regression sanity ─────────────
class TestRegression:
    def test_login_ok(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
        assert r.status_code == 200
        assert "token" in r.json()

    def test_credits_me(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/credits/me", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "packs" in d and "action_costs" in d

    def test_deployments_me(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/deployments/me", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json().get("deployments"), list)

    def test_exchange_listings_public(self):
        r = requests.get(f"{BASE_URL}/api/exchange/listings", timeout=20)
        assert r.status_code == 200


# ───────────── /run persists to deployment_runs ─────────────
class TestRunPersistence:
    def test_run_three_times_and_listed(self, admin_headers, admin_deployment_id):
        # call /run 3 times
        run_ids = []
        for _ in range(3):
            r = requests.post(f"{BASE_URL}/api/deployments/{admin_deployment_id}/run",
                              headers=admin_headers, timeout=20)
            assert r.status_code == 200, r.text
            j = r.json()
            assert j.get("allowed") is True, j
            assert "run_id" in j and "duration_ms" in j and "success" in j
            run_ids.append(j["run_id"])
        # fetch runs and confirm the 3 IDs present in first page
        r = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/runs?limit=50",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("runs", "total", "limit", "skip"):
            assert k in body
        assert body["total"] >= 3
        runs = body["runs"]
        # validate shape
        first = runs[0]
        for f in ("id", "status", "duration_ms", "credits_spent", "started_at", "trigger"):
            assert f in first, f"missing {f} in {first}"
        assert first["status"] in ("success", "failed")
        ids_returned = [r["id"] for r in runs]
        for rid in run_ids:
            assert rid in ids_returned

    def test_runs_pagination_and_cap(self, admin_headers, admin_deployment_id):
        r = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/runs?limit=2&skip=0",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 2
        assert len(body["runs"]) <= 2
        # cap at 200
        r2 = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/runs?limit=10000",
                          headers=admin_headers, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["limit"] == 200

    def test_runs_other_deployment_404(self, admin_headers):
        bogus = uuid.uuid4().hex
        r = requests.get(f"{BASE_URL}/api/deployments/{bogus}/runs", headers=admin_headers, timeout=20)
        assert r.status_code == 404


# ───────────── Analytics ─────────────
class TestAnalytics:
    def test_analytics_default_30_days(self, admin_headers, admin_deployment_id):
        r = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/analytics",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("totals", "latency_ms", "daily", "monthly_quota", "recent_errors"):
            assert k in d
        t = d["totals"]
        for k in ("runs", "successes", "failures", "success_rate", "credits_spent"):
            assert k in t
        lat = d["latency_ms"]
        for k in ("avg", "p50", "p95", "p99", "min", "max"):
            assert k in lat
        q = d["monthly_quota"]
        for k in ("used", "limit", "remaining"):
            assert k in q
        # daily 30 entries (incl. zero-days)
        assert len(d["daily"]) == 30
        # each daily entry has date/runs/success/failed
        for e in d["daily"]:
            for f in ("date", "runs", "success", "failed"):
                assert f in e
        assert len(d["recent_errors"]) <= 5

    def test_analytics_days_clamping(self, admin_headers, admin_deployment_id):
        r1 = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/analytics?days=1",
                          headers=admin_headers, timeout=30)
        assert r1.status_code == 200
        assert len(r1.json()["daily"]) == 1

        r2 = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/analytics?days=90",
                          headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        assert len(r2.json()["daily"]) == 90

        # over 90 should be clamped to 90
        r3 = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/analytics?days=500",
                          headers=admin_headers, timeout=30)
        assert r3.status_code == 200
        assert len(r3.json()["daily"]) == 90

        # under 1 should be clamped to 1
        r4 = requests.get(f"{BASE_URL}/api/deployments/{admin_deployment_id}/analytics?days=0",
                          headers=admin_headers, timeout=30)
        assert r4.status_code == 200
        assert len(r4.json()["daily"]) == 1

    def test_analytics_non_owner_404(self, admin_headers):
        bogus = uuid.uuid4().hex
        r = requests.get(f"{BASE_URL}/api/deployments/{bogus}/analytics",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 404

    def test_percentile_calculation_logic(self):
        """Replicate the _pct algorithm to validate percentile math contract.
        durations = [100..1000 step 100]; p50≈500, p95≈1000, p99≈1000."""
        durations = sorted([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
        def _pct(p):
            i = max(0, min(len(durations) - 1, int(round((p / 100) * (len(durations) - 1)))))
            return durations[i]
        assert _pct(50) == 500
        assert _pct(95) == 1000
        assert _pct(99) == 1000
