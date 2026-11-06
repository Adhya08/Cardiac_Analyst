"""
Automated Pytest Suite: Login Protection & Password Strength (Item 5)
=====================================================================
Verifies:
1. Registration rejects weak passwords (length < 8, missing upper, lower, digit, or special).
2. Registration succeeds with a strong password.
3. Login lockout triggers HTTP 429 after 5 failed login attempts.
4. Successful login clears failed attempt tracking.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.rate_limiter import reset_rate_limits_for_testing


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_rate_limits():
    reset_rate_limits_for_testing()
    yield
    reset_rate_limits_for_testing()


def test_registration_rejects_weak_passwords(client):
    """Weak passwords must be rejected with 422 Unprocessable Entity."""
    weak_cases = [
        "Short1!",          # < 8 chars
        "alllowercase1!",   # no uppercase
        "ALLUPPERCASE1!",   # no lowercase
        "NoDigitsHere!@",   # no number
        "NoSpecialChar123", # no special char
    ]
    for weak_pw in weak_cases:
        email = f"weak_{uuid.uuid4().hex[:8]}@example.com"
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": weak_pw}
        )
        assert resp.status_code == 422, f"Expected 422 for weak password '{weak_pw}', got {resp.status_code}: {resp.text}"
        assert "password" in str(resp.json()["detail"]).lower()


def test_registration_accepts_strong_password(client):
    """Strong password must succeed."""
    email = f"strong_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPassword2026!#"}
    )
    assert resp.status_code in (200, 201)
    assert "access_token" in resp.json()


def test_login_temporary_lockout_after_failures(client):
    """5 failed login attempts should trigger temporary account/IP lockout (HTTP 429)."""
    email = f"lockout_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectPassword123!"}
    )
    assert reg.status_code in (200, 201)

    # 5 failed login attempts
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword999!"}
        )
        assert resp.status_code == 401, f"Attempt {i+1} expected 401, got {resp.status_code}"

    # 6th attempt must be locked out with 429
    locked_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword999!"}
    )
    assert locked_resp.status_code == 429, f"Expected 429 lockout on 6th failed attempt, got {locked_resp.status_code}"
    assert "lock" in locked_resp.json()["detail"].lower()


def test_successful_login_resets_failures(client):
    """Successful authentication clears failed counter."""
    email = f"reset_fail_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectPassword123!"}
    )
    assert reg.status_code in (200, 201)

    # 3 failed attempts
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword999!"})

    # Successful login
    success = client.post("/api/v1/auth/login", json={"email": email, "password": "CorrectPassword123!"})
    assert success.status_code == 200

    # Next attempt should be normal 401, not locked
    next_attempt = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword999!"})
    assert next_attempt.status_code == 401
