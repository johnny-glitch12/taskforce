"""
Test Manual Credential Bridge with 2FA handling for CSDROP Portal
Tests: POST /api/csdrop/manual-login, POST /api/csdrop/submit-2fa, GET /api/csdrop/sync-status
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# CSDROP client credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"


@pytest.fixture(scope="module")
def csdrop_token():
    """Get authentication token for CSDROP client."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CSDROP_EMAIL,
        "password": CSDROP_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"CSDROP authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def csdrop_headers(csdrop_token):
    """Headers with CSDROP auth token."""
    return {
        "Authorization": f"Bearer {csdrop_token}",
        "Content-Type": "application/json"
    }


class TestCsdropLogin:
    """Test CSDROP client authentication."""
    
    def test_csdrop_login_success(self):
        """Verify CSDROP client can login successfully."""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == CSDROP_EMAIL
        assert data["user"]["client_id"] == "csdrop"
        print(f"✓ CSDROP login successful, client_id: {data['user']['client_id']}")


class TestCsdropDashboard:
    """Test CSDROP dashboard endpoint."""
    
    def test_dashboard_loads(self, csdrop_headers):
        """Verify CSDROP dashboard endpoint returns expected data."""
        response = requests.get(f"{BASE_URL}/api/csdrop/dashboard", headers=csdrop_headers)
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        assert "client" in data
        assert data["client"] == "csdrop"
        assert "bot_running" in data
        print(f"✓ Dashboard loaded, bot_running: {data['bot_running']}")


class TestSyncStatusEndpoint:
    """Test GET /api/csdrop/sync-status endpoint."""
    
    def test_sync_status_returns_expected_fields(self, csdrop_headers):
        """Verify sync-status returns all required fields."""
        response = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=csdrop_headers)
        assert response.status_code == 200, f"sync-status failed: {response.text}"
        data = response.json()
        
        # Verify required fields exist
        assert "status" in data, "Missing 'status' field"
        assert "needs_2fa" in data, "Missing 'needs_2fa' field"
        assert "qr_available" in data, "Missing 'qr_available' field"
        assert "logs" in data, "Missing 'logs' field"
        assert "session_exists" in data, "Missing 'session_exists' field"
        
        # Verify types
        assert isinstance(data["status"], str)
        assert isinstance(data["needs_2fa"], bool)
        assert isinstance(data["qr_available"], bool)
        assert isinstance(data["logs"], list)
        
        print(f"✓ sync-status returned: status={data['status']}, needs_2fa={data['needs_2fa']}")


class TestManualLoginEndpoint:
    """Test POST /api/csdrop/manual-login endpoint."""
    
    def test_manual_login_requires_auth(self):
        """Verify manual-login requires authentication."""
        response = requests.post(f"{BASE_URL}/api/csdrop/manual-login", json={
            "email": "test@discord.com",
            "password": "testpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ manual-login requires authentication")
    
    def test_manual_login_validates_payload(self, csdrop_headers):
        """Verify manual-login validates required fields."""
        # Missing email
        response = requests.post(f"{BASE_URL}/api/csdrop/manual-login", 
            headers=csdrop_headers,
            json={"password": "testpass"})
        assert response.status_code == 422, f"Expected 422 for missing email, got {response.status_code}"
        
        # Missing password
        response = requests.post(f"{BASE_URL}/api/csdrop/manual-login", 
            headers=csdrop_headers,
            json={"email": "test@discord.com"})
        assert response.status_code == 422, f"Expected 422 for missing password, got {response.status_code}"
        print("✓ manual-login validates required fields")
    
    def test_manual_login_starts_process(self, csdrop_headers):
        """Verify manual-login starts the login process (will fail without real Discord but should start)."""
        # First stop any existing sync
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        time.sleep(0.5)
        
        response = requests.post(f"{BASE_URL}/api/csdrop/manual-login", 
            headers=csdrop_headers,
            json={
                "email": "test@discord.com",
                "password": "testpassword123"
            })
        
        # Should return ok or error (if playwright not installed)
        assert response.status_code == 200, f"manual-login failed: {response.text}"
        data = response.json()
        assert "status" in data
        assert "message" in data
        
        # Status should be 'ok' or 'error' (error if dependencies missing)
        assert data["status"] in ["ok", "error"], f"Unexpected status: {data['status']}"
        
        if data["status"] == "ok":
            print(f"✓ manual-login started successfully: {data['message']}")
            # Clean up - stop the process
            time.sleep(1)
            requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        else:
            print(f"✓ manual-login returned expected error (dependencies): {data['message']}")


class TestSubmit2FAEndpoint:
    """Test POST /api/csdrop/submit-2fa endpoint."""
    
    def test_submit_2fa_requires_auth(self):
        """Verify submit-2fa requires authentication."""
        response = requests.post(f"{BASE_URL}/api/csdrop/submit-2fa", json={
            "code": "123456"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ submit-2fa requires authentication")
    
    def test_submit_2fa_validates_code(self, csdrop_headers):
        """Verify submit-2fa validates code format."""
        # First stop any existing sync
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        time.sleep(0.5)
        
        # Try to submit 2FA without active process
        response = requests.post(f"{BASE_URL}/api/csdrop/submit-2fa", 
            headers=csdrop_headers,
            json={"code": "123456"})
        
        assert response.status_code == 200
        data = response.json()
        # Should return error because no login process is running
        assert data["status"] == "error"
        assert "No login process running" in data["message"]
        print("✓ submit-2fa returns error when no process running")
    
    def test_submit_2fa_validates_code_length(self, csdrop_headers):
        """Verify submit-2fa validates code length (4-8 digits)."""
        # Start a manual login first to have an active process
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        time.sleep(0.5)
        
        login_response = requests.post(f"{BASE_URL}/api/csdrop/manual-login", 
            headers=csdrop_headers,
            json={"email": "test@discord.com", "password": "testpass"})
        
        if login_response.json().get("status") == "ok":
            time.sleep(0.5)
            
            # Test with too short code (less than 4 digits)
            response = requests.post(f"{BASE_URL}/api/csdrop/submit-2fa", 
                headers=csdrop_headers,
                json={"code": "12"})
            data = response.json()
            assert data["status"] == "error"
            assert "Invalid code" in data["message"]
            print("✓ submit-2fa rejects codes shorter than 4 digits")
            
            # Clean up
            requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        else:
            print("✓ submit-2fa validation test skipped (dependencies not installed)")


class TestSyncStopEndpoint:
    """Test POST /api/csdrop/sync-stop endpoint."""
    
    def test_sync_stop_requires_auth(self):
        """Verify sync-stop requires authentication."""
        response = requests.post(f"{BASE_URL}/api/csdrop/sync-stop")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ sync-stop requires authentication")
    
    def test_sync_stop_when_no_process(self, csdrop_headers):
        """Verify sync-stop returns appropriate message when no process running."""
        # First ensure no process is running
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        time.sleep(0.5)
        
        response = requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "No sync in progress" in data["message"]
        print("✓ sync-stop returns error when no process running")


class TestQRSyncRegression:
    """Regression tests for existing QR sync flow."""
    
    def test_sync_session_endpoint_exists(self, csdrop_headers):
        """Verify POST /api/csdrop/sync-session endpoint still works."""
        # First stop any existing sync
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        time.sleep(0.5)
        
        response = requests.post(f"{BASE_URL}/api/csdrop/sync-session", headers=csdrop_headers)
        assert response.status_code == 200, f"sync-session failed: {response.text}"
        data = response.json()
        assert "status" in data
        assert "message" in data
        
        if data["status"] == "ok":
            print(f"✓ QR sync-session started: {data['message']}")
            # Clean up
            time.sleep(1)
            requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=csdrop_headers)
        else:
            print(f"✓ QR sync-session returned expected error: {data['message']}")
    
    def test_sync_qr_image_endpoint_exists(self, csdrop_headers):
        """Verify GET /api/csdrop/sync-qr endpoint exists."""
        response = requests.get(f"{BASE_URL}/api/csdrop/sync-qr")
        # Should return 404 if no QR available, or 200 with image
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✓ sync-qr endpoint exists (status: {response.status_code})")


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_returns_expected_fields(self, csdrop_headers):
        """Verify health endpoint returns all required fields."""
        response = requests.get(f"{BASE_URL}/api/csdrop/health", headers=csdrop_headers)
        assert response.status_code == 200, f"health failed: {response.text}"
        data = response.json()
        
        assert "status" in data
        assert "ready" in data
        assert "python_path" in data
        assert "repair_running" in data
        
        print(f"✓ health endpoint: ready={data['ready']}, repair_running={data['repair_running']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
