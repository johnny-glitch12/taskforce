"""
Nova AI Backend API Tests - Iteration 8
Tests: Dashboard, Custom Agents, Sandbox Execution, Webhooks, Tier Limits
New in v8: Dashboard stats, agent CRUD, sandbox execution, webhook triggers, tier limits
"""
import pytest
import requests
import os
import time
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ─── Dashboard Stats Tests ───
class TestDashboardStats:
    """Dashboard stats endpoint tests"""
    
    @pytest.fixture
    def admin_headers(self):
        """Get auth headers for admin user"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture
    def test_user_headers(self):
        """Get auth headers for test user"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@example.com",
            "password": "newpassword123"
        })
        if login_res.status_code != 200:
            # Register if not exists
            reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": "test@example.com",
                "password": "newpassword123",
                "name": "Test User"
            })
            token = reg_res.json()["token"]
        else:
            token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_dashboard_stats_requires_auth(self):
        """Dashboard stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 401
        print("✓ Dashboard stats requires auth")
    
    def test_dashboard_stats_returns_data(self, admin_headers):
        """Dashboard stats returns agent_count, agent_limit, tier, total_runs, purchased_agents"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "agent_count" in data
        assert "agent_limit" in data
        assert "tier" in data
        assert "total_runs" in data
        assert "purchased_agents" in data
        assert isinstance(data["agent_count"], int)
        assert isinstance(data["agent_limit"], int)
        print(f"✓ Dashboard stats: {data['agent_count']}/{data['agent_limit']} agents, tier={data['tier']}")
    
    def test_free_tier_limit_is_3(self, test_user_headers):
        """Free tier users have agent_limit of 3"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=test_user_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "free"
        assert data["agent_limit"] == 3
        print(f"✓ Free tier limit is 3")


# ─── Agent CRUD Tests ───
class TestAgentCRUD:
    """Custom agent CRUD operations"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_list_agents_empty_or_existing(self, admin_headers):
        """List user agents returns array"""
        response = requests.get(f"{BASE_URL}/api/dashboard/agents", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List agents returned {len(data)} agents")
    
    def test_create_agent_with_valid_code(self, admin_headers):
        """Create agent with valid Python code"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents", 
            headers=admin_headers,
            json={
                "name": "TEST_Echo_Agent",
                "description": "Test echo agent",
                "code": "RESULT = {'echo': INPUT}",
                "env_vars": {"API_KEY": "test123"},
                "trigger_type": "both"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TEST_Echo_Agent"
        assert data["status"] == "ready"
        assert "webhook_key" in data
        assert data["trigger_type"] == "both"
        print(f"✓ Created agent: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{data['id']}", headers=admin_headers)
    
    def test_create_agent_with_blocked_import_os(self, admin_headers):
        """Create agent with blocked import (os) is rejected"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Bad_Agent",
                "description": "Should fail",
                "code": "import os\nRESULT = os.getcwd()",
                "trigger_type": "manual"
            }
        )
        # Should be 400 for validation error (not 403 for limit)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.json()}"
        data = response.json()
        assert "not allowed" in data["detail"].lower() or "blocked" in data["detail"].lower()
        print(f"✓ Blocked import os rejected: {data['detail'][:50]}")
    
    def test_create_agent_with_blocked_import_subprocess(self, admin_headers):
        """Create agent with blocked import (subprocess) is rejected"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Bad_Agent2",
                "code": "import subprocess\nRESULT = subprocess.run(['ls'])",
                "trigger_type": "manual"
            }
        )
        assert response.status_code == 400
        print("✓ Blocked import subprocess rejected")
    
    def test_create_agent_with_blocked_pattern_eval(self, admin_headers):
        """Create agent with blocked pattern (eval) is rejected"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Eval_Agent",
                "code": "RESULT = eval('1+1')",
                "trigger_type": "manual"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "blocked" in data["detail"].lower() or "not allowed" in data["detail"].lower()
        print("✓ Blocked pattern eval rejected")
    
    def test_create_agent_with_blocked_pattern_exec(self, admin_headers):
        """Create agent with blocked pattern (exec) is rejected"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Exec_Agent",
                "code": "exec('print(1)')\nRESULT = 1",
                "trigger_type": "manual"
            }
        )
        assert response.status_code == 400
        print("✓ Blocked pattern exec rejected")
    
    def test_create_agent_with_blocked_pattern_open(self, admin_headers):
        """Create agent with blocked pattern (open) is rejected"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Open_Agent",
                "code": "f = open('/etc/passwd')\nRESULT = f.read()",
                "trigger_type": "manual"
            }
        )
        assert response.status_code == 400
        print("✓ Blocked pattern open rejected")
    
    def test_delete_agent(self, admin_headers):
        """Delete agent removes it from list"""
        # Create
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Delete_Me", "code": "RESULT = 1", "trigger_type": "manual"}
        )
        agent_id = create_res.json()["id"]
        
        # Delete
        delete_res = requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
        assert delete_res.status_code == 200
        
        # Verify deleted
        get_res = requests.get(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
        assert get_res.status_code == 404
        print("✓ Agent deleted successfully")


# ─── Agent Execution Tests ───
class TestAgentExecution:
    """Agent run/execution tests"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture
    def test_agent(self, admin_headers):
        """Create a test agent for execution tests"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Run_Agent",
                "description": "Agent for run tests",
                "code": """
import json
data = INPUT
print(f"Received: {json.dumps(data)}")
RESULT = {"echo": data, "status": "ok"}
""",
                "env_vars": {"TEST_VAR": "test_value"},
                "trigger_type": "both"
            }
        )
        agent = response.json()
        yield agent
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent['id']}", headers=admin_headers)
    
    def test_run_agent_success(self, admin_headers, test_agent):
        """Run agent with valid input returns success"""
        response = requests.post(
            f"{BASE_URL}/api/dashboard/agents/{test_agent['id']}/run",
            headers=admin_headers,
            json={"input_data": {"message": "hello"}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["result"]["echo"]["message"] == "hello"
        assert data["result"]["status"] == "ok"
        assert "output" in data
        assert "Received:" in data["output"]
        assert data["duration_ms"] >= 0
        print(f"✓ Agent run success: {data['duration_ms']}ms")
    
    def test_run_agent_with_safe_imports(self, admin_headers):
        """Agent can use safe imports (json, math, re, datetime, etc.)"""
        # Create agent with safe imports
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Safe_Imports",
                "code": """
import json
import math
import re
import datetime
import collections
import random
import hashlib
import base64

result = {
    "json_works": json.dumps({"a": 1}),
    "math_works": math.sqrt(16),
    "re_works": bool(re.match(r"\\d+", "123")),
    "datetime_works": str(datetime.datetime.now().year),
    "collections_works": str(type(collections.Counter())),
    "random_works": random.randint(1, 10) > 0,
    "hashlib_works": len(hashlib.md5(b"test").hexdigest()) == 32,
    "base64_works": base64.b64encode(b"test").decode() == "dGVzdA=="
}
RESULT = result
""",
                "trigger_type": "manual"
            }
        )
        assert create_res.status_code == 200
        agent_id = create_res.json()["id"]
        
        # Run
        run_res = requests.post(
            f"{BASE_URL}/api/dashboard/agents/{agent_id}/run",
            headers=admin_headers,
            json={"input_data": {}}
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["success"] == True
        assert data["result"]["math_works"] == 4.0
        assert data["result"]["re_works"] == True
        assert data["result"]["random_works"] == True
        assert data["result"]["hashlib_works"] == True
        assert data["result"]["base64_works"] == True
        print("✓ All safe imports work correctly")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
    
    def test_run_agent_accesses_input_dict(self, admin_headers):
        """Agent receives INPUT dict with input_data"""
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Input_Access",
                "code": "RESULT = {'received': INPUT, 'type': str(type(INPUT))}",
                "trigger_type": "manual"
            }
        )
        agent_id = create_res.json()["id"]
        
        run_res = requests.post(
            f"{BASE_URL}/api/dashboard/agents/{agent_id}/run",
            headers=admin_headers,
            json={"input_data": {"key": "value", "num": 42}}
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["success"] == True
        assert data["result"]["received"]["key"] == "value"
        assert data["result"]["received"]["num"] == 42
        print("✓ INPUT dict accessible in agent code")
        
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
    
    def test_run_agent_accesses_env_dict(self, admin_headers):
        """Agent receives ENV dict with env_vars"""
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Env_Access",
                "code": "RESULT = {'env': ENV}",
                "env_vars": {"MY_SECRET": "secret123", "API_URL": "https://api.test.com"},
                "trigger_type": "manual"
            }
        )
        agent_id = create_res.json()["id"]
        
        run_res = requests.post(
            f"{BASE_URL}/api/dashboard/agents/{agent_id}/run",
            headers=admin_headers,
            json={"input_data": {}}
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["success"] == True
        assert data["result"]["env"]["MY_SECRET"] == "secret123"
        assert data["result"]["env"]["API_URL"] == "https://api.test.com"
        print("✓ ENV dict accessible in agent code")
        
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
    
    def test_run_agent_print_captured(self, admin_headers):
        """Agent print() output is captured in output field"""
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Print_Capture",
                "code": """
print("Line 1")
print("Line 2")
print("Hello", "World", sep="-")
RESULT = "done"
""",
                "trigger_type": "manual"
            }
        )
        agent_id = create_res.json()["id"]
        
        run_res = requests.post(
            f"{BASE_URL}/api/dashboard/agents/{agent_id}/run",
            headers=admin_headers,
            json={"input_data": {}}
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["success"] == True
        assert "Line 1" in data["output"]
        assert "Line 2" in data["output"]
        assert "Hello-World" in data["output"]
        print("✓ print() output captured correctly")
        
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
    
    def test_run_disabled_agent_fails(self, admin_headers, test_agent):
        """Running a disabled agent returns 400"""
        # Disable the agent
        requests.post(f"{BASE_URL}/api/dashboard/agents/{test_agent['id']}/stop", headers=admin_headers)
        
        # Try to run
        run_res = requests.post(
            f"{BASE_URL}/api/dashboard/agents/{test_agent['id']}/run",
            headers=admin_headers,
            json={"input_data": {}}
        )
        assert run_res.status_code == 400
        assert "disabled" in run_res.json()["detail"].lower()
        print("✓ Disabled agent cannot be run")
        
        # Re-enable for cleanup
        requests.post(f"{BASE_URL}/api/dashboard/agents/{test_agent['id']}/start", headers=admin_headers)


# ─── Agent Toggle Tests ───
class TestAgentToggle:
    """Agent enable/disable (start/stop) tests"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_stop_agent_changes_status_to_disabled(self, admin_headers):
        """POST /stop changes agent status to disabled"""
        # Create agent
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Toggle", "code": "RESULT = 1", "trigger_type": "manual"}
        )
        agent_id = create_res.json()["id"]
        assert create_res.json()["status"] == "ready"
        
        # Stop
        stop_res = requests.post(f"{BASE_URL}/api/dashboard/agents/{agent_id}/stop", headers=admin_headers)
        assert stop_res.status_code == 200
        
        # Verify status
        get_res = requests.get(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
        assert get_res.json()["status"] == "disabled"
        print("✓ Agent stopped, status=disabled")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
    
    def test_start_agent_changes_status_to_ready(self, admin_headers):
        """POST /start changes agent status to ready"""
        # Create and stop agent
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Toggle2", "code": "RESULT = 1", "trigger_type": "manual"}
        )
        agent_id = create_res.json()["id"]
        requests.post(f"{BASE_URL}/api/dashboard/agents/{agent_id}/stop", headers=admin_headers)
        
        # Start
        start_res = requests.post(f"{BASE_URL}/api/dashboard/agents/{agent_id}/start", headers=admin_headers)
        assert start_res.status_code == 200
        
        # Verify status
        get_res = requests.get(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)
        assert get_res.json()["status"] == "ready"
        print("✓ Agent started, status=ready")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)


# ─── Webhook Trigger Tests ───
class TestWebhookTrigger:
    """Webhook trigger endpoint tests"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture
    def webhook_agent(self, admin_headers):
        """Create agent with webhook trigger"""
        response = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Webhook_Agent",
                "code": "RESULT = {'webhook_received': INPUT}",
                "trigger_type": "webhook"
            }
        )
        agent = response.json()
        yield agent
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent['id']}", headers=admin_headers)
    
    def test_webhook_trigger_executes_agent(self, webhook_agent):
        """POST /webhook/agent/{key} executes the agent"""
        webhook_key = webhook_agent["webhook_key"]
        response = requests.post(
            f"{BASE_URL}/api/webhook/agent/{webhook_key}",
            headers={"Content-Type": "application/json"},
            json={"data": "from_webhook"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["result"]["webhook_received"]["data"] == "from_webhook"
        print(f"✓ Webhook trigger executed: {data['duration_ms']}ms")
    
    def test_webhook_trigger_disabled_agent_fails(self, admin_headers, webhook_agent):
        """Webhook trigger on disabled agent returns 400"""
        # Disable
        requests.post(f"{BASE_URL}/api/dashboard/agents/{webhook_agent['id']}/stop", headers=admin_headers)
        
        # Try webhook
        response = requests.post(
            f"{BASE_URL}/api/webhook/agent/{webhook_agent['webhook_key']}",
            json={"test": 1}
        )
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()
        print("✓ Webhook on disabled agent rejected")
        
        # Re-enable
        requests.post(f"{BASE_URL}/api/dashboard/agents/{webhook_agent['id']}/start", headers=admin_headers)
    
    def test_webhook_trigger_manual_only_agent_fails(self, admin_headers):
        """Webhook trigger on manual-only agent returns 400"""
        # Create manual-only agent
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={
                "name": "TEST_Manual_Only",
                "code": "RESULT = 1",
                "trigger_type": "manual"
            }
        )
        agent = create_res.json()
        
        # Try webhook
        response = requests.post(
            f"{BASE_URL}/api/webhook/agent/{agent['webhook_key']}",
            json={"test": 1}
        )
        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower() or "webhook" in response.json()["detail"].lower()
        print("✓ Webhook on manual-only agent rejected")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent['id']}", headers=admin_headers)
    
    def test_webhook_invalid_key_returns_404(self):
        """Webhook with invalid key returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/webhook/agent/invalid_key_12345",
            json={"test": 1}
        )
        assert response.status_code == 404
        print("✓ Invalid webhook key returns 404")


# ─── Execution History Tests ───
class TestExecutionHistory:
    """Execution history endpoint tests"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_executions_returns_history(self, admin_headers):
        """GET /executions returns recent runs"""
        # Create agent and run it
        create_res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_History", "code": "RESULT = INPUT", "trigger_type": "manual"}
        )
        agent_id = create_res.json()["id"]
        
        # Run twice
        requests.post(f"{BASE_URL}/api/dashboard/agents/{agent_id}/run", headers=admin_headers, json={"input_data": {"run": 1}})
        requests.post(f"{BASE_URL}/api/dashboard/agents/{agent_id}/run", headers=admin_headers, json={"input_data": {"run": 2}})
        
        # Get executions
        exec_res = requests.get(f"{BASE_URL}/api/dashboard/agents/{agent_id}/executions", headers=admin_headers)
        assert exec_res.status_code == 200
        data = exec_res.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        assert "trigger" in data[0]
        assert "success" in data[0]
        assert "duration_ms" in data[0]
        assert "result" in data[0]
        print(f"✓ Execution history returned {len(data)} records")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/dashboard/agents/{agent_id}", headers=admin_headers)


# ─── Tier Limit Tests ───
class TestTierLimits:
    """Agent tier limit tests"""
    
    @pytest.fixture
    def free_user_headers(self):
        """Create a fresh free tier user"""
        unique_email = f"free_tier_{int(time.time())}@test.com"
        reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Free Tier User"
        })
        token = reg_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_free_user_can_create_up_to_3_agents(self, free_user_headers):
        """Free tier user can create up to 3 agents"""
        agent_ids = []
        
        # Create 3 agents
        for i in range(3):
            res = requests.post(f"{BASE_URL}/api/dashboard/agents",
                headers=free_user_headers,
                json={"name": f"TEST_Limit_{i}", "code": "RESULT = 1", "trigger_type": "manual"}
            )
            assert res.status_code == 200, f"Failed to create agent {i+1}: {res.json()}"
            agent_ids.append(res.json()["id"])
        
        print(f"✓ Created 3 agents for free tier user")
        
        # Try to create 4th - should fail
        res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=free_user_headers,
            json={"name": "TEST_Limit_4", "code": "RESULT = 1", "trigger_type": "manual"}
        )
        assert res.status_code == 403
        assert "limit" in res.json()["detail"].lower() or "upgrade" in res.json()["detail"].lower()
        print(f"✓ 4th agent rejected with 403: {res.json()['detail'][:50]}")
        
        # Cleanup
        for aid in agent_ids:
            requests.delete(f"{BASE_URL}/api/dashboard/agents/{aid}", headers=free_user_headers)


# ─── Purchased Agents Tests ───
class TestPurchasedAgents:
    """Purchased agents endpoint tests"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_purchased_endpoint_returns_list(self, admin_headers):
        """GET /dashboard/purchased returns list of transactions"""
        response = requests.get(f"{BASE_URL}/api/dashboard/purchased", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Purchased endpoint returned {len(data)} transactions")


# ─── Sandbox Security Tests ───
class TestSandboxSecurity:
    """Sandbox security validation tests"""
    
    @pytest.fixture
    def admin_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_blocked_import_sys(self, admin_headers):
        """Import sys is blocked"""
        res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Sys", "code": "import sys\nRESULT = sys.version", "trigger_type": "manual"}
        )
        assert res.status_code == 400
        print("✓ import sys blocked")
    
    def test_blocked_import_socket(self, admin_headers):
        """Import socket is blocked"""
        res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Socket", "code": "import socket\nRESULT = 1", "trigger_type": "manual"}
        )
        assert res.status_code == 400
        print("✓ import socket blocked")
    
    def test_blocked_pattern_getattr(self, admin_headers):
        """getattr() is blocked"""
        res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Getattr", "code": "RESULT = getattr(str, '__class__')", "trigger_type": "manual"}
        )
        assert res.status_code == 400
        print("✓ getattr() blocked")
    
    def test_blocked_pattern_dunder_import(self, admin_headers):
        """__import__ is blocked"""
        res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_DunderImport", "code": "RESULT = __import__('os')", "trigger_type": "manual"}
        )
        assert res.status_code == 400
        print("✓ __import__ blocked")
    
    def test_blocked_pattern_dunder_builtins(self, admin_headers):
        """__builtins__ access is blocked"""
        res = requests.post(f"{BASE_URL}/api/dashboard/agents",
            headers=admin_headers,
            json={"name": "TEST_Builtins", "code": "RESULT = __builtins__", "trigger_type": "manual"}
        )
        assert res.status_code == 400
        print("✓ __builtins__ blocked")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
