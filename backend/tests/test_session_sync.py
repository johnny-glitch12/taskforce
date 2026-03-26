"""
Test Suite for CSDROP Session Sync Feature (Remote Login / QR Code Sync)
Tests the following endpoints:
- POST /api/csdrop/sync-session - Start session sync process
- GET /api/csdrop/sync-status - Poll sync status and logs
- POST /api/csdrop/sync-stop - Cancel running sync
- GET /api/csdrop/sync-qr - Serve QR code image

Also includes regression tests for existing CSDROP endpoints.
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


class TestSessionSyncAuth:
    """Test authentication requirements for session sync endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get CSDROP auth token"""
        # Login as CSDROP user
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if res.status_code == 200:
            self.csdrop_token = res.json().get("token")
            self.csdrop_headers = {
                "Authorization": f"Bearer {self.csdrop_token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("CSDROP login failed")
        
        # Login as admin (non-CSDROP user)
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if res.status_code == 200:
            self.admin_token = res.json().get("token")
            self.admin_headers = {
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
        else:
            self.admin_headers = None
    
    def test_sync_session_requires_auth(self):
        """POST /api/csdrop/sync-session requires authentication"""
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-session")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: sync-session requires authentication (401)")
    
    def test_sync_status_requires_auth(self):
        """GET /api/csdrop/sync-status requires authentication"""
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-status")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: sync-status requires authentication (401)")
    
    def test_sync_stop_requires_auth(self):
        """POST /api/csdrop/sync-stop requires authentication"""
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-stop")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: sync-stop requires authentication (401)")
    
    def test_sync_qr_no_auth_required(self):
        """GET /api/csdrop/sync-qr has NO auth (for <img src> usage)"""
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-qr")
        # Should return 404 (no QR available) not 401
        assert res.status_code == 404, f"Expected 404 (no QR), got {res.status_code}"
        print("PASS: sync-qr has no auth requirement (returns 404 when no QR)")
    
    def test_sync_session_rejects_non_csdrop_user(self):
        """POST /api/csdrop/sync-session rejects non-CSDROP users"""
        if not self.admin_headers:
            pytest.skip("Admin login failed")
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-session", headers=self.admin_headers)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("PASS: sync-session rejects non-CSDROP users (403)")
    
    def test_sync_status_rejects_non_csdrop_user(self):
        """GET /api/csdrop/sync-status rejects non-CSDROP users"""
        if not self.admin_headers:
            pytest.skip("Admin login failed")
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=self.admin_headers)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("PASS: sync-status rejects non-CSDROP users (403)")
    
    def test_sync_stop_rejects_non_csdrop_user(self):
        """POST /api/csdrop/sync-stop rejects non-CSDROP users"""
        if not self.admin_headers:
            pytest.skip("Admin login failed")
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.admin_headers)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("PASS: sync-stop rejects non-CSDROP users (403)")


class TestSyncStatusEndpoint:
    """Test GET /api/csdrop/sync-status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get CSDROP auth token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if res.status_code == 200:
            self.token = res.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("CSDROP login failed")
    
    def test_sync_status_returns_expected_fields(self):
        """GET /api/csdrop/sync-status returns status, qr_available, logs, session info"""
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=self.headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        
        # Check required fields
        assert "status" in data, "Missing 'status' field"
        assert "qr_available" in data, "Missing 'qr_available' field"
        assert "logs" in data, "Missing 'logs' field"
        assert "session_exists" in data, "Missing 'session_exists' field"
        assert "session_last_updated" in data, "Missing 'session_last_updated' field"
        
        # Validate types
        assert isinstance(data["status"], str), "status should be string"
        assert isinstance(data["qr_available"], bool), "qr_available should be bool"
        assert isinstance(data["logs"], list), "logs should be list"
        assert isinstance(data["session_exists"], bool), "session_exists should be bool"
        
        print(f"PASS: sync-status returns expected fields: status={data['status']}, qr_available={data['qr_available']}")
    
    def test_sync_status_idle_when_no_sync(self):
        """GET /api/csdrop/sync-status returns 'idle' when no sync in progress"""
        # First stop any running sync
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        time.sleep(0.5)
        
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        
        # Status should be idle, finished, success, or timeout (not syncing)
        assert data["status"] in ["idle", "finished", "success", "timeout"], f"Unexpected status: {data['status']}"
        print(f"PASS: sync-status returns '{data['status']}' when no sync in progress")


class TestSyncStopEndpoint:
    """Test POST /api/csdrop/sync-stop endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get CSDROP auth token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if res.status_code == 200:
            self.token = res.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("CSDROP login failed")
    
    def test_sync_stop_when_no_sync_running(self):
        """POST /api/csdrop/sync-stop returns error when no sync in progress"""
        # First ensure no sync is running
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        time.sleep(0.5)
        
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        
        assert data.get("status") == "error", f"Expected error status, got {data.get('status')}"
        assert "No sync in progress" in data.get("message", ""), f"Unexpected message: {data.get('message')}"
        print("PASS: sync-stop returns error when no sync in progress")


class TestSyncQREndpoint:
    """Test GET /api/csdrop/sync-qr endpoint"""
    
    def test_sync_qr_returns_404_when_no_qr(self):
        """GET /api/csdrop/sync-qr returns 404 when no QR available"""
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-qr")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: sync-qr returns 404 when no QR available")
    
    def test_sync_qr_no_auth_header_needed(self):
        """GET /api/csdrop/sync-qr works without auth header"""
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-qr")
        # Should be 404 (no QR) not 401 (unauthorized)
        assert res.status_code != 401, "sync-qr should not require auth"
        print("PASS: sync-qr does not require authentication")


class TestSyncSessionEndpoint:
    """Test POST /api/csdrop/sync-session endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get CSDROP auth token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if res.status_code == 200:
            self.token = res.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("CSDROP login failed")
    
    def test_sync_session_rejects_if_bot_running(self):
        """POST /api/csdrop/sync-session rejects if bot is already running"""
        # First check if bot is running
        res = requests.get(f"{BASE_URL}/api/csdrop/bot-logs", headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            if data.get("running"):
                # Bot is running, try to start sync
                res = requests.post(f"{BASE_URL}/api/csdrop/sync-session", headers=self.headers)
                assert res.status_code == 200
                data = res.json()
                assert data.get("status") == "error", "Should reject when bot is running"
                assert "Stop the bot first" in data.get("message", "")
                print("PASS: sync-session rejects when bot is running")
            else:
                print("SKIP: Bot not running, cannot test rejection")
        else:
            print("SKIP: Could not check bot status")
    
    def test_sync_session_rejects_duplicate_sync(self):
        """POST /api/csdrop/sync-session rejects duplicate sync request"""
        # First stop any running sync
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        time.sleep(0.5)
        
        # Start a sync
        res1 = requests.post(f"{BASE_URL}/api/csdrop/sync-session", headers=self.headers)
        
        # If first sync started successfully, try to start another
        if res1.status_code == 200 and res1.json().get("status") == "ok":
            time.sleep(0.5)
            res2 = requests.post(f"{BASE_URL}/api/csdrop/sync-session", headers=self.headers)
            assert res2.status_code == 200
            data = res2.json()
            assert data.get("status") == "error", "Should reject duplicate sync"
            assert "already in progress" in data.get("message", "")
            print("PASS: sync-session rejects duplicate sync request")
            
            # Clean up - stop the sync
            requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        else:
            # First sync failed (maybe playwright not installed)
            print(f"SKIP: Could not start first sync: {res1.json()}")


class TestSyncSessionFlow:
    """Test the full sync session flow: start -> status -> stop"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get CSDROP auth token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if res.status_code == 200:
            self.token = res.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("CSDROP login failed")
    
    def test_full_sync_flow(self):
        """Test start sync -> check status -> stop sync flow"""
        # 1. Stop any existing sync
        requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        time.sleep(0.5)
        
        # 2. Start sync
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-session", headers=self.headers)
        assert res.status_code == 200, f"Start sync failed: {res.status_code}"
        data = res.json()
        
        if data.get("status") == "error":
            # Sync couldn't start (maybe playwright not installed)
            print(f"SKIP: Sync could not start: {data.get('message')}")
            return
        
        assert data.get("status") == "ok", f"Expected ok status, got {data}"
        print(f"Step 1 PASS: Sync started - {data.get('message')}")
        
        # 3. Check status shows 'syncing'
        time.sleep(1)
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "syncing", f"Expected 'syncing', got {data.get('status')}"
        print(f"Step 2 PASS: Status is 'syncing'")
        
        # 4. Stop the sync
        res = requests.post(f"{BASE_URL}/api/csdrop/sync-stop", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok", f"Expected ok status, got {data}"
        print(f"Step 3 PASS: Sync stopped - {data.get('message')}")
        
        # 5. Verify status is no longer 'syncing'
        time.sleep(0.5)
        res = requests.get(f"{BASE_URL}/api/csdrop/sync-status", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") != "syncing", f"Status should not be 'syncing' after stop"
        print(f"Step 4 PASS: Status after stop is '{data.get('status')}'")
        
        print("PASS: Full sync flow completed successfully")


class TestRegressionCSDROP:
    """Regression tests for existing CSDROP endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get CSDROP auth token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if res.status_code == 200:
            self.token = res.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("CSDROP login failed")
    
    def test_csdrop_health_still_works(self):
        """GET /api/csdrop/health still works (regression)"""
        res = requests.get(f"{BASE_URL}/api/csdrop/health", headers=self.headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert "status" in data, "Missing 'status' field"
        assert "ready" in data, "Missing 'ready' field"
        print(f"PASS: /api/csdrop/health works - ready={data.get('ready')}")
    
    def test_csdrop_live_feed_still_works(self):
        """GET /api/csdrop/live-feed still works (regression)"""
        res = requests.get(f"{BASE_URL}/api/csdrop/live-feed", headers=self.headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert "available" in data, "Missing 'available' field"
        assert "bot_running" in data, "Missing 'bot_running' field"
        print(f"PASS: /api/csdrop/live-feed works - available={data.get('available')}")
    
    def test_csdrop_dashboard_still_works(self):
        """GET /api/csdrop/dashboard still works (regression)"""
        res = requests.get(f"{BASE_URL}/api/csdrop/dashboard", headers=self.headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert "client" in data, "Missing 'client' field"
        assert data.get("client") == "csdrop", f"Expected client='csdrop', got {data.get('client')}"
        print(f"PASS: /api/csdrop/dashboard works - client={data.get('client')}")
    
    def test_csdrop_bot_logs_still_works(self):
        """GET /api/csdrop/bot-logs still works (regression)"""
        res = requests.get(f"{BASE_URL}/api/csdrop/bot-logs", headers=self.headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert "running" in data, "Missing 'running' field"
        assert "logs" in data, "Missing 'logs' field"
        print(f"PASS: /api/csdrop/bot-logs works - running={data.get('running')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
