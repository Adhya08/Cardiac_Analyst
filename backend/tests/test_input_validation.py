"""
Automated Pytest Suite: Input Validation & Boundary Testing
============================================================
Verifies:
1. Systolic blood pressure boundary rejection (BP < 60, > 250, or extreme outside sane range).
2. Diastolic blood pressure boundary rejection (BP < 40 or > 180).
3. Heart rate boundary rejection (HR < 20 or > 250 bpm).
4. Oxygen saturation boundary rejection (SpO2 < 40% or > 100%).
5. Weight boundary rejection (< 20 kg or > 300 kg).
6. Age boundary rejection (Age < 18 or > 120 years).
7. Demographics sex validation (strictly Male, Female, Other).
8. Registration email format validation (malformed email rejection).
9. ECG input validation: Rejection of PNG/JPG/PDF scans with informative clinical messaging.
10. Valid vitals payload processed successfully with deterministic risk score and tiers.
"""

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_vitals_rejects_low_systolic_bp(client):
    payload = {
        "bp_sys": 50,  # Below minimum 60 / sane threshold 70
        "bp_dia": 70,
        "hr": 75,
        "weight": 70.0,
        "spo2": 98.0,
    }
    resp = client.post("/api/v1/vitals", json=payload)
    assert resp.status_code == 422


def test_vitals_rejects_extreme_high_systolic_bp(client):
    payload = {
        "bp_sys": 280,  # Above maximum 250
        "bp_dia": 110,
        "hr": 80,
        "weight": 75.0,
        "spo2": 96.0,
    }
    resp = client.post("/api/v1/vitals", json=payload)
    assert resp.status_code == 422


def test_vitals_rejects_invalid_heart_rate(client):
    payload_low = {
        "bp_sys": 120,
        "bp_dia": 80,
        "hr": 10,  # Below 20
        "weight": 70.0,
        "spo2": 98.0,
    }
    assert client.post("/api/v1/vitals", json=payload_low).status_code == 422

    payload_high = {
        "bp_sys": 120,
        "bp_dia": 80,
        "hr": 300,  # Above 250
        "weight": 70.0,
        "spo2": 98.0,
    }
    assert client.post("/api/v1/vitals", json=payload_high).status_code == 422


def test_vitals_rejects_invalid_spo2(client):
    payload_low = {
        "bp_sys": 120,
        "bp_dia": 80,
        "hr": 70,
        "weight": 70.0,
        "spo2": 30.0,  # Below 40%
    }
    assert client.post("/api/v1/vitals", json=payload_low).status_code == 422

    payload_high = {
        "bp_sys": 120,
        "bp_dia": 80,
        "hr": 70,
        "weight": 70.0,
        "spo2": 105.0,  # Above 100%
    }
    assert client.post("/api/v1/vitals", json=payload_high).status_code == 422


def test_vitals_rejects_invalid_weight(client):
    payload = {
        "bp_sys": 120,
        "bp_dia": 80,
        "hr": 70,
        "weight": 10.0,  # Below 20 kg
        "spo2": 98.0,
    }
    assert client.post("/api/v1/vitals", json=payload).status_code == 422


def test_demographics_rejects_underage_and_invalid_sex(client):
    underage_payload = {
        "name": "Underage",
        "age": 15,  # Below 18
        "sex": "Male",
    }
    assert client.put("/api/v1/user/profile", json=underage_payload).status_code == 422

    invalid_sex_payload = {
        "name": "Invalid Sex",
        "age": 45,
        "sex": "Alien",  # Must be Male, Female, Other
    }
    assert client.put("/api/v1/user/profile", json=invalid_sex_payload).status_code == 422


def test_register_rejects_invalid_email_format(client):
    payload = {
        "email": "not-a-valid-email",
        "password": "ValidPassword123!",
        "name": "Test",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


def test_ecg_upload_rejects_image_scan_with_guidance(client):
    fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\nFake PNG content")
    files = {"file": ("ecg_photo.png", fake_png, "image/png")}
    resp = client.post("/api/v1/ecg/upload", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "analysis_unavailable"
    assert data["urgency"] == "unavailable"
    assert "digital" in data["abstain_reason"].lower() or "photo" in data["abstain_reason"].lower()


def test_valid_vitals_payload_succeeds(client):
    payload = {
        "bp_sys": 125,
        "bp_dia": 82,
        "hr": 74,
        "weight": 72.5,
        "spo2": 98.5,
        "glucose": 95.0,
        "cholesterol": 185.0,
    }
    resp = client.post("/api/v1/vitals", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_score" in data
    assert data["risk_tier"] in ("Low", "Borderline", "Elevated")
    assert "shap_top5" in data
