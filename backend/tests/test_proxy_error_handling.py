"""
Test suite for 407 Proxy Authentication Required error handling in CSDROP bot.
Tests:
1. POST /api/csdrop/test-proxy - tests proxy and returns status/ip/code/message
2. GET /api/csdrop/bot-signal - reads bot signal file (STRIKE_PAUSED or null)
3. Bot signal file mechanism - write STRIKE_PAUSED:proxy_auth_407 and verify endpoint reads it
4. Bot signal file mechanism - when file absent, returns signal:null
5. Regression tests for dashboard and auth
"""

import pytest
import requests
import os
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
BOT_SIGNAL_FILE = Path("/app/backend/clients/csdrop/bot_signal.txt")

# CSDROP client credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"


class TestCsdropAuth:
    """Test CSDROP authentication - prerequisite for other tests"""
    
    @pytest.fixture(scope="class")
    def csdrop_token(self):
        """Get CSDROP client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200, f"CSDROP login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        assert data["user"]["client_id"] == "csdrop", "User is not CSDROP client"
        return data["token"]
    
    def test_csdrop_login_success(self, csdrop_token):
        """Verify CSDROP client can login"""
        assert csdrop_token is not None
        print(f"✓ CSDROP login successful, token obtained")


class TestProxyEndpoint:
    """Test POST /api/csdrop/test-proxy endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authenticated headers for CSDROP client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_test_proxy_requires_auth(self):
        """POST /api/csdrop/test-proxy requires authentication"""
        response = requests.post(f"{BASE_URL}/api/csdrop/test-proxy")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ test-proxy requires authentication (401)")
    
    def test_test_proxy_returns_expected_fields(self, auth_headers):
        """POST /api/csdrop/test-proxy returns status, code, and message/ip"""
        response = requests.post(f"{BASE_URL}/api/csdrop/test-proxy", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Must have status field
        assert "status" in data, "Response missing 'status' field"
        assert data["status"] in ["ok", "error"], f"Invalid status: {data['status']}"
        
        # If error, must have code and message
        if data["status"] == "error":
            assert "code" in data, "Error response missing 'code' field"
            assert "message" in data, "Error response missing 'message' field"
            print(f"✓ test-proxy returned error: code={data['code']}, message={data['message'][:50]}...")
        else:
            # If ok, must have ip
            assert "ip" in data, "Success response missing 'ip' field"
            print(f"✓ test-proxy returned ok: ip={data['ip']}")
    
    def test_test_proxy_407_response_format(self, auth_headers):
        """Verify 407 error response has correct format (proxy in this env returns 407)"""
        response = requests.post(f"{BASE_URL}/api/csdrop/test-proxy", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # In this environment, proxy returns 407
        if data.get("code") == 407:
            assert data["status"] == "error"
            assert "407" in data["message"] or "Authentication" in data["message"]
            print(f"✓ 407 response format correct: {data['message']}")
        else:
            print(f"✓ Proxy returned code {data.get('code', 'N/A')} (not 407 in this run)")


class TestBotSignalEndpoint:
    """Test GET /api/csdrop/bot-signal endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authenticated headers for CSDROP client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(autouse=True)
    def cleanup_signal_file(self):
        """Clean up signal file before and after each test"""
        # Cleanup before
        if BOT_SIGNAL_FILE.exists():
            BOT_SIGNAL_FILE.unlink()
        yield
        # Cleanup after
        if BOT_SIGNAL_FILE.exists():
            BOT_SIGNAL_FILE.unlink()
    
    def test_bot_signal_requires_auth(self):
        """GET /api/csdrop/bot-signal requires authentication"""
        response = requests.get(f"{BASE_URL}/api/csdrop/bot-signal")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ bot-signal requires authentication (401)")
    
    def test_bot_signal_returns_null_when_no_file(self, auth_headers):
        """GET /api/csdrop/bot-signal returns signal:null when file absent"""
        # Ensure file doesn't exist
        if BOT_SIGNAL_FILE.exists():
            BOT_SIGNAL_FILE.unlink()
        
        response = requests.get(f"{BASE_URL}/api/csdrop/bot-signal", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "signal" in data, "Response missing 'signal' field"
        assert "reason" in data, "Response missing 'reason' field"
        assert data["signal"] is None, f"Expected signal=null, got {data['signal']}"
        assert data["reason"] is None, f"Expected reason=null, got {data['reason']}"
        print("✓ bot-signal returns null when file absent")
    
    def test_bot_signal_reads_strike_paused_proxy_407(self, auth_headers):
        """GET /api/csdrop/bot-signal reads STRIKE_PAUSED:proxy_auth_407 correctly"""
        # Write the signal file
        BOT_SIGNAL_FILE.write_text("STRIKE_PAUSED:proxy_auth_407")
        
        response = requests.get(f"{BASE_URL}/api/csdrop/bot-signal", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["signal"] == "STRIKE_PAUSED", f"Expected signal=STRIKE_PAUSED, got {data['signal']}"
        assert data["reason"] == "proxy_auth_407", f"Expected reason=proxy_auth_407, got {data['reason']}"
        print("✓ bot-signal reads STRIKE_PAUSED:proxy_auth_407 correctly")
    
    def test_bot_signal_reads_other_signals(self, auth_headers):
        """GET /api/csdrop/bot-signal reads other signal formats correctly"""
        # Test with different signal
        BOT_SIGNAL_FILE.write_text("STRIKE_PAUSED:proxy_connection_failed")
        
        response = requests.get(f"{BASE_URL}/api/csdrop/bot-signal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["signal"] == "STRIKE_PAUSED"
        assert data["reason"] == "proxy_connection_failed"
        print("✓ bot-signal reads other signal formats correctly")
    
    def test_bot_signal_handles_signal_without_reason(self, auth_headers):
        """GET /api/csdrop/bot-signal handles signal without colon separator"""
        BOT_SIGNAL_FILE.write_text("SOME_SIGNAL")
        
        response = requests.get(f"{BASE_URL}/api/csdrop/bot-signal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["signal"] == "SOME_SIGNAL"
        assert data["reason"] is None
        print("✓ bot-signal handles signal without reason")


class TestDashboardRegression:
    """Regression tests for dashboard and existing endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authenticated headers for CSDROP client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_csdrop_dashboard_loads(self, auth_headers):
        """GET /api/csdrop/dashboard returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/csdrop/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify expected fields
        assert "client" in data
        assert "user_name" in data
        assert "agent_count" in data
        assert "total_runs" in data
        assert "bot_running" in data
        assert "bot_log_count" in data
        print(f"✓ Dashboard loads: client={data['client']}, bot_running={data['bot_running']}")
    
    def test_csdrop_health_endpoint(self, auth_headers):
        """GET /api/csdrop/health returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/csdrop/health", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "status" in data
        assert "ready" in data
        assert "python_path" in data
        print(f"✓ Health endpoint: ready={data['ready']}")
    
    def test_csdrop_executions_endpoint(self, auth_headers):
        """GET /api/csdrop/executions returns list"""
        response = requests.get(f"{BASE_URL}/api/csdrop/executions", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list response"
        print(f"✓ Executions endpoint: {len(data)} executions")
    
    def test_csdrop_logs_endpoint(self, auth_headers):
        """GET /api/csdrop/logs returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/csdrop/logs", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "running" in data
        assert "logs" in data
        assert isinstance(data["logs"], list)
        print(f"✓ Logs endpoint: running={data['running']}, log_count={len(data['logs'])}")


class TestSyncEndpointsRegression:
    """Regression tests for sync endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authenticated headers for CSDROP client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_sync_status_endpoint(self, auth_headers):
        """GET /api/csdrop/sync-status returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "status" in data
        assert "needs_2fa" in data
        assert "qr_available" in data
        assert "logs" in data
        assert "session_exists" in data
        print(f"✓ Sync status: status={data['status']}, session_exists={data['session_exists']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
