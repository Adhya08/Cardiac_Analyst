"""
Automated Pytest Suite: Authentication & Access Control
=======================================================
Verifies:
1. User registration with valid credentials (201 Created + JWT token).
2. Registration rejecting duplicate email (400 Bad Request).
3. Registration rejecting weak passwords < 8 chars (422 Unprocessable Entity).
4. User login with valid credentials (200 OK + JWT token).
5. User login rejecting incorrect password (401 Unauthorized).
6. User login rejecting nonexistent email (401 Unauthorized).
7. Protected endpoint (/api/v1/auth/me) rejecting unauthenticated requests (401).
8. Protected endpoint (/api/v1/auth/me) allowing valid Bearer tokens (200 OK).
9. Updating profile for authenticated user (/api/v1/auth/me).
10. Multi-tenant User Isolation: Patient A cannot read Patient B's vitals history (403).
11. Multi-tenant User Isolation: Patient A cannot read Patient B's ECG history (403).
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models_db import User, VitalsLog, ECGAnalysis


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_register_success(client):
    unique_email = f"clinician_{uuid.uuid4().hex[:8]}@hospital.org"
    payload = {
        "email": unique_email,
        "password": "SecurePassword123!",
        "name": "Dr. Sarah Lin",
        "role": "clinician",
        "age": 42,
        "sex": "Female",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == unique_email
    assert data["user"]["role"] == "patient"


def test_register_duplicate_email(client):
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@hospital.org"
    payload = {
        "email": unique_email,
        "password": "Password123!",
        "name": "First User",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]


def test_register_short_password_rejected(client):
    payload = {
        "email": f"weak_{uuid.uuid4().hex[:8]}@hospital.org",
        "password": "short",  # < 8 chars
        "name": "Weak User",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


def test_login_success(client):
    email = f"user_{uuid.uuid4().hex[:8]}@hospital.org"
    password = "CorrectPassword123"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "name": "Login Tester",
    })

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_login_invalid_password(client):
    email = f"user_{uuid.uuid4().hex[:8]}@hospital.org"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "ValidPassword123",
        "name": "Login Tester",
    })

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword"})
    assert resp.status_code == 401
    assert "Incorrect email or password" in resp.json()["detail"]


def test_login_nonexistent_email(client):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@nowhere.com", "password": "AnyPassword123"})
    assert resp.status_code == 401


def test_protected_me_unauthorized(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_protected_me_authorized_and_update(client):
    email = f"auth_{uuid.uuid4().hex[:8]}@hospital.org"
    reg = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password12345",
        "name": "Original Name",
        "age": 35,
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch profile
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Original Name"

    # Update profile
    upd_resp = client.put("/api/v1/auth/me", headers=headers, json={
        "name": "Updated Clinician Name",
        "age": 36,
        "sex": "Female",
    })
    assert upd_resp.status_code == 200
    assert upd_resp.json()["name"] == "Updated Clinician Name"
    assert upd_resp.json()["age"] == 36


def test_user_isolation_vitals_history(client):
    # Register Patient A
    pA_email = f"patientA_{uuid.uuid4().hex[:8]}@domain.com"
    regA = client.post("/api/v1/auth/register", json={
        "email": pA_email,
        "password": "Password123!",
        "role": "patient",
    })
    tokenA = regA.json()["access_token"]
    userA_id = regA.json()["user"]["id"]

    # Register Patient B
    pB_email = f"patientB_{uuid.uuid4().hex[:8]}@domain.com"
    regB = client.post("/api/v1/auth/register", json={
        "email": pB_email,
        "password": "Password123!",
        "role": "patient",
    })
    tokenB = regB.json()["access_token"]
    userB_id = regB.json()["user"]["id"]

    # Patient A logs vitals
    vitals_payload = {
        "bp_sys": 120,
        "bp_dia": 80,
        "hr": 72,
        "weight": 70.0,
        "spo2": 98.0,
    }
    client.post("/api/v1/vitals", json=vitals_payload, headers={"Authorization": f"Bearer {tokenA}"})

    # Patient A can access their own history
    own_hist = client.get("/api/v1/vitals/history", headers={"Authorization": f"Bearer {tokenA}"})
    assert own_hist.status_code == 200
    assert len(own_hist.json()) >= 1

    # Patient B attempts to access Patient A's history -> Must receive 403 Forbidden!
    snoop_resp = client.get(f"/api/v1/vitals/history?user_id={userA_id}", headers={"Authorization": f"Bearer {tokenB}"})
    assert snoop_resp.status_code == 403
    assert "Access denied" in snoop_resp.json()["detail"]


def test_user_isolation_ecg_history(client):
    # Register Patient X
    pX_email = f"patientX_{uuid.uuid4().hex[:8]}@domain.com"
    regX = client.post("/api/v1/auth/register", json={
        "email": pX_email,
        "password": "Password123!",
        "role": "patient",
    })
    tokenX = regX.json()["access_token"]
    userX_id = regX.json()["user"]["id"]

    # Register Patient Y
    pY_email = f"patientY_{uuid.uuid4().hex[:8]}@domain.com"
    regY = client.post("/api/v1/auth/register", json={
        "email": pY_email,
        "password": "Password123!",
        "role": "patient",
    })
    tokenY = regY.json()["access_token"]

    # Patient Y attempts to query Patient X's ECG history -> Must receive 403 Forbidden!
    snoop_ecg = client.get(f"/api/v1/ecg/history?user_id={userX_id}", headers={"Authorization": f"Bearer {tokenY}"})
    assert snoop_ecg.status_code == 403
    assert "Access denied" in snoop_ecg.json()["detail"]
