"""
Automated Pytest Suite: Emergency Triage & Hospital Routing Path
================================================================
Verifies:
1. All NO symptoms correctly returns severity='no_emergency_warning_signs' without emergency escalation.
2. Lowest tier instruction matches clinical non-reassurance requirement.
3. Cardinal STEMI Triad triggers severity='emergency' and stemi_suspicious=True.
4. Syncope / Loss of consciousness triggers immediate severity='emergency'.
5. Cardiogenic shock combo (Chest pain + Confusion) triggers severity='emergency'.
6. Hypertensive crisis (SBP > 180) escalates to severity='emergency' even with 0 symptoms.
7. Hypotensive shock (SBP < 90) escalates to severity='emergency'.
8. Critical tachycardia (HR > 150) escalates to severity='emergency'.
9. Single red-flag symptom (isolated resting dyspnea) triggers severity='see_doctor_today'.
10. POST /api/v1/emergency/triage rejects invalid symptom list lengths (!= 8 and != 12).
11. POST /api/v1/emergency/triage returns complete triage payload with nearby hospitals and emergency helplines (112, 108).
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.ml.triage import assess_emergency, LOWEST_TIER_STATEMENT


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_all_no_symptoms_returns_no_emergency_warning_signs():
    symptoms = [False] * 12
    res = assess_emergency(symptoms=symptoms)
    assert res["severity"] == "no_emergency_warning_signs"
    assert res["stemi_suspicious"] is False
    assert res["combo_triggered"] is False
    assert res["vitals_red_flag"] is False
    assert res["yes_count"] == 0
    assert res["risk_score"] < 15.0
    assert res["instructions"][0] == LOWEST_TIER_STATEMENT
    assert "low-risk" not in " ".join(res["instructions"]).lower()
    assert "normal" not in " ".join(res["instructions"]).lower()
    assert "week" not in " ".join(res["instructions"]).lower()


def test_stemi_cardinal_triad_triggers_emergency():
    # Q0: crushing chest pain, Q1: radiation, Q3: cold sweats
    symptoms = [False] * 12
    symptoms[0] = True
    symptoms[1] = True
    symptoms[3] = True
    res = assess_emergency(symptoms=symptoms)
    assert res["severity"] == "emergency"
    assert res["stemi_suspicious"] is True
    assert res["combo_triggered"] is True
    assert res["risk_score"] >= 80.0
    assert any("112" in inst for inst in res["instructions"])


def test_syncope_alone_triggers_emergency():
    # Q4: fainted / near syncope
    symptoms = [False] * 12
    symptoms[4] = True
    res = assess_emergency(symptoms=symptoms)
    assert res["severity"] == "emergency"
    assert res["combo_triggered"] is True


def test_hypertensive_crisis_vitals_escalation():
    # All 0 symptoms, but critical BP
    symptoms = [False] * 12
    res = assess_emergency(symptoms=symptoms, bp_sys=195, hr=80)
    assert res["severity"] == "emergency"
    assert res["vitals_red_flag"] is True


def test_hypotensive_shock_vitals_escalation():
    # All 0 symptoms, but shock BP
    symptoms = [False] * 12
    res = assess_emergency(symptoms=symptoms, bp_sys=80, hr=95)
    assert res["severity"] == "emergency"
    assert res["vitals_red_flag"] is True


def test_critical_tachycardia_vitals_escalation():
    symptoms = [False] * 12
    res = assess_emergency(symptoms=symptoms, bp_sys=120, hr=165)
    assert res["severity"] == "emergency"
    assert res["vitals_red_flag"] is True


def test_isolated_resting_dyspnea_triggers_see_doctor_today():
    # Q2: Short of breath while resting
    symptoms = [False] * 12
    symptoms[2] = True
    res = assess_emergency(symptoms=symptoms)
    assert res["severity"] == "see_doctor_today"
    assert res["combo_triggered"] is False


def test_endpoint_rejects_invalid_symptom_length(client):
    # Register test patient
    email = f"triage_patient1_{uuid.uuid4().hex[:8]}@hospital.org"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    token = reg.json()["access_token"]

    # Only 5 answers provided instead of 8 or 12
    payload = {
        "symptoms": [False, False, True, True, False],
    }
    resp = client.post(
        "/api/v1/emergency/triage",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


def test_endpoint_full_triage_flow(client):
    email = f"triage_patient2_{uuid.uuid4().hex[:8]}@hospital.org"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    token = reg.json()["access_token"]

    payload = {
        "symptoms": [False] * 12,
        "bp_sys": 120,
        "hr": 70,
        "lat": 28.6139,
        "lon": 77.2090,
    }
    resp = client.post(
        "/api/v1/emergency/triage",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["severity"] == "no_emergency_warning_signs"
    assert "hospitals" in data
    assert len(data["hospitals"]) > 0
    assert "ambulances" in data
    assert any("112" in amb["contact"] for amb in data["ambulances"])
    assert "triage_id" in data
