#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class NovaAPITester:
    def __init__(self, base_url="https://dark-mode-nova.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('/') else f"{self.base_url}{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "response": response.text[:200] if response.text else "No response"
                })
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.failed_tests.append({
                "test": name,
                "error": str(e)
            })
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health check"""
        return self.run_test("Health Check", "GET", "", 200)

    def test_login_admin(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@nova.ai", "password": "admin123"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.log(f"✅ Admin token obtained: {self.token[:20]}...")
            return True, response
        return False, {}

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        return self.run_test(
            "Login Wrong Password",
            "POST",
            "auth/login",
            401,
            data={"email": "admin@nova.ai", "password": "wrongpassword"}
        )

    def test_register_new_user(self):
        """Test user registration"""
        test_email = f"test_{datetime.now().strftime('%H%M%S')}@nova.ai"
        return self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={"email": test_email, "password": "testpass123", "name": "Test User"}
        )

    def test_get_me_with_token(self):
        """Test /me endpoint with valid token"""
        if not self.token:
            self.log("❌ No token available for /me test")
            return False, {}
        return self.run_test("Get Me (with token)", "GET", "auth/me", 200)

    def test_get_me_without_token(self):
        """Test /me endpoint without token"""
        old_token = self.token
        self.token = None
        success, response = self.run_test("Get Me (no token)", "GET", "auth/me", 401)
        self.token = old_token
        return success, response

    def test_waitlist_signup(self):
        """Test waitlist signup"""
        test_email = f"waitlist_{datetime.now().strftime('%H%M%S')}@nova.ai"
        return self.run_test(
            "Waitlist Signup",
            "POST",
            "waitlist",
            200,
            data={"email": test_email}
        )

    def test_get_agents(self):
        """Test get all agents"""
        return self.run_test("Get All Agents", "GET", "agents", 200)

    def test_get_agents_by_category(self):
        """Test get agents by category"""
        return self.run_test("Get Sales Agents", "GET", "agents?category=sales", 200)

    def test_get_agents_by_search(self):
        """Test get agents by search"""
        return self.run_test("Search Agents (data)", "GET", "agents?search=data", 200)

    def test_get_agent_detail(self):
        """Test get specific agent details"""
        return self.run_test("Get Agent 1 Details", "GET", "agents/1", 200)

    def test_get_agent_reviews(self):
        """Test get agent reviews"""
        return self.run_test("Get Agent 1 Reviews", "GET", "agents/1/reviews", 200)

    def test_get_creators(self):
        """Test get all creators"""
        return self.run_test("Get All Creators", "GET", "creators", 200)

    def test_get_creator_detail(self):
        """Test get specific creator details"""
        return self.run_test("Get Creator cxmaster", "GET", "creators/cxmaster", 200)

    def run_all_tests(self):
        """Run all backend API tests"""
        self.log("🚀 Starting Nova AI Backend API Tests")
        self.log("=" * 50)

        # Health check
        self.test_health_check()

        # Authentication tests
        self.test_login_admin()
        self.test_login_wrong_password()
        self.test_register_new_user()
        self.test_get_me_with_token()
        self.test_get_me_without_token()

        # Waitlist tests
        self.test_waitlist_signup()

        # Agent tests
        success, agents_response = self.test_get_agents()
        if success and agents_response:
            agent_count = len(agents_response)
            self.log(f"📊 Found {agent_count} agents in database")
            if agent_count != 6:
                self.log(f"⚠️  Expected 6 agents, found {agent_count}")

        self.test_get_agents_by_category()
        self.test_get_agents_by_search()
        self.test_get_agent_detail()
        self.test_get_agent_reviews()

        # Creator tests
        success, creators_response = self.test_get_creators()
        if success and creators_response:
            creator_count = len(creators_response)
            self.log(f"📊 Found {creator_count} creators in database")
            if creator_count != 5:
                self.log(f"⚠️  Expected 5 creators, found {creator_count}")

        self.test_get_creator_detail()

        # Print results
        self.log("=" * 50)
        self.log(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            self.log("❌ Failed Tests:")
            for failure in self.failed_tests:
                self.log(f"   - {failure.get('test', 'Unknown')}: {failure}")

        return self.tests_passed == self.tests_run

def main():
    tester = NovaAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())