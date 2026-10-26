"""
Test Registration Role Hardening & Admin Path
----------------------------------------------
Asserts that:
1. Public self-registration ALWAYS creates a patient and strictly ignores any client-supplied role.
2. Clinician creation is restricted to an admin-only path.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models_db import User
from app.auth import create_access_token, hash_password


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_self_registration_ignores_role_and_defaults_to_patient(client):
    """
    Asserts that public registration ignores 'role': 'clinician' or 'role': 'admin'
    and strictly creates a patient account.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"attacker_{unique_suffix}@example.com",
        "password": "SecurePassword123!",
        "role": "clinician",  # Attacker attempts to self-promote to clinician
        "name": "Attacker Trying Clinician",
        "age": 35,
        "sex": "Male",
    }
    
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["role"] == "patient", f"Expected patient, but got {data['user']['role']}"


def test_self_registration_without_role_creates_patient(client):
    """Registration without role field also creates a patient."""
    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"patient_{unique_suffix}@example.com",
        "password": "SecurePassword123!",
        "name": "Normal Patient",
        "age": 40,
        "sex": "Female",
    }
    
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["role"] == "patient"


def test_admin_create_clinician_requires_admin(client):
    """Non-admin or unauthenticated cannot call admin clinician creation route."""
    unique_suffix = uuid.uuid4().hex[:8]
    clinician_payload = {
        "email": f"dr_smith_{unique_suffix}@example.com",
        "password": "DoctorPassword123!",
        "name": "Dr. Smith",
        "age": 45,
        "sex": "Female",
    }
    
    # 1. Unauthenticated -> 401
    res1 = client.post("/api/v1/auth/admin/create-clinician", json=clinician_payload)
    assert res1.status_code == 401
    
    # 2. Patient token -> 403 Forbidden
    db = SessionLocal()
    patient = User(
        email=f"patient_token_{unique_suffix}@example.com",
        hashed_password=hash_password("Pass12345!"),
        role="patient",
        name="Test Patient"
    )
    admin = User(
        email=f"admin_{unique_suffix}@example.com",
        hashed_password=hash_password("Pass12345!"),
        role="admin",
        name="Admin User"
    )
    db.add(patient)
    db.add(admin)
    db.commit()
    db.refresh(patient)
    db.refresh(admin)
    db.close()
    
    patient_token = create_access_token({"sub": patient.id, "email": patient.email, "role": "patient"})
    res2 = client.post(
        "/api/v1/auth/admin/create-clinician",
        json=clinician_payload,
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert res2.status_code == 403
    
    # 3. Admin token -> 201 Created and role is clinician
    admin_token = create_access_token({"sub": admin.id, "email": admin.email, "role": "admin"})
    res3 = client.post(
        "/api/v1/auth/admin/create-clinician",
        json=clinician_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res3.status_code == 201
    assert res3.json()["role"] == "clinician"
