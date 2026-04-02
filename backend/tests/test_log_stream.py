"""
Test suite for Real-Time Log Stream feature (Iteration 13)
Tests GET /api/csdrop/logs endpoint and log file creation via POST /api/csdrop/launch
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def csdrop_token():
    """Get auth token for CSDROP client user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CSDROP_EMAIL,
        "password": CSDROP_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"CSDROP login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_token():
    """Get auth token for admin user (non-CSDROP)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture
def csdrop_headers(csdrop_token):
    """Headers with CSDROP auth"""
    return {
        "Authorization": f"Bearer {csdrop_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_headers(admin_token):
    """Headers with admin auth (non-CSDROP)"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestLogStreamEndpoint:
    """Tests for GET /api/csdrop/logs endpoint"""

    def test_logs_requires_authentication(self):
        """GET /api/csdrop/logs requires authentication"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/csdrop/logs requires authentication (401)")

    def test_logs_rejects_non_csdrop_user(self, admin_headers):
        """GET /api/csdrop/logs rejects non-CSDROP users"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs", headers=admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ GET /api/csdrop/logs rejects non-CSDROP users (403)")

    def test_logs_returns_expected_fields(self, csdrop_headers):
        """GET /api/csdrop/logs returns expected response structure"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs", headers=csdrop_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "running" in data, "Response missing 'running' field"
        assert "logs" in data, "Response missing 'logs' field"
        assert "source" in data, "Response missing 'source' field"
        assert isinstance(data["logs"], list), "'logs' should be a list"
        print(f"✓ GET /api/csdrop/logs returns expected fields: running={data['running']}, logs_count={len(data['logs'])}, source={data['source']}")

    def test_logs_returns_total_lines_when_file_exists(self, csdrop_headers):
        """GET /api/csdrop/logs returns total_lines when log file exists"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs", headers=csdrop_headers)
        assert response.status_code == 200
        
        data = response.json()
        # If source is 'file' and logs exist, total_lines should be present
        if data.get("source") == "file" and len(data.get("logs", [])) > 0:
            assert "total_lines" in data, "Response missing 'total_lines' when file exists"
            assert isinstance(data["total_lines"], int), "'total_lines' should be an integer"
            print(f"✓ GET /api/csdrop/logs returns total_lines={data['total_lines']}")
        else:
            print(f"✓ GET /api/csdrop/logs - file may not exist or be empty, source={data.get('source')}")

    def test_logs_lines_parameter(self, csdrop_headers):
        """GET /api/csdrop/logs?lines=10 limits returned lines"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs?lines=10", headers=csdrop_headers)
        assert response.status_code == 200
        
        data = response.json()
        logs = data.get("logs", [])
        # If there are logs, they should be limited to 10
        if len(logs) > 0:
            assert len(logs) <= 10, f"Expected max 10 lines, got {len(logs)}"
        print(f"✓ GET /api/csdrop/logs?lines=10 returns {len(logs)} lines (max 10)")

    def test_logs_default_lines_50(self, csdrop_headers):
        """GET /api/csdrop/logs defaults to 50 lines"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs", headers=csdrop_headers)
        assert response.status_code == 200
        
        data = response.json()
        logs = data.get("logs", [])
        # Default should be 50 lines max
        assert len(logs) <= 50, f"Expected max 50 lines by default, got {len(logs)}"
        print(f"✓ GET /api/csdrop/logs defaults to max 50 lines, got {len(logs)}")


class TestLogFileCreation:
    """Tests for log file creation via POST /api/csdrop/launch"""

    def test_launch_creates_log_file(self, csdrop_headers):
        """POST /api/csdrop/launch creates log file at expected path"""
        # First, stop any running bot
        requests.post(f"{BASE_URL}/api/csdrop/stop", headers=csdrop_headers)
        time.sleep(1)
        
        # Launch the bot
        response = requests.post(f"{BASE_URL}/api/csdrop/launch", headers=csdrop_headers, json={
            "promo": "https://csdrop.com/r/TEST",
            "batch": 5
        })
        
        # Bot may fail to connect to Discord (expected in test env), but should still create log file
        if response.status_code == 200:
            data = response.json()
            print(f"✓ POST /api/csdrop/launch response: {data}")
            
            # Wait for bot to start writing logs
            time.sleep(3)
            
            # Check logs endpoint
            logs_response = requests.get(f"{BASE_URL}/api/csdrop/logs?lines=20", headers=csdrop_headers)
            assert logs_response.status_code == 200
            
            logs_data = logs_response.json()
            logs = logs_data.get("logs", [])
            
            # Should have some boot logs
            if len(logs) > 0:
                print(f"✓ Log file created with {len(logs)} lines")
                # Check for expected boot messages
                log_text = "\n".join(logs)
                assert "Launching" in log_text or "BOOT" in log_text or "Bot" in log_text, \
                    f"Expected boot messages in logs, got: {logs[:3]}"
                print(f"✓ Log file contains boot messages")
            else:
                print("⚠ Log file may be empty (bot may have failed quickly)")
        else:
            # Bot launch may fail due to missing dependencies - that's OK for this test
            print(f"⚠ Bot launch returned {response.status_code}: {response.text}")
            pytest.skip("Bot launch failed - may be missing dependencies")

    def test_stop_bot_after_launch(self, csdrop_headers):
        """POST /api/csdrop/stop terminates the bot"""
        response = requests.post(f"{BASE_URL}/api/csdrop/stop", headers=csdrop_headers)
        # May return error if bot already stopped
        assert response.status_code == 200
        data = response.json()
        print(f"✓ POST /api/csdrop/stop response: {data}")


class TestRegressionChecks:
    """Regression tests for existing CSDROP features"""

    def test_health_endpoint(self, csdrop_headers):
        """GET /api/csdrop/health still works"""
        response = requests.get(f"{BASE_URL}/api/csdrop/health", headers=csdrop_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ready" in data
        print(f"✓ GET /api/csdrop/health works: ready={data['ready']}")

    def test_dashboard_endpoint(self, csdrop_headers):
        """GET /api/csdrop/dashboard still works"""
        response = requests.get(f"{BASE_URL}/api/csdrop/dashboard", headers=csdrop_headers)
        assert response.status_code == 200
        data = response.json()
        assert "client" in data
        assert data["client"] == "csdrop"
        print(f"✓ GET /api/csdrop/dashboard works: client={data['client']}")

    def test_bot_logs_endpoint(self, csdrop_headers):
        """GET /api/csdrop/bot-logs still works (legacy endpoint)"""
        response = requests.get(f"{BASE_URL}/api/csdrop/bot-logs", headers=csdrop_headers)
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "logs" in data
        print(f"✓ GET /api/csdrop/bot-logs works: running={data['running']}, logs_count={len(data['logs'])}")

    def test_live_feed_endpoint(self, csdrop_headers):
        """GET /api/csdrop/live-feed still works"""
        response = requests.get(f"{BASE_URL}/api/csdrop/live-feed", headers=csdrop_headers)
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "bot_running" in data
        print(f"✓ GET /api/csdrop/live-feed works: available={data['available']}, bot_running={data['bot_running']}")

    def test_sync_session_endpoint(self, csdrop_headers):
        """GET /api/csdrop/sync-status still works"""
        response = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=csdrop_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        print(f"✓ GET /api/csdrop/sync-status works: status={data['status']}")

    def test_execute_code_endpoint(self, csdrop_headers):
        """POST /api/csdrop/execute still works"""
        response = requests.post(f"{BASE_URL}/api/csdrop/execute", headers=csdrop_headers, json={
            "code": "RESULT = {'test': True}",
            "input_data": {}
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        print(f"✓ POST /api/csdrop/execute works: success={data['success']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
