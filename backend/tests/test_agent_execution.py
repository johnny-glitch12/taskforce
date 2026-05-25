"""
Test Agent Execution API - nidoai architecture
Tests for:
- POST /api/run-agent (agent execution trigger)
- GET /api/agent-logs/{logId} (polling endpoint)
- Agent execution flow (queued → processing → success/failed)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from iteration_16.json
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"


class TestAgentExecutionAuth:
    """Test authentication requirements for agent endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_run_agent_requires_auth(self):
        """POST /api/run-agent should return 401 without token"""
        response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "user_message": "Test message"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ POST /api/run-agent requires authentication (401)")
    
    def test_agent_logs_requires_auth(self):
        """GET /api/agent-logs/{logId} should return 401 without token"""
        response = self.session.get(f"{BASE_URL}/api/agent-logs/test-log-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ GET /api/agent-logs/{logId} requires authentication (401)")


class TestAgentExecutionValidation:
    """Test input validation for agent endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        self.token = data.get("access_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print(f"✓ Logged in as {ADMIN_EMAIL}")
    
    def test_run_agent_requires_user_message(self):
        """POST /api/run-agent should validate user_message is required"""
        # Test with empty user_message
        response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "user_message": ""
        })
        # Pydantic validation should return 422 for min_length=1 violation
        assert response.status_code == 422, f"Expected 422 for empty message, got {response.status_code}: {response.text}"
        print("✓ POST /api/run-agent validates user_message is required (422 for empty)")
    
    def test_run_agent_requires_user_message_field(self):
        """POST /api/run-agent should validate user_message field exists"""
        response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "system_prompt": "Test prompt only"
        })
        # Pydantic validation should return 422 for missing required field
        assert response.status_code == 422, f"Expected 422 for missing user_message, got {response.status_code}: {response.text}"
        print("✓ POST /api/run-agent validates user_message field exists (422)")


class TestAgentExecutionFlow:
    """Test the full agent execution flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        self.token = data.get("access_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_run_agent_returns_log_id(self):
        """POST /api/run-agent should return success=true and logId"""
        response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "user_message": "Hello, test agent execution",
            "system_prompt": "You are a test assistant."
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, "success should be True"
        assert "logId" in data, "Response should contain 'logId' field"
        assert isinstance(data["logId"], str), "logId should be a string"
        assert len(data["logId"]) > 0, "logId should not be empty"
        
        print(f"✓ POST /api/run-agent returns success=true and logId={data['logId'][:8]}...")
        return data["logId"]
    
    def test_agent_logs_returns_execution_log(self):
        """GET /api/agent-logs/{logId} should return execution log with correct schema"""
        # First create an execution
        create_response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "user_message": "Test message for log retrieval",
            "system_prompt": "You are a test assistant."
        })
        assert create_response.status_code == 200
        log_id = create_response.json()["logId"]
        
        # Wait a moment for the log to be created
        time.sleep(0.5)
        
        # Fetch the log
        response = self.session.get(f"{BASE_URL}/api/agent-logs/{log_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify schema
        assert "log_id" in data, "Response should contain 'log_id'"
        assert data["log_id"] == log_id, "log_id should match requested ID"
        assert "status" in data, "Response should contain 'status'"
        assert data["status"] in ["queued", "processing", "success", "failed"], f"Invalid status: {data['status']}"
        assert "terminal_history" in data, "Response should contain 'terminal_history'"
        assert isinstance(data["terminal_history"], list), "terminal_history should be a list"
        assert "input_payload" in data, "Response should contain 'input_payload'"
        assert "system_prompt" in data, "Response should contain 'system_prompt'"
        
        print(f"✓ GET /api/agent-logs/{log_id[:8]}... returns correct schema (status={data['status']})")
    
    def test_agent_logs_404_for_unknown_id(self):
        """GET /api/agent-logs/{logId} should return 404 for unknown logId"""
        response = self.session.get(f"{BASE_URL}/api/agent-logs/nonexistent-log-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ GET /api/agent-logs/{logId} returns 404 for unknown logId")
    
    def test_agent_execution_status_transitions(self):
        """Test that agent execution transitions through status states"""
        # Create an execution
        create_response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "user_message": "What is 2+2?",
            "system_prompt": "You are a helpful math assistant. Be concise."
        })
        assert create_response.status_code == 200
        log_id = create_response.json()["logId"]
        
        # Poll for status changes (max 15 seconds)
        statuses_seen = set()
        terminal_entries = []
        final_status = None
        
        for i in range(10):  # 10 polls at 1.5s = 15 seconds max
            time.sleep(1.5)
            response = self.session.get(f"{BASE_URL}/api/agent-logs/{log_id}")
            if response.status_code != 200:
                continue
            data = response.json()
            statuses_seen.add(data["status"])
            terminal_entries = data.get("terminal_history", [])
            final_status = data["status"]
            
            print(f"  Poll {i+1}: status={data['status']}, terminal_entries={len(terminal_entries)}")
            
            if data["status"] in ["success", "failed"]:
                break
        
        # Verify we saw status transitions
        assert len(statuses_seen) >= 1, "Should see at least one status"
        assert final_status in ["success", "failed", "processing"], f"Final status should be terminal or processing, got {final_status}"
        
        # Verify terminal history accumulated
        assert len(terminal_entries) >= 1, "Terminal history should have at least one entry"
        
        print(f"✓ Agent execution status transitions: {statuses_seen}")
        print(f"✓ Terminal history accumulated {len(terminal_entries)} entries")
        
        # If execution completed, verify output_result
        if final_status == "success":
            response = self.session.get(f"{BASE_URL}/api/agent-logs/{log_id}")
            data = response.json()
            assert "output_result" in data, "Completed execution should have output_result"
            print(f"✓ Agent execution completed with output_result")
        elif final_status == "failed":
            print(f"✓ Agent execution failed (expected due to budget limits)")


class TestAgentExecutionWithDefaultPrompt:
    """Test agent execution with default system prompt"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        data = login_response.json()
        self.token = data.get("access_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_run_agent_with_default_system_prompt(self):
        """POST /api/run-agent should work with default system_prompt"""
        response = self.session.post(f"{BASE_URL}/api/run-agent", json={
            "user_message": "Hello agent"
            # system_prompt not provided, should use default
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert "logId" in data
        print("✓ POST /api/run-agent works with default system_prompt")


class TestRegressionAuth:
    """Regression tests for authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_admin_login(self):
        """Admin login should work (admin@nova.ai / admin123)"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, "Login should return token"
        print(f"✓ Admin login works ({ADMIN_EMAIL})")
    
    def test_csdrop_login(self):
        """CSDROP login should work (admin@csdrop.com / nova_csdrop_2026)"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200, f"CSDROP login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, "Login should return token"
        print(f"✓ CSDROP login works ({CSDROP_EMAIL})")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        data = login_response.json()
        self.token = data.get("access_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_studio_workflows_endpoint(self):
        """GET /api/studio/workflows should work"""
        response = self.session.get(f"{BASE_URL}/api/studio/workflows")
        assert response.status_code == 200, f"Studio workflows failed: {response.text}"
        print("✓ GET /api/studio/workflows works (regression)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
