"""
CSDROP Private Client Portal Tests - Iteration 9
Tests for the isolated CSDROP client portal with:
- Authentication and client isolation
- Code execution sandbox
- Sovereign bot launch/stop
- Agent CRUD operations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://agent-memory-hub-5.preview.emergentagent.com')

# Test credentials
CSDROP_EMAIL = "admin@csdrop.com"
CSDROP_PASSWORD = "nova_csdrop_2026"
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASSWORD = "admin123"


class TestCsdropAuthentication:
    """CSDROP login and user data tests"""
    
    def test_csdrop_login_success(self):
        """CSDROP user can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == CSDROP_EMAIL
        print(f"✓ CSDROP login successful")
    
    def test_csdrop_user_has_correct_attributes(self):
        """CSDROP user has client_id=csdrop and tier=pro"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        assert response.status_code == 200
        user = response.json()["user"]
        assert user["client_id"] == "csdrop", f"Expected client_id='csdrop', got '{user.get('client_id')}'"
        assert user["tier"] == "pro", f"Expected tier='pro', got '{user.get('tier')}'"
        assert user["role"] == "client", f"Expected role='client', got '{user.get('role')}'"
        print(f"✓ CSDROP user has correct attributes: client_id=csdrop, tier=pro, role=client")
    
    def test_csdrop_login_wrong_password(self):
        """CSDROP login fails with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print(f"✓ CSDROP login correctly rejects wrong password")


class TestClientIsolation:
    """Tests for client isolation - admin and regular users cannot access CSDROP endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Admin login failed")
    
    @pytest.fixture
    def csdrop_token(self):
        """Get CSDROP token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("CSDROP login failed")
    
    def test_admin_cannot_access_csdrop_dashboard(self, admin_token):
        """Admin user CANNOT access /api/csdrop/dashboard (403)"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Admin correctly blocked from CSDROP dashboard (403)")
    
    def test_admin_cannot_access_csdrop_execute(self, admin_token):
        """Admin user CANNOT access /api/csdrop/execute (403)"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": "print('test')", "input_data": {}}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Admin correctly blocked from CSDROP execute (403)")
    
    def test_admin_cannot_access_csdrop_agents(self, admin_token):
        """Admin user CANNOT access /api/csdrop/agents (403)"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/agents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Admin correctly blocked from CSDROP agents (403)")
    
    def test_unauthenticated_cannot_access_csdrop(self):
        """Unauthenticated requests CANNOT access CSDROP endpoints (401)"""
        response = requests.get(f"{BASE_URL}/api/csdrop/dashboard")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Unauthenticated correctly blocked from CSDROP (401)")
    
    def test_csdrop_user_can_access_dashboard(self, csdrop_token):
        """CSDROP user CAN access /api/csdrop/dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/dashboard",
            headers={"Authorization": f"Bearer {csdrop_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["client"] == "csdrop"
        print(f"✓ CSDROP user can access dashboard")


class TestCsdropDashboard:
    """Tests for CSDROP dashboard stats"""
    
    @pytest.fixture
    def csdrop_headers(self):
        """Get CSDROP auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pytest.skip("CSDROP login failed")
    
    def test_dashboard_returns_stats(self, csdrop_headers):
        """Dashboard returns agent_count, total_runs, bot_running, bot_log_count"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/dashboard",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields
        assert "agent_count" in data, "Missing agent_count"
        assert "total_runs" in data, "Missing total_runs"
        assert "bot_running" in data, "Missing bot_running"
        assert "bot_log_count" in data, "Missing bot_log_count"
        assert data["client"] == "csdrop"
        
        print(f"✓ Dashboard stats: agents={data['agent_count']}, runs={data['total_runs']}, bot_running={data['bot_running']}")


class TestCodeExecution:
    """Tests for CSDROP code execution sandbox"""
    
    @pytest.fixture
    def csdrop_headers(self):
        """Get CSDROP auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pytest.skip("CSDROP login failed")
    
    def test_execute_simple_code(self, csdrop_headers):
        """POST /api/csdrop/execute runs Python code and returns output/result"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={
                "code": "print('Hello CSDROP')\nRESULT = {'status': 'ok'}",
                "input_data": {}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Hello CSDROP" in data["output"]
        assert data["result"]["status"] == "ok"
        print("✓ Code execution works: output contains 'Hello CSDROP', RESULT={'status': 'ok'}")
    
    def test_execute_with_safe_imports(self, csdrop_headers):
        """Safe imports work (json, math, hashlib, datetime etc)"""
        code = """
import json
import math
import hashlib
import datetime

data = {"pi": math.pi, "hash": hashlib.md5(b"test").hexdigest()}
print(json.dumps(data))
RESULT = data
"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={"code": code, "input_data": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "pi" in str(data["result"])
        print(f"✓ Safe imports (json, math, hashlib, datetime) work correctly")
    
    def test_execute_blocks_dangerous_imports_os(self, csdrop_headers):
        """Dangerous import 'os' is blocked"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={"code": "import os\nprint(os.getcwd())", "input_data": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "os" in data["error"].lower() or "not allowed" in data["error"].lower()
        print(f"✓ Import 'os' correctly blocked")
    
    def test_execute_blocks_dangerous_imports_sys(self, csdrop_headers):
        """Dangerous import 'sys' is blocked"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={"code": "import sys\nprint(sys.version)", "input_data": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        print(f"✓ Import 'sys' correctly blocked")
    
    def test_execute_blocks_dangerous_imports_subprocess(self, csdrop_headers):
        """Dangerous import 'subprocess' is blocked"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={"code": "import subprocess\nsubprocess.run(['ls'])", "input_data": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        print(f"✓ Import 'subprocess' correctly blocked")
    
    def test_execute_receives_input_data(self, csdrop_headers):
        """INPUT dict receives the input_data payload"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={
                "code": "print(f'Got: {INPUT}')\nRESULT = INPUT",
                "input_data": {"key": "value", "number": 42}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["result"]["key"] == "value"
        assert data["result"]["number"] == 42
        print(f"✓ INPUT dict correctly receives input_data payload")
    
    def test_execute_print_captured(self, csdrop_headers):
        """print() output is captured in output field"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={
                "code": "print('Line 1')\nprint('Line 2')\nRESULT = 'done'",
                "input_data": {}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Line 1" in data["output"]
        assert "Line 2" in data["output"]
        print(f"✓ print() output correctly captured")


class TestExecutionHistory:
    """Tests for execution history"""
    
    @pytest.fixture
    def csdrop_headers(self):
        """Get CSDROP auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pytest.skip("CSDROP login failed")
    
    def test_get_executions(self, csdrop_headers):
        """GET /api/csdrop/executions returns past runs"""
        # First execute something
        requests.post(
            f"{BASE_URL}/api/csdrop/execute",
            headers=csdrop_headers,
            json={"code": "RESULT = 'history_test'", "input_data": {}}
        )
        
        # Then get history
        response = requests.get(
            f"{BASE_URL}/api/csdrop/executions",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "id" in data[0]
            assert "success" in data[0]
            assert "created_at" in data[0]
        print(f"✓ Execution history returns {len(data)} records")


class TestBotControls:
    """Tests for Sovereign bot launch/stop controls"""
    
    @pytest.fixture
    def csdrop_headers(self):
        """Get CSDROP auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pytest.skip("CSDROP login failed")
    
    def test_bot_launch_endpoint(self, csdrop_headers):
        """POST /api/csdrop/launch responds correctly"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/launch",
            headers=csdrop_headers,
            json={"promo": "https://csdrop.com/r/TEST", "batch": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Bot may fail to actually run (no playwright) but endpoint should respond
        print(f"✓ Bot launch endpoint responds: status={data['status']}, message={data.get('message', 'N/A')}")
    
    def test_bot_stop_endpoint(self, csdrop_headers):
        """POST /api/csdrop/stop responds correctly"""
        response = requests.post(
            f"{BASE_URL}/api/csdrop/stop",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        print(f"✓ Bot stop endpoint responds: status={data['status']}")
    
    def test_bot_logs_endpoint(self, csdrop_headers):
        """GET /api/csdrop/bot-logs returns running status and logs"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/bot-logs",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "logs" in data
        assert isinstance(data["logs"], list)
        print(f"✓ Bot logs endpoint: running={data['running']}, log_count={len(data['logs'])}")


class TestCsdropAgents:
    """Tests for CSDROP agent CRUD operations"""
    
    @pytest.fixture
    def csdrop_headers(self):
        """Get CSDROP auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CSDROP_EMAIL,
            "password": CSDROP_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pytest.skip("CSDROP login failed")
    
    def test_list_agents(self, csdrop_headers):
        """GET /api/csdrop/agents returns list"""
        response = requests.get(
            f"{BASE_URL}/api/csdrop/agents",
            headers=csdrop_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ CSDROP agents list: {len(data)} agents")
    
    def test_create_and_delete_agent(self, csdrop_headers):
        """POST /api/csdrop/agents creates agent, DELETE removes it"""
        # Create
        create_response = requests.post(
            f"{BASE_URL}/api/csdrop/agents",
            headers=csdrop_headers,
            json={
                "name": "TEST_CSDROP_Agent",
                "description": "Test agent for CSDROP portal",
                "code": "RESULT = INPUT",
                "env_vars": {},
                "trigger_type": "manual"
            }
        )
        assert create_response.status_code == 200
        agent = create_response.json()
        assert agent["name"] == "TEST_CSDROP_Agent"
        agent_id = agent["id"]
        print(f"✓ Created CSDROP agent: {agent_id}")
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/csdrop/agents/{agent_id}",
            headers=csdrop_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Deleted CSDROP agent: {agent_id}")
    
    def test_run_agent(self, csdrop_headers):
        """POST /api/csdrop/agents/{id}/run executes agent in sandbox"""
        # Create agent
        create_response = requests.post(
            f"{BASE_URL}/api/csdrop/agents",
            headers=csdrop_headers,
            json={
                "name": "TEST_Run_Agent",
                "description": "Test run",
                "code": "print('Running!')\nRESULT = {'ran': True, 'input': INPUT}",
                "env_vars": {},
                "trigger_type": "manual"
            }
        )
        assert create_response.status_code == 200
        agent_id = create_response.json()["id"]
        
        # Run agent
        run_response = requests.post(
            f"{BASE_URL}/api/csdrop/agents/{agent_id}/run",
            headers=csdrop_headers,
            json={"input_data": {"test": "data"}}
        )
        assert run_response.status_code == 200
        result = run_response.json()
        assert result["success"] == True
        assert result["result"]["ran"] == True
        print(f"✓ Agent run successful: {result['result']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/csdrop/agents/{agent_id}", headers=csdrop_headers)


class TestMainAppStillWorks:
    """Verify main app functionality is not affected"""
    
    @pytest.fixture
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pytest.skip("Admin login failed")
    
    def test_marketplace_agents_still_work(self):
        """Marketplace agents endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"✓ Marketplace agents: {len(data)} agents available")
    
    def test_admin_dashboard_still_works(self, admin_headers):
        """Admin dashboard stats endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "agent_count" in data
        assert "tier" in data
        print(f"✓ Admin dashboard works: tier={data['tier']}, agents={data['agent_count']}")
    
    def test_api_root_still_works(self):
        """API root endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print(f"✓ API root works: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
