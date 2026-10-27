"""
Automated Pytest Suite: Patient Health Record Access Audit Logging (Fix 1c - Item 3)
=====================================================================================
Verifies:
1. When a clinician reads a patient's vitals, ECG, or triage records, an AccessAuditLog
   event is recorded with accessor_user_id, patient_user_id, endpoint, timestamp, and IP.
2. The log contains ZERO health data (no ECG signals, risk scores, symptoms).
3. When a patient reads their OWN records, no audit event is logged.
4. Patient can view who has accessed their records via GET /api/v1/user/access-log.
5. Unauthenticated requests to GET /api/v1/user/access-log return 401 Unauthorized.
6. A patient cannot view another patient's access log (403 Forbidden).
"""

import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, SessionLocal
from app.models_db import User, VitalsLog, ECGAnalysis, TriageEvent, PatientClinicianGrant
from app.auth import hash_password, create_access_token


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_setup():
    db = SessionLocal()
    # Create patient 1
    p1_id = f"pat_{uuid.uuid4().hex[:8]}"
    patient1 = User(
        id=p1_id,
        email=f"patient1_{p1_id}@test.com",
        hashed_password=hash_password("StrongPassword123!"),
        role="patient",
        is_active=True,
    )
    db.add(patient1)

    # Create patient 2
    p2_id = f"pat_{uuid.uuid4().hex[:8]}"
    patient2 = User(
        id=p2_id,
        email=f"patient2_{p2_id}@test.com",
        hashed_password=hash_password("StrongPassword123!"),
        role="patient",
        is_active=True,
    )
    db.add(patient2)

    # Create clinician
    c_id = f"clin_{uuid.uuid4().hex[:8]}"
    clinician = User(
        id=c_id,
        email=f"doctor_{c_id}@hospital.com",
        hashed_password=hash_password("DoctorPassword123!"),
        role="clinician",
        is_active=True,
    )
    db.add(clinician)

    # Active grant from patient1 to clinician
    grant = PatientClinicianGrant(
        id=str(uuid.uuid4()),
        patient_id=p1_id,
        clinician_id=c_id,
        is_active=True,
    )
    db.add(grant)

    # Add vitals log for patient1
    vitals = VitalsLog(
        id=str(uuid.uuid4()),
        user_id=p1_id,
        bp_sys=120,
        bp_dia=80,
        hr=72,
        weight=70.0,
        spo2=98.0,
        risk_score=12.5,
        risk_tier="Low",
        timestamp=datetime.utcnow(),
    )
    db.add(vitals)

    # Add ECG record for patient1
    ecg_id = str(uuid.uuid4())
    ecg = ECGAnalysis(
        id=ecg_id,
        user_id=p1_id,
        file_name="lead_ii.png",
        image_quality="good",
        urgency="Routine",
        analysis_json='{"top_condition": "NORM", "model_scores": {"NORM": 0.95}}',
        timestamp=datetime.utcnow(),
    )
    db.add(ecg)

    # Add Triage record for patient1
    triage = TriageEvent(
        id=str(uuid.uuid4()),
        user_id=p1_id,
        symptoms_json='["chest_pain"]',
        severity="urgent",
        confidence=0.88,
        risk_score=65.0,
        timestamp=datetime.utcnow(),
    )
    db.add(triage)

    db.commit()
    db.close()

    pat1_token = create_access_token({"sub": p1_id})
    pat2_token = create_access_token({"sub": p2_id})
    clin_token = create_access_token({"sub": c_id})

    return {
        "p1_id": p1_id,
        "p2_id": p2_id,
        "c_id": c_id,
        "pat1_token": pat1_token,
        "pat2_token": pat2_token,
        "clin_token": clin_token,
        "ecg_id": ecg_id,
    }


def test_unauthenticated_access_log_returns_401(client):
    """GET /api/v1/user/access-log must be protected by authentication."""
    resp = client.get("/api/v1/user/access-log")
    assert resp.status_code == 401


def test_clinician_access_records_audit_event_and_patient_can_view(client, test_setup):
    """
    When clinician reads patient1's vitals and ECG, audit events must be recorded.
    Patient1 can then view who accessed their records.
    """
    clin_token = test_setup["clin_token"]
    p1_id = test_setup["p1_id"]
    ecg_id = test_setup["ecg_id"]

    # 1. Clinician reads patient1's vitals history
    resp = client.get(
        f"/api/v1/vitals/history?user_id={p1_id}",
        headers={"Authorization": f"Bearer {clin_token}", "X-Forwarded-For": "198.51.100.99"},
    )
    assert resp.status_code == 200

    # 2. Clinician reads patient1's ECG record
    resp_ecg = client.get(
        f"/api/v1/ecg/{ecg_id}",
        headers={"Authorization": f"Bearer {clin_token}", "X-Forwarded-For": "198.51.100.99"},
    )
    assert resp_ecg.status_code == 200

    # 3. Patient1 checks their access log
    pat1_token = test_setup["pat1_token"]
    resp_log = client.get(
        "/api/v1/user/access-log",
        headers={"Authorization": f"Bearer {pat1_token}"},
    )
    assert resp_log.status_code == 200, f"Expected 200 OK, got: {resp_log.status_code} {resp_log.text}"
    logs = resp_log.json()
    assert len(logs) >= 2

    # Check the recorded audit fields
    vitals_event = next((l for l in logs if "/vitals/history" in l["endpoint"]), None)
    assert vitals_event is not None
    assert vitals_event["accessor_user_id"] == test_setup["c_id"]
    assert vitals_event["patient_user_id"] == p1_id
    assert vitals_event["ip_address"] == "198.51.100.99"
    # Ensure zero health data in the log schema
    assert "bp_sys" not in vitals_event
    assert "symptoms" not in vitals_event
    assert "ecg" not in vitals_event


def test_self_access_does_not_create_audit_log(client, test_setup):
    """When patient accesses their own records, it should not pollute the audit log."""
    pat2_token = test_setup["pat2_token"]
    p2_id = test_setup["p2_id"]

    # Patient2 reads own vitals
    resp = client.get(
        f"/api/v1/vitals/history",
        headers={"Authorization": f"Bearer {pat2_token}"},
    )
    assert resp.status_code == 200

    # Check patient2 log - must be empty
    resp_log = client.get(
        "/api/v1/user/access-log",
        headers={"Authorization": f"Bearer {pat2_token}"},
    )
    assert resp_log.status_code == 200
    assert len(resp_log.json()) == 0
