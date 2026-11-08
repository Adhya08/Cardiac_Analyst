"""
Automated Pytest Suite: Clinician Grants by Email and Invite Code (Fix 1c - Item 4)
====================================================================================
Verifies:
1. Patient grants and revokes clinician access by clinician email (not internal UUID).
2. Patient grants and revokes clinician access by invite code.
3. User enumeration is strictly prevented: querying a non-existent email and querying
   a real patient's email return the EXACT same generic error (HTTP 400).
4. Clinician access status takes effect immediately on health data endpoints.
5. Endpoints require authentication (401 Unauthorized).
"""

import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, SessionLocal
from app.models_db import User, VitalsLog
from app.auth import hash_password, create_access_token


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def grant_setup():
    db = SessionLocal()
    # Patient 1
    p1_id = f"pat_{uuid.uuid4().hex[:8]}"
    patient1 = User(
        id=p1_id,
        email=f"patient1_{p1_id}@test.com",
        hashed_password=hash_password("Pass123!"),
        role="patient",
        is_active=True,
    )
    db.add(patient1)

    # Patient 2 (another patient, NOT a clinician)
    p2_id = f"pat_{uuid.uuid4().hex[:8]}"
    p2_email = f"patient2_{p2_id}@test.com"
    patient2 = User(
        id=p2_id,
        email=p2_email,
        hashed_password=hash_password("Pass123!"),
        role="patient",
        is_active=True,
    )
    db.add(patient2)

    # Clinician
    c_id = f"clin_{uuid.uuid4().hex[:8]}"
    c_email = f"dr.smith_{c_id}@hospital.org"
    invite_code = f"DR-{uuid.uuid4().hex[:6].upper()}"
    clinician = User(
        id=c_id,
        email=c_email,
        hashed_password=hash_password("DocPass123!"),
        role="clinician",
        invite_code=invite_code,
        is_active=True,
    )
    db.add(clinician)

    # Vitals for patient1
    vitals = VitalsLog(
        id=str(uuid.uuid4()),
        user_id=p1_id,
        bp_sys=125,
        bp_dia=82,
        hr=70,
        weight=68.0,
        spo2=99.0,
        risk_score=10.0,
        risk_tier="Low",
        timestamp=datetime.utcnow(),
    )
    db.add(vitals)

    db.commit()
    db.close()

    pat1_token = create_access_token({"sub": p1_id})
    clin_token = create_access_token({"sub": c_id})

    return {
        "p1_id": p1_id,
        "p2_email": p2_email,
        "c_id": c_id,
        "c_email": c_email,
        "invite_code": invite_code,
        "pat1_token": pat1_token,
        "clin_token": clin_token,
    }


def test_grant_endpoints_require_authentication(client):
    """Grant and revoke endpoints must require Bearer authentication."""
    res_grant = client.post("/api/v1/auth/grant-clinician", json={"email": "doc@test.com"})
    assert res_grant.status_code == 401

    res_revoke = client.post("/api/v1/auth/revoke-clinician", json={"email": "doc@test.com"})
    assert res_revoke.status_code == 401


def test_patient_can_grant_and_revoke_by_email(client, grant_setup):
    """Patient grants access to clinician using email, verifies access, and revokes it."""
    pat_token = grant_setup["pat1_token"]
    clin_token = grant_setup["clin_token"]
    p1_id = grant_setup["p1_id"]
    c_email = grant_setup["c_email"]

    # Before grant: clinician cannot access patient's vitals (403)
    res_pre = client.get(f"/api/v1/vitals/history?user_id={p1_id}", headers={"Authorization": f"Bearer {clin_token}"})
    assert res_pre.status_code == 403

    # Patient grants clinician by email
    res_grant = client.post(
        "/api/v1/auth/grant-clinician",
        json={"email": c_email},
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert res_grant.status_code == 200, f"Expected 200 OK, got: {res_grant.status_code} {res_grant.text}"
    assert res_grant.json()["status"] == "granted"

    # After grant: clinician can read vitals
    res_post = client.get(f"/api/v1/vitals/history?user_id={p1_id}", headers={"Authorization": f"Bearer {clin_token}"})
    assert res_post.status_code == 200

    # Patient revokes clinician by email
    res_revoke = client.post(
        "/api/v1/auth/revoke-clinician",
        json={"email": c_email},
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "revoked"

    # Clinician is immediately blocked again (403)
    res_blocked = client.get(f"/api/v1/vitals/history?user_id={p1_id}", headers={"Authorization": f"Bearer {clin_token}"})
    assert res_blocked.status_code == 403


def test_patient_can_grant_and_revoke_by_invite_code(client, grant_setup):
    """Patient grants access to clinician using invite code, and revokes it."""
    pat_token = grant_setup["pat1_token"]
    clin_token = grant_setup["clin_token"]
    p1_id = grant_setup["p1_id"]
    invite_code = grant_setup["invite_code"]

    # Grant via invite code
    res_grant = client.post(
        "/api/v1/auth/grant-clinician",
        json={"invite_code": invite_code},
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert res_grant.status_code == 200
    assert res_grant.json()["status"] == "granted"

    # Clinician reads vitals
    res_check = client.get(f"/api/v1/vitals/history?user_id={p1_id}", headers={"Authorization": f"Bearer {clin_token}"})
    assert res_check.status_code == 200

    # Revoke via invite code
    res_revoke = client.post(
        "/api/v1/auth/revoke-clinician",
        json={"invite_code": invite_code},
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "revoked"

    # Blocked again
    res_blocked = client.get(f"/api/v1/vitals/history?user_id={p1_id}", headers={"Authorization": f"Bearer {clin_token}"})
    assert res_blocked.status_code == 403


def test_grant_avoids_user_enumeration(client, grant_setup):
    """
    Querying a nonexistent email and querying a real patient's email
    MUST return the exact same generic error (status 400 and detail message).
    """
    pat_token = grant_setup["pat1_token"]
    p2_email = grant_setup["p2_email"]

    # 1. Nonexistent email
    res_nonexistent = client.post(
        "/api/v1/auth/grant-clinician",
        json={"email": "nonexistent_fake_user@hospital.com"},
        headers={"Authorization": f"Bearer {pat_token}"},
    )

    # 2. Real patient email (not a clinician)
    res_patient = client.post(
        "/api/v1/auth/grant-clinician",
        json={"email": p2_email},
        headers={"Authorization": f"Bearer {pat_token}"},
    )

    # Both must return HTTP 400 with identical error detail
    assert res_nonexistent.status_code == 400
    assert res_patient.status_code == 400
    assert res_nonexistent.json()["detail"] == res_patient.json()["detail"]
    assert "Invalid clinician email or invite code" in res_nonexistent.json()["detail"]
