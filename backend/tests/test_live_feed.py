"""
Test suite for CSDROP Live Satellite Feed feature.
Tests the live-feed status endpoint and live-feed/image endpoint.
"""
import pytest
import requests
import os
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"

# Static file path for testing
STATIC_DIR = Path(__file__).parent.parent / "static"
LIVE_STREAM_PATH = STATIC_DIR / "live_stream.jpg"


@pytest.fixture(scope="module")
def csdrop_token():
    """Get CSDROP user authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": CSDROP_EMAIL, "password": CSDROP_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("CSDROP authentication failed")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin user authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def csdrop_headers(csdrop_token):
    """Headers for CSDROP authenticated requests."""
    return {
        "Authorization": f"Bearer {csdrop_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_headers(admin_token):
    """Headers for admin authenticated requests."""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestLiveFeedStatusEndpoint:
    """Tests for GET /api/csdrop/live-feed status endpoint."""

    def test_live_feed_status_requires_auth(self):
        """Live feed status endpoint requires authentication."""
        response = requests.get(f"{BASE_URL}/api/csdrop/live-feed")
        assert response.status_code == 401
        print("PASS: Live feed status requires authentication")

    def test_live_feed_status_requires_csdrop_user(self, admin_headers):
        """Live feed status endpoint rejects non-CSDROP users."""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/live-feed",
            headers=admin_headers
        )
        assert response.status_code == 403
        print("PASS: Live feed status rejects admin user (403)")

    def test_live_feed_status_returns_availability(self, csdrop_headers):
        """Live feed status returns availability info."""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/live-feed",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "available" in data
        assert "bot_running" in data
        assert "last_updated" in data
        
        # Verify data types
        assert isinstance(data["available"], bool)
        assert isinstance(data["bot_running"], bool)
        
        print(f"PASS: Live feed status returns: available={data['available']}, bot_running={data['bot_running']}")

    def test_live_feed_status_shows_available_when_file_exists(self, csdrop_headers):
        """Live feed status shows available=true when screenshot file exists."""
        # Ensure file exists
        assert LIVE_STREAM_PATH.exists(), "Test placeholder file should exist"
        
        response = requests.get(
            f"{BASE_URL}/api/csdrop/live-feed",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["available"] == True
        assert data["last_updated"] is not None
        print("PASS: Live feed status shows available=true when file exists")


class TestLiveFeedImageEndpoint:
    """Tests for GET /api/csdrop/live-feed/image endpoint."""

    def test_live_feed_image_no_auth_required(self):
        """Live feed image endpoint has NO auth guard (for <img src> usage)."""
        response = requests.get(f"{BASE_URL}/api/csdrop/live-feed/image")
        # Should return 200 (image) or 404 (no file), but NOT 401
        assert response.status_code in [200, 404]
        assert response.status_code != 401
        print("PASS: Live feed image endpoint has no auth guard")

    def test_live_feed_image_returns_jpeg_when_exists(self):
        """Live feed image returns JPEG with correct content-type when file exists."""
        # Ensure file exists
        assert LIVE_STREAM_PATH.exists(), "Test placeholder file should exist"
        
        response = requests.get(f"{BASE_URL}/api/csdrop/live-feed/image")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "image/jpeg"
        assert len(response.content) > 0
        print(f"PASS: Live feed image returns JPEG ({len(response.content)} bytes)")

    def test_live_feed_image_has_no_cache_headers(self):
        """Live feed image has no-cache headers for real-time updates."""
        # Ensure file exists
        assert LIVE_STREAM_PATH.exists(), "Test placeholder file should exist"
        
        response = requests.get(f"{BASE_URL}/api/csdrop/live-feed/image")
        assert response.status_code == 200
        
        cache_control = response.headers.get("cache-control", "")
        pragma = response.headers.get("pragma", "")
        
        # Check for no-cache directives
        assert "no-cache" in cache_control or "no-store" in cache_control
        print(f"PASS: Live feed image has no-cache headers: {cache_control}")

    def test_live_feed_image_returns_404_when_no_file(self):
        """Live feed image returns 404 when screenshot file doesn't exist."""
        # Temporarily rename the file
        backup_path = LIVE_STREAM_PATH.with_suffix(".jpg.bak")
        file_existed = LIVE_STREAM_PATH.exists()
        
        if file_existed:
            LIVE_STREAM_PATH.rename(backup_path)
        
        try:
            response = requests.get(f"{BASE_URL}/api/csdrop/live-feed/image")
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "No feed available" in data["detail"]
            print("PASS: Live feed image returns 404 when file doesn't exist")
        finally:
            # Restore the file
            if file_existed and backup_path.exists():
                backup_path.rename(LIVE_STREAM_PATH)


class TestSovereignPyIntegration:
    """Tests for sovereign.py bot integration with live feed."""

    def test_screenshot_path_constant_exists(self):
        """sovereign.py defines SCREENSHOT_PATH constant."""
        sovereign_path = Path(__file__).parent.parent / "clients" / "csdrop" / "sovereign.py"
        assert sovereign_path.exists(), "sovereign.py should exist"
        
        content = sovereign_path.read_text()
        assert "SCREENSHOT_PATH" in content
        assert "live_stream.jpg" in content
        print("PASS: sovereign.py defines SCREENSHOT_PATH for live_stream.jpg")

    def test_capture_feed_function_exists(self):
        """sovereign.py defines _capture_feed function."""
        sovereign_path = Path(__file__).parent.parent / "clients" / "csdrop" / "sovereign.py"
        content = sovereign_path.read_text()
        
        assert "async def _capture_feed" in content
        assert "page.screenshot" in content
        print("PASS: sovereign.py defines _capture_feed function")

    def test_stealth_async_import(self):
        """sovereign.py uses stealth_async (not Stealth class)."""
        sovereign_path = Path(__file__).parent.parent / "clients" / "csdrop" / "sovereign.py"
        content = sovereign_path.read_text()
        
        assert "from playwright_stealth import stealth_async" in content
        assert "await stealth_async(page)" in content
        # Should NOT have the old Stealth class import
        assert "from playwright_stealth import Stealth" not in content
        print("PASS: sovereign.py uses stealth_async correctly")

    def test_capture_feed_called_at_key_points(self):
        """sovereign.py calls _capture_feed at key action points."""
        sovereign_path = Path(__file__).parent.parent / "clients" / "csdrop" / "sovereign.py"
        content = sovereign_path.read_text()
        
        # Count _capture_feed calls
        capture_calls = content.count("await _capture_feed(")
        assert capture_calls >= 3, f"Expected at least 3 _capture_feed calls, found {capture_calls}"
        print(f"PASS: sovereign.py calls _capture_feed {capture_calls} times at key points")


class TestCsdropDashboardIntegration:
    """Tests for CSDROP dashboard still working with live feed."""

    def test_csdrop_dashboard_endpoint_works(self, csdrop_headers):
        """CSDROP dashboard endpoint still works."""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/dashboard",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "client" in data
        assert data["client"] == "csdrop"
        assert "bot_running" in data
        print("PASS: CSDROP dashboard endpoint works")

    def test_csdrop_health_endpoint_works(self, csdrop_headers):
        """CSDROP health endpoint still works."""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/health",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ready" in data
        print("PASS: CSDROP health endpoint works")

    def test_csdrop_execute_endpoint_works(self, csdrop_headers):
        """CSDROP code execution endpoint still works."""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={
                "code": "RESULT = {'test': 'ok'}",
                "input_data": {}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["result"]["test"] == "ok"
        print("PASS: CSDROP code execution works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
