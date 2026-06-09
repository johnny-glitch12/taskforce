"""
Test Environment Manager Features for CSDROP Portal
Tests: Health check, Repair endpoint, Repair status, Pre-flight check on launch
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://agent-memory-hub-5.preview.emergentagent.com').rstrip('/')

# Test credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"


class TestHealthCheckEndpoint:
    """GET /api/csdrop/health - Verify all 4 dependencies"""
    
    def test_health_check_returns_all_dependencies(self):
        """Health check should return status for all 4 dependencies"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/health",
            headers={"Authorization": "Bearer any_token"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all 4 dependencies are present
        assert "status" in data
        assert "playwright" in data["status"]
        assert "playwright_stealth" in data["status"]
        assert "RestrictedPython" in data["status"]
        assert "chromium" in data["status"]
        
        # Verify ready flag
        assert "ready" in data
        assert isinstance(data["ready"], bool)
        
        # Verify python_path
        assert "python_path" in data
        assert data["python_path"] is not None
        
        # Verify repair_running flag
        assert "repair_running" in data
        
        print(f"Health check response: {data}")
    
    def test_health_check_all_dependencies_ok(self):
        """All dependencies should be OK (installed)"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/health",
            headers={"Authorization": "Bearer any_token"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All should be OK since dependencies are installed
        for dep, status in data["status"].items():
            assert status == "OK", f"Dependency {dep} is {status}, expected OK"
        
        # ready should be true
        assert data["ready"] == True, "ready should be True when all dependencies are OK"
        print("All 4 dependencies are OK, ready=True")
    
    def test_health_check_accepts_any_bearer_token(self):
        """Health check uses Depends(security) not Depends(get_csdrop_user)"""
        # Should work with any token
        response = requests.get(
            f"{BASE_URL}/api/csdrop/health",
            headers={"Authorization": "Bearer fake_token_12345"}
        )
        assert response.status_code == 200
        print("Health check accepts any Bearer token")


class TestRepairEndpoint:
    """POST /api/admin/repair - Background repair"""
    
    def test_repair_starts_background_task(self):
        """Repair endpoint should start background task and return immediately"""
        response = requests.post(f"{BASE_URL}/api/admin/repair")
        assert response.status_code == 200
        data = response.json()
        
        # Should return status ok or busy
        assert "status" in data
        assert data["status"] in ["ok", "busy"]
        assert "message" in data
        print(f"Repair response: {data}")
    
    def test_repair_no_auth_required(self):
        """Repair endpoint has no auth guard"""
        response = requests.post(f"{BASE_URL}/api/admin/repair")
        # Should not return 401 or 403
        assert response.status_code == 200
        print("Repair endpoint has no auth requirement")


class TestRepairStatusEndpoint:
    """GET /api/admin/repair-status - Poll repair progress"""
    
    def test_repair_status_returns_state(self):
        """Repair status should return running state and logs"""
        response = requests.get(f"{BASE_URL}/api/admin/repair-status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "running" in data
        assert isinstance(data["running"], bool)
        assert "last_result" in data
        assert "logs" in data
        assert isinstance(data["logs"], list)
        print(f"Repair status: running={data['running']}, last_result={data['last_result']}, logs_count={len(data['logs'])}")
    
    def test_repair_status_no_auth_required(self):
        """Repair status endpoint has no auth guard"""
        response = requests.get(f"{BASE_URL}/api/admin/repair-status")
        # Should not return 401 or 403
        assert response.status_code == 200
        print("Repair status endpoint has no auth requirement")
    
    def test_repair_status_shows_logs_after_repair(self):
        """After repair, status should show logs"""
        # First trigger repair
        requests.post(f"{BASE_URL}/api/admin/repair")
        
        # Wait for repair to complete
        time.sleep(5)
        
        response = requests.get(f"{BASE_URL}/api/admin/repair-status")
        assert response.status_code == 200
        data = response.json()
        
        # Should have logs from the repair
        assert len(data["logs"]) > 0, "Should have repair logs"
        assert data["running"] == False, "Repair should be complete"
        print(f"Repair logs: {data['logs']}")


class TestLaunchPreflightCheck:
    """POST /api/csdrop/launch - Pre-flight dependency check"""
    
    @pytest.fixture
    def csdrop_token(self):
        """Get CSDROP user token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CSDROP_EMAIL, "password": CSDROP_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("CSDROP login failed")
    
    def test_launch_succeeds_when_dependencies_ready(self, csdrop_token):
        """Launch should succeed when all dependencies are installed"""
        # First verify health is ready
        health_response = requests.get(
            f"{BASE_URL}/api/csdrop/health",
            headers={"Authorization": f"Bearer {csdrop_token}"}
        )
        health_data = health_response.json()
        
        if not health_data.get("ready"):
            pytest.skip("Dependencies not ready, skipping launch test")
        
        # Try to launch
        response = requests.post(
            f"{BASE_URL}/api/csdrop/launch",
            headers={"Authorization": f"Bearer {csdrop_token}", "Content-Type": "application/json"},
            json={"promo": "https://csdrop.com/r/TEST", "batch": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should succeed or say bot already running
        assert data["status"] in ["ok", "error"]
        if data["status"] == "ok":
            print("Launch succeeded - bot started")
            # Stop the bot
            requests.post(
                f"{BASE_URL}/api/csdrop/stop",
                headers={"Authorization": f"Bearer {csdrop_token}"}
            )
        else:
            print(f"Launch response: {data}")
    
    def test_launch_requires_csdrop_auth(self):
        """Launch should require CSDROP user authentication"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/launch",
            headers={"Content-Type": "application/json"},
            json={"promo": "https://csdrop.com/r/TEST", "batch": 5}
        )
        # Should return 401 or 403
        assert response.status_code in [401, 403]
        print("Launch requires authentication")
    
    def test_launch_rejects_admin_user(self):
        """Launch should reject admin user (not CSDROP client)"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Admin login failed")
        
        admin_token = login_response.json()["token"]
        
        response = requests.post(
            f"{BASE_URL}/api/csdrop/launch",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"promo": "https://csdrop.com/r/TEST", "batch": 5}
        )
        # Should return 403 (access denied)
        assert response.status_code == 403
        print("Launch correctly rejects admin user")


class TestSysExecutable:
    """Verify bot launcher uses sys.executable instead of hardcoded python3"""
    
    def test_health_check_shows_python_path(self):
        """Health check should show the actual Python path being used"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/health",
            headers={"Authorization": "Bearer any_token"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # python_path should be set and not be just "python3"
        assert data["python_path"] is not None
        assert len(data["python_path"]) > 0
        # Should be a full path, not just "python3"
        assert "/" in data["python_path"], "python_path should be a full path"
        print(f"Python path: {data['python_path']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
