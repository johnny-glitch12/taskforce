"""Shared pytest fixtures for backend tests."""
import os
import sys
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

# Load backend .env (MONGO_URL, DB_NAME)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Public preview URL (frontend .env)
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    assert BASE_URL, "REACT_APP_BACKEND_URL must be set in frontend/.env"
    return BASE_URL


@pytest.fixture(scope="session")
def admin_token(base_url):
    res = requests.post(
        f"{base_url}/api/auth/login",
        json={"email": "admin@nova.ai", "password": "admin123"},
        timeout=15,
    )
    if res.status_code != 200:
        pytest.skip(f"admin login failed: {res.status_code} {res.text}")
    return res.json()["token"]


@pytest.fixture(scope="session")
def freeuser_token(base_url):
    res = requests.post(
        f"{base_url}/api/auth/login",
        json={"email": "freeuser@test.com", "password": "test123"},
        timeout=15,
    )
    if res.status_code != 200:
        pytest.skip(f"freeuser login failed: {res.status_code} {res.text}")
    return res.json()["token"]


@pytest.fixture(scope="session")
def admin_client(base_url, admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}",
                      "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def freeuser_client(base_url, freeuser_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {freeuser_token}",
                      "Content-Type": "application/json"})
    return s
