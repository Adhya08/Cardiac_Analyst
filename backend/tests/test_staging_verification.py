"""
Pytest Suite: Staging End-to-End Guarantees Verification
=========================================================
Runs the exact 5 staging audit checks in-process via FastAPI TestClient:
1. Health check recovery.
2. Unauthenticated access to every health endpoint returns 401.
3. Registration role injection immunity (attacker requesting clinician is forced to patient).
4. Strict cross-tenant isolation (User A cannot read User B).
5. Public emergency access without authentication.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_staging_health_and_wake(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_staging_unauthenticated_health_endpoints_return_401(client):
    protected_endpoints = [
        ("GET", "/api/v1/vitals/history"),
        ("POST", "/api/v1/vitals"),
        ("GET", "/api/v1/user/profile"),
        ("GET", "/api/v1/ecg/history"),
        ("POST", "/api/v1/ecg/upload"),
        ("GET", "/api/v1/emergency/history"),
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/user/access-log"),
        ("GET", "/api/v1/consent"),
    ]
    for method, path in protected_endpoints:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={})
        assert r.status_code == 401, f"Expected 401 Unauthorized for {method} {path}, got {r.status_code}"


def test_staging_registration_strictly_forces_patient_role(client):
    email = f"staging_reg_{uuid.uuid4().hex[:8]}@hospital.org"
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "role": "clinician"})
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["user"]["role"] == "patient", "Role injection attack must be ignored!"


def test_staging_user_a_cannot_read_user_b(client):
    # Register user A
    email_a = f"staging_usera_{uuid.uuid4().hex[:8]}@hospital.org"
    token_a = client.post("/api/v1/auth/register", json={"email": email_a, "password": "Password123!"}).json()["access_token"]

    # Register user B
    email_b = f"staging_userb_{uuid.uuid4().hex[:8]}@hospital.org"
    data_b = client.post("/api/v1/auth/register", json={"email": email_b, "password": "Password123!"}).json()
    token_b = data_b["access_token"]
    user_b_id = data_b["user"]["id"]

    # Post vitals for B
    vitals_resp = client.post(
        "/api/v1/vitals",
        json={"bp_sys": 120, "bp_dia": 80, "hr": 70, "weight": 70.0, "spo2": 98.0},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert vitals_resp.status_code == 200

    # User A tries to read User B's vitals & triage
    vitals_probe = client.get(f"/api/v1/vitals/history?user_id={user_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert vitals_probe.status_code == 403

    triage_probe = client.get(f"/api/v1/emergency/history?user_id={user_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert triage_probe.status_code == 403


def test_staging_emergency_mode_works_when_logged_out(client):
    # Public triage
    triage_resp = client.post(
        "/api/v1/emergency/triage",
        json={"symptoms": [False] * 12, "lat": 28.6139, "lon": 77.2090},
    )
    assert triage_resp.status_code == 200
    data = triage_resp.json()
    assert data["severity"] == "no_emergency_warning_signs"
    assert len(data["hospitals"]) > 0
    assert len(data["ambulances"]) > 0

    # Public SOS
    sos_resp = client.post("/api/v1/emergency/sos", json={})
    assert sos_resp.status_code == 200
    assert len(sos_resp.json()["emergency_hotlines"]) >= 3
