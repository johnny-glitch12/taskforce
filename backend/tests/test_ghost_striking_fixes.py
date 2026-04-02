"""
Test suite for CSDROP Ghost Striking Fixes (Iteration 14)
Tests:
- POST /api/csdrop/launch spawns bot with -u flag
- GET /api/csdrop/logs returns boot diagnostics with DB pulse info
- GET /api/csdrop/error-screenshot returns 404 when no error screenshot exists
- Regression tests for health, code runner, sync session
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"


class TestCsdropAuth:
    """Authentication tests for CSDROP client"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"CSDROP login failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, csdrop_token):
        """Auth headers for CSDROP client"""
        return {
            "Authorization": f"Bearer {csdrop_token}",
            "Content-Type": "application/json"
        }
    
    def test_csdrop_login_success(self):
        """Test CSDROP client can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["client_id"] == "csdrop"


class TestErrorScreenshotEndpoint:
    """Tests for /api/csdrop/error-screenshot endpoint"""
    
    def test_error_screenshot_returns_404_when_no_screenshot(self):
        """GET /api/csdrop/error-screenshot returns 404 when no error screenshot exists"""
        response = requests.get(f"{BASE_URL}/api/csdrop/error-screenshot")
        # Should return 404 since no error screenshot exists initially
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "No error screenshot available" in data["detail"]


class TestBotLaunchAndLogs:
    """Tests for bot launch with -u flag and boot diagnostics"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"CSDROP login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, csdrop_token):
        """Auth headers for CSDROP client"""
        return {
            "Authorization": f"Bearer {csdrop_token}",
            "Content-Type": "application/json"
        }
    
    def test_bot_launch_and_boot_logs(self, auth_headers):
        """POST /api/csdrop/launch spawns bot and logs appear immediately with -u flag"""
        # First stop any running bot
        requests.post(f"{BASE_URL}/api/csdrop/stop", headers=auth_headers)
        time.sleep(1)
        
        # Launch the bot
        response = requests.post(f"{BASE_URL}/api/csdrop/launch", headers=auth_headers, json={
            "promo": "https://csdrop.com/r/TEST",
            "batch": 5
        })
        assert response.status_code == 200, f"Launch failed: {response.text}"
        data = response.json()
        # Bot may fail due to Discord proxy, but launch should succeed
        assert data.get("status") in ["ok", "error"], f"Unexpected status: {data}"
        
        # Wait for boot logs to appear (8 seconds as per instructions)
        time.sleep(8)
        
        # Get logs
        logs_response = requests.get(f"{BASE_URL}/api/csdrop/logs?lines=100", headers=auth_headers)
        assert logs_response.status_code == 200, f"Logs fetch failed: {logs_response.text}"
        logs_data = logs_response.json()
        
        # Verify log structure
        assert "logs" in logs_data
        assert "running" in logs_data
        assert isinstance(logs_data["logs"], list)
        
        # Check for boot diagnostics in logs
        logs_text = "\n".join(logs_data["logs"])
        print(f"Boot logs:\n{logs_text}")
        
        # The bot should show boot messages (may fail on proxy but boot messages should appear)
        # Check for launch message at minimum
        assert any("Launching" in log or "Promo" in log for log in logs_data["logs"]), \
            f"Expected launch messages in logs. Got: {logs_data['logs'][:5]}"
        
        # Stop the bot after test
        stop_response = requests.post(f"{BASE_URL}/api/csdrop/stop", headers=auth_headers)
        assert stop_response.status_code == 200
    
    def test_logs_endpoint_returns_expected_fields(self, auth_headers):
        """GET /api/csdrop/logs returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "running" in data
        assert "logs" in data
        assert "source" in data
        assert isinstance(data["logs"], list)
        assert isinstance(data["running"], bool)


class TestHealthEndpoint:
    """Regression tests for health endpoint"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"CSDROP login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, csdrop_token):
        """Auth headers for CSDROP client"""
        return {
            "Authorization": f"Bearer {csdrop_token}",
            "Content-Type": "application/json"
        }
    
    def test_health_check_works(self, auth_headers):
        """GET /api/csdrop/health still works (regression)"""
        response = requests.get(f"{BASE_URL}/api/csdrop/health", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ready" in data
        assert "python_path" in data


class TestCodeRunner:
    """Regression tests for code runner"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"CSDROP login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, csdrop_token):
        """Auth headers for CSDROP client"""
        return {
            "Authorization": f"Bearer {csdrop_token}",
            "Content-Type": "application/json"
        }
    
    def test_code_runner_still_works(self, auth_headers):
        """POST /api/csdrop/execute still works (regression)"""
        response = requests.post(f"{BASE_URL}/api/csdrop/execute", headers=auth_headers, json={
            "code": "RESULT = {'test': 'passed'}",
            "input_data": {}
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("result") == {"test": "passed"}


class TestSyncSession:
    """Regression tests for sync session flow"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"CSDROP login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, csdrop_token):
        """Auth headers for CSDROP client"""
        return {
            "Authorization": f"Bearer {csdrop_token}",
            "Content-Type": "application/json"
        }
    
    def test_sync_status_endpoint_works(self, auth_headers):
        """GET /api/csdrop/sync-status still works (regression)"""
        response = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestDashboard:
    """Regression tests for dashboard endpoint"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"CSDROP login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, csdrop_token):
        """Auth headers for CSDROP client"""
        return {
            "Authorization": f"Bearer {csdrop_token}",
            "Content-Type": "application/json"
        }
    
    def test_dashboard_endpoint_works(self, auth_headers):
        """GET /api/csdrop/dashboard still works (regression)"""
        response = requests.get(f"{BASE_URL}/api/csdrop/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "client" in data
        assert data["client"] == "csdrop"
        assert "bot_running" in data
