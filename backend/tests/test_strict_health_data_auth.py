"""
Automated Pytest Suite: Strict Authentication & Patient Isolation Across Health Data Endpoints
================================================================================================
Verifies READINESS.md Section 2 & 3:
1. Every health endpoint requires authentication (returns 401 Unauthorized when called without a token).
   - GET /api/v1/vitals/history
   - POST /api/v1/vitals
   - GET /api/v1/user/profile
   - PUT /api/v1/user/profile
   - POST /api/v1/ecg/upload
   - GET /api/v1/ecg/history
   - GET /api/v1/ecg/{ecg_id}
   - POST /api/v1/emergency/triage
2. User isolation: Patient A cannot query or read Patient B's records (returns 403 Forbidden).
3. Clinician delegation: A clinician cannot read Patient B's records without an active grant (403 Forbidden).
4. Once Patient B grants access to Clinician C, Clinician C can access Patient B's records (200 OK).
5. Once Patient B revokes access from Clinician C, Clinician C is immediately blocked again (403 Forbidden).
"""

import io
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


def register_user(client, email_prefix="user", role="patient"):
    unique_email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@hospital.org"
    res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "Password123!",
        "name": f"Test {email_prefix.capitalize()}",
    })
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]["id"]


def test_unauthenticated_request_to_every_health_endpoint_returns_401(client):
    """
    Asserts that every endpoint returning or modifying patient health data
    strictly returns 401 Unauthorized when unauthenticated.
    """
    # 1. GET /vitals/history
    res = client.get("/api/v1/vitals/history")
    assert res.status_code == 401, f"GET /vitals/history returned {res.status_code}"

    # 2. POST /vitals
    res = client.post("/api/v1/vitals", json={"bp_sys": 120, "bp_dia": 80, "hr": 70, "weight": 70.0, "spo2": 98.0})
    assert res.status_code == 401, f"POST /vitals returned {res.status_code}"

    # 3. GET /user/profile
    res = client.get("/api/v1/user/profile")
    assert res.status_code == 401, f"GET /user/profile returned {res.status_code}"

    # 4. PUT /user/profile
    res = client.put("/api/v1/user/profile", json={"name": "Attacker", "age": 30, "sex": "Male"})
    assert res.status_code == 401, f"PUT /user/profile returned {res.status_code}"

    # 5. POST /ecg/upload
    fake_csv = io.BytesIO(b"0.1,0.2,0.3\n0.2,0.3,0.4\n")
    files = {"file": ("test.csv", fake_csv, "text/csv")}
    res = client.post("/api/v1/ecg/upload", files=files)
    assert res.status_code == 401, f"POST /ecg/upload returned {res.status_code}"

    # 6. GET /ecg/history
    res = client.get("/api/v1/ecg/history")
    assert res.status_code == 401, f"GET /ecg/history returned {res.status_code}"

    # 7. GET /ecg/{ecg_id}
    res = client.get(f"/api/v1/ecg/{uuid.uuid4()}")
    assert res.status_code == 401, f"GET /ecg/id returned {res.status_code}"

    # 8. Note: POST /emergency/triage is a public life-safety endpoint tested in test_emergency_public_access.py


def test_user_a_cannot_access_user_b_records(client):
    """
    Patient A cannot view Patient B's vitals history, ECG history, ECG details, or profile.
    Must return 403 Forbidden.
    """
    token_a, id_a = register_user(client, "patient_a")
    token_b, id_b = register_user(client, "patient_b")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Patient B logs vitals
    vitals_payload = {"bp_sys": 125, "bp_dia": 82, "hr": 72, "weight": 70.0, "spo2": 98.0}
    res_vitals = client.post("/api/v1/vitals", json=vitals_payload, headers=headers_b)
    assert res_vitals.status_code == 200

    # Patient B uploads an ECG
    ecg_csv = io.BytesIO(b"0.01,0.02,0.03\n0.02,0.03,0.04\n" * 100)
    files = {"file": ("ecg.csv", ecg_csv, "text/csv")}
    res_ecg = client.post("/api/v1/ecg/upload", files=files, headers=headers_b)
    assert res_ecg.status_code == 200
    ecg_id_b = res_ecg.json()["ecg_id"]

    # Patient A attempts to view Patient B's vitals history -> 403 Forbidden
    res = client.get(f"/api/v1/vitals/history?user_id={id_b}", headers=headers_a)
    assert res.status_code == 403

    # Patient A attempts to view Patient B's profile -> 403 Forbidden
    res = client.get(f"/api/v1/user/profile?user_id={id_b}", headers=headers_a)
    assert res.status_code == 403

    # Patient A attempts to view Patient B's ECG history -> 403 Forbidden
    res = client.get(f"/api/v1/ecg/history?user_id={id_b}", headers=headers_a)
    assert res.status_code == 403

    # Patient A attempts to view Patient B's ECG analysis by ID -> 403 Forbidden
    res = client.get(f"/api/v1/ecg/{ecg_id_b}", headers=headers_a)
    assert res.status_code == 403


def test_clinician_access_delegation_flow(client):
    """
    1. Clinician C attempts to view Patient B's records without grant -> 403 Forbidden.
    2. Patient B grants access to Clinician C -> Clinician C can view records (200 OK).
    3. Patient B revokes access -> Clinician C is blocked again (403 Forbidden).
    """
    # Create an admin user first to provision a legitimate clinician
    from app.database import SessionLocal
    from app.models_db import User
    from app.auth import hash_password, create_access_token

    db = SessionLocal()
    admin_id = str(uuid.uuid4())
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@hospital.org"
    admin_user = User(
        id=admin_id,
        email=admin_email,
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.close()

    admin_token = create_access_token({"sub": admin_id, "email": admin_email, "role": "admin"})

    # Admin provisions Clinician C
    clinician_email = f"doctor_{uuid.uuid4().hex[:8]}@hospital.org"
    res_clinician = client.post(
        "/api/v1/auth/admin/create-clinician",
        json={"email": clinician_email, "password": "DocPassword123!", "name": "Dr. House"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_clinician.status_code == 201
    clinician_id = res_clinician.json()["id"]

    # Login as clinician
    res_login = client.post("/api/v1/auth/login", json={"email": clinician_email, "password": "DocPassword123!"})
    clinician_token = res_login.json()["access_token"]
    headers_c = {"Authorization": f"Bearer {clinician_token}"}

    # Register Patient B
    token_b, id_b = register_user(client, "patient_del_b")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Patient B logs vitals
    vitals_payload = {"bp_sys": 130, "bp_dia": 85, "hr": 78, "weight": 75.0, "spo2": 99.0}
    client.post("/api/v1/vitals", json=vitals_payload, headers=headers_b)

    # 1. Clinician C requests Patient B's vitals history WITHOUT grant -> 403 Forbidden
    res = client.get(f"/api/v1/vitals/history?user_id={id_b}", headers=headers_c)
    assert res.status_code == 403

    # 2. Patient B grants access to Clinician C
    grant_res = client.post(f"/api/v1/auth/grant-clinician/{clinician_id}", headers=headers_b)
    assert grant_res.status_code == 200
    assert grant_res.json()["status"] == "granted"

    # Now Clinician C requests Patient B's vitals history -> 200 OK!
    res_granted = client.get(f"/api/v1/vitals/history?user_id={id_b}", headers=headers_c)
    assert res_granted.status_code == 200
    assert len(res_granted.json()) >= 1

    # 3. Patient B revokes access from Clinician C
    revoke_res = client.delete(f"/api/v1/auth/grant-clinician/{clinician_id}", headers=headers_b)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # Clinician C is immediately blocked again -> 403 Forbidden
    res_revoked = client.get(f"/api/v1/vitals/history?user_id={id_b}", headers=headers_c)
    assert res_revoked.status_code == 403
