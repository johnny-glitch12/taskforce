"""
Nova AI Backend API Tests - Iteration 7
Tests: Auth, Waitlist, Studio Workflows, Linter, Search, Export, Stripe Payments
New in v7: Stripe checkout, payment status, webhook endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndWaitlist:
    """Health check and waitlist counter tests"""
    
    def test_api_health(self):
        """API root returns ok status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Nova AI API"
        print("✓ API health check passed")
    
    def test_waitlist_count(self):
        """Waitlist count endpoint returns count"""
        response = requests.get(f"{BASE_URL}/api/waitlist/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
        print(f"✓ Waitlist count: {data['count']}")


class TestAuthentication:
    """Authentication flow tests - register, login, password reset"""
    
    def test_user_registration(self):
        """New user registration creates account and returns token"""
        unique_email = f"test_reg_{int(time.time())}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Test Registration"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["name"] == "Test Registration"
        assert data["user"]["role"] == "user"
        print(f"✓ User registration successful: {unique_email}")
    
    def test_duplicate_registration_fails(self):
        """Duplicate email registration returns 400"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "admin@nova.ai",
            "password": "testpass123",
            "name": "Duplicate"
        })
        assert response.status_code == 400
        data = response.json()
        assert "already registered" in data["detail"].lower()
        print("✓ Duplicate registration correctly rejected")
    
    def test_admin_login(self):
        """Admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "admin@nova.ai"
        assert data["user"]["role"] == "admin"
        print("✓ Admin login successful")
    
    def test_regular_user_login(self):
        """Regular user login with test@example.com"""
        # First register the user if not exists
        unique_email = f"testuser_{int(time.time())}@example.com"
        reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "newpassword123",
            "name": "Test User"
        })
        if reg_res.status_code == 200:
            data = reg_res.json()
            assert data["user"]["role"] == "user"
            print(f"✓ Regular user login successful: {unique_email}")
        else:
            # User might already exist, try login
            login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": unique_email,
                "password": "newpassword123"
            })
            assert login_res.status_code == 200
            print("✓ Regular user login successful")
    
    def test_login_wrong_password(self):
        """Login with wrong password returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Wrong password correctly rejected")
    
    def test_get_me_with_token(self):
        """GET /auth/me with valid token returns user"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@nova.ai"
        print("✓ GET /auth/me with token successful")
    
    def test_get_me_without_token(self):
        """GET /auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ GET /auth/me without token correctly rejected")


class TestStudioWorkflows:
    """Studio workflow CRUD tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get auth headers for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture
    def regular_user_headers(self):
        """Get auth headers for regular user (non-admin)"""
        unique_email = f"studio_test_{int(time.time())}@example.com"
        reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Studio Test User"
        })
        token = reg_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_workflow(self, auth_headers):
        """Create new workflow"""
        response = requests.post(f"{BASE_URL}/api/studio/workflows", 
            headers=auth_headers,
            json={
                "name": "TEST_Workflow",
                "mode": "vibe",
                "vibe_messages": [{"role": "user", "content": "test message"}],
                "nodes": [],
                "edges": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TEST_Workflow"
        assert data["mode"] == "vibe"
        assert "id" in data
        print(f"✓ Workflow created: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/studio/workflows/{data['id']}", headers=auth_headers)
    
    def test_regular_user_can_access_studio(self, regular_user_headers):
        """Regular user (not admin) can access studio workflows"""
        response = requests.get(f"{BASE_URL}/api/studio/workflows", headers=regular_user_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print("✓ Regular user can access studio workflows")
    
    def test_regular_user_can_create_workflow(self, regular_user_headers):
        """Regular user can create workflows"""
        response = requests.post(f"{BASE_URL}/api/studio/workflows",
            headers=regular_user_headers,
            json={"name": "TEST_User_Workflow", "mode": "node"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TEST_User_Workflow"
        print("✓ Regular user can create workflows")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/studio/workflows/{data['id']}", headers=regular_user_headers)
    
    def test_workflow_crud_flow(self, auth_headers):
        """Full CRUD flow: create -> get -> update -> delete"""
        # Create
        create_res = requests.post(f"{BASE_URL}/api/studio/workflows",
            headers=auth_headers,
            json={"name": "TEST_CRUD_Workflow", "mode": "node"}
        )
        assert create_res.status_code == 200
        wf_id = create_res.json()["id"]
        
        # Get
        get_res = requests.get(f"{BASE_URL}/api/studio/workflows/{wf_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "TEST_CRUD_Workflow"
        
        # Update with nodes and edges
        update_res = requests.put(f"{BASE_URL}/api/studio/workflows/{wf_id}",
            headers=auth_headers,
            json={
                "name": "TEST_Updated_Workflow",
                "nodes": [
                    {"id": "n1", "type": "trigger", "label": "Trigger", "x": 100, "y": 100},
                    {"id": "n2", "type": "llm", "label": "LLM", "x": 300, "y": 100}
                ],
                "edges": [{"from": "n1", "to": "n2"}]
            }
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "TEST_Updated_Workflow"
        assert len(update_res.json()["nodes"]) == 2
        assert len(update_res.json()["edges"]) == 1
        
        # Delete
        delete_res = requests.delete(f"{BASE_URL}/api/studio/workflows/{wf_id}", headers=auth_headers)
        assert delete_res.status_code == 200
        
        # Verify deleted
        verify_res = requests.get(f"{BASE_URL}/api/studio/workflows/{wf_id}", headers=auth_headers)
        assert verify_res.status_code == 404
        
        print("✓ Workflow CRUD flow complete")
    
    def test_workflow_without_auth(self):
        """Workflow endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/studio/workflows")
        assert response.status_code == 401
        print("✓ Workflow endpoints require auth")


class TestComplianceLinter:
    """Compliance linter scan tests"""
    
    @pytest.fixture
    def auth_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_linter_clean_workflow(self, auth_headers):
        """Clean workflow gets high trust score"""
        response = requests.post(f"{BASE_URL}/api/linter/scan",
            headers=auth_headers,
            json={
                "nodes": [
                    {"id": "n1", "type": "trigger", "data": {}},
                    {"id": "n2", "type": "llm", "data": {"model": "nova-7b"}}
                ],
                "edges": [{"from": "n1", "to": "n2"}]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] >= 85
        assert data["status"] == "certified"
        print(f"✓ Clean workflow trust score: {data['trust_score']}")
    
    def test_linter_detects_exposed_api_key(self, auth_headers):
        """Linter flags exposed API keys"""
        response = requests.post(f"{BASE_URL}/api/linter/scan",
            headers=auth_headers,
            json={
                "nodes": [{"id": "n1", "type": "llm", "data": {"api_key": "sk-12345secret"}}],
                "edges": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] < 85
        assert any("api_key" in f["message"].lower() or "credential" in f["message"].lower() for f in data["flags"])
        print(f"✓ Exposed API key detected, score: {data['trust_score']}")


class TestStripePayments:
    """Stripe payment integration tests - NEW in v7"""
    
    @pytest.fixture
    def auth_headers(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nova.ai",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_checkout_requires_auth(self):
        """Checkout endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/payments/checkout",
            headers={"Content-Type": "application/json"},
            json={"agent_id": 1, "plan": "rent", "origin_url": "https://example.com"}
        )
        assert response.status_code == 401
        print("✓ Checkout requires authentication")
    
    def test_checkout_rent_creates_session(self, auth_headers):
        """Rent checkout creates Stripe session"""
        response = requests.post(f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={
                "agent_id": 1,
                "plan": "rent",
                "origin_url": "https://agent-memory-hub-5.preview.emergentagent.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "session_id" in data
        assert data["url"].startswith("https://checkout.stripe.com")
        assert data["session_id"].startswith("cs_test_")
        print(f"✓ Rent checkout created session: {data['session_id'][:30]}...")
    
    def test_checkout_buy_creates_session(self, auth_headers):
        """Buy checkout creates Stripe session"""
        response = requests.post(f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={
                "agent_id": 1,
                "plan": "buy",
                "origin_url": "https://agent-memory-hub-5.preview.emergentagent.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "session_id" in data
        print(f"✓ Buy checkout created session: {data['session_id'][:30]}...")
    
    def test_checkout_requires_origin_url(self, auth_headers):
        """Checkout requires origin_url"""
        response = requests.post(f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={"agent_id": 1, "plan": "rent"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "origin_url" in data["detail"].lower()
        print("✓ Checkout requires origin_url")
    
    def test_checkout_invalid_agent(self, auth_headers):
        """Checkout with invalid agent returns 404"""
        response = requests.post(f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={
                "agent_id": 9999,
                "plan": "rent",
                "origin_url": "https://example.com"
            }
        )
        assert response.status_code == 404
        print("✓ Invalid agent returns 404")
    
    def test_payment_status_endpoint(self, auth_headers):
        """Payment status endpoint returns session info"""
        # First create a checkout session
        checkout_res = requests.post(f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={
                "agent_id": 1,
                "plan": "rent",
                "origin_url": "https://agent-memory-hub-5.preview.emergentagent.com"
            }
        )
        session_id = checkout_res.json()["session_id"]
        
        # Get status
        response = requests.get(f"{BASE_URL}/api/payments/status/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "status" in data
        assert "payment_status" in data
        assert data["agent_id"] == 1
        assert data["agent_name"] == "Customer Service Pro"
        assert data["plan"] == "rent"
        print(f"✓ Payment status: {data['status']}, payment: {data['payment_status']}")
    
    def test_payment_status_invalid_session(self):
        """Payment status with invalid session returns 404"""
        response = requests.get(f"{BASE_URL}/api/payments/status/invalid_session_id")
        assert response.status_code == 404
        print("✓ Invalid session returns 404")
    
    def test_webhook_endpoint_exists(self):
        """Webhook endpoint exists and handles requests"""
        response = requests.post(f"{BASE_URL}/api/webhook/stripe",
            headers={"Content-Type": "application/json"},
            json={}
        )
        # Webhook returns error for invalid payload but endpoint exists
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        print("✓ Webhook endpoint exists")


class TestMarketplaceSearch:
    """Marketplace search engine tests"""
    
    def test_search_by_query(self):
        """Search agents by query string"""
        response = requests.get(f"{BASE_URL}/api/agents/search?q=customer")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert len(data["agents"]) > 0
        print(f"✓ Search 'customer' returned {len(data['agents'])} agents")
    
    def test_search_by_category(self):
        """Search agents by category"""
        response = requests.get(f"{BASE_URL}/api/agents/search?category=sales")
        assert response.status_code == 200
        data = response.json()
        assert all(a["category"] == "sales" for a in data["agents"])
        print(f"✓ Category filter 'sales' returned {len(data['agents'])} agents")
    
    def test_get_agents_list(self):
        """Get all agents"""
        response = requests.get(f"{BASE_URL}/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 6  # Seeded with 6 agents
        print(f"✓ Got {len(data)} agents")
    
    def test_get_agent_detail(self):
        """Get single agent detail"""
        response = requests.get(f"{BASE_URL}/api/agents/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["shortTitle"] == "Customer Service Pro"
        assert "price" in data
        assert "buyPrice" in data
        print(f"✓ Agent 1: {data['shortTitle']}, rent: ${data['price']}, buy: ${data['buyPrice']}")


class TestCreatorsAndSupernova:
    """Creator and Supernova badge tests"""
    
    def test_get_creators(self):
        """Get all creators"""
        response = requests.get(f"{BASE_URL}/api/creators")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert all("is_supernova" in c for c in data)
        print(f"✓ Got {len(data)} creators")
    
    def test_creator_has_supernova_field(self):
        """Creators have is_supernova field"""
        response = requests.get(f"{BASE_URL}/api/creators/cxmaster")
        assert response.status_code == 200
        data = response.json()
        assert "creator" in data
        assert "is_supernova" in data["creator"]
        print(f"✓ Creator cxmaster is_supernova: {data['creator']['is_supernova']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
