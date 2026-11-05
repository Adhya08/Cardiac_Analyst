"""
Automated Pytest Suite: Emergency Public Access & Safety (Item 1)
==================================================================
Verifies:
1. POST /api/v1/emergency/triage works WITHOUT login (returns 200 OK, full triage + hospitals).
2. Unauthenticated emergency triage does NOT read or store any user data in DB.
3. Invalid or expired token does NOT block emergency triage (returns 200 OK, does not save).
4. Authenticated emergency triage links and saves event to current_user.id.
5. POST /api/v1/emergency/sos returns immediate emergency instructions and contacts without login.
6. GET /api/v1/hospitals/nearby and GET /api/v1/ambulance/nearby work without login.
7. IP-based rate limiting enforces protection against rapid automated spam (HTTP 429).
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, SessionLocal
from app.models_db import TriageEvent, User


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


def test_emergency_triage_without_token_returns_200(client):
    """Fails on old code that requires authentication (returns 401)."""
    db = SessionLocal()
    initial_count = db.query(TriageEvent).count()
    db.close()

    payload = {
        "symptoms": [True, True, False, False, False, True, False, False],
        "bp_sys": 130,
        "hr": 80,
        "lat": 28.6139,
        "lon": 77.2090,
    }
    resp = client.post("/api/v1/emergency/triage", json=payload)
    assert resp.status_code == 200, f"Expected 200 OK for emergency triage, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["severity"] == "emergency"
    assert len(data["hospitals"]) > 0
    assert len(data["ambulances"]) > 0
    assert data["triage_id"] == "unauthenticated"

    # Ensure nothing was saved to DB for unauthenticated caller
    db = SessionLocal()
    after_count = db.query(TriageEvent).count()
    db.close()
    assert after_count == initial_count, "Unauthenticated triage event must NOT be stored in DB!"


def test_emergency_triage_with_invalid_or_expired_token(client):
    """Fails on old code that rejects invalid tokens with 401."""
    payload = {
        "symptoms": [False] * 8,
        "lat": 28.6139,
        "lon": 77.2090,
    }
    resp = client.post(
        "/api/v1/emergency/triage",
        json=payload,
        headers={"Authorization": "Bearer invalid_expired_garbage_token"}
    )
    assert resp.status_code == 200, f"Expected 200 OK even with expired/invalid token, got {resp.status_code}"
    assert resp.json()["triage_id"] == "unauthenticated"


def test_emergency_triage_with_valid_token_saves_to_user(client):
    """Authenticated users have their emergency triage event persisted."""
    email = f"emer_patient_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]

    db = SessionLocal()
    initial_user_events = db.query(TriageEvent).filter(TriageEvent.user_id == user_id).count()
    db.close()

    payload = {
        "symptoms": [True, True, False, False, False, False, False, False],
        "lat": 28.6139,
        "lon": 77.2090,
    }
    resp = client.post(
        "/api/v1/emergency/triage",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    triage_id = resp.json()["triage_id"]
    assert triage_id != "unauthenticated"

    db = SessionLocal()
    saved = db.query(TriageEvent).filter(TriageEvent.id == triage_id).first()
    assert saved is not None
    assert saved.user_id == user_id
    db.close()


def test_emergency_sos_endpoint_without_token(client):
    """Test SOS emergency broadcast endpoint without login."""
    resp = client.post("/api/v1/emergency/sos", json={"lat": 28.6139, "lon": 77.2090})
    assert resp.status_code == 200
    data = resp.json()
    assert "112" in str(data)
    assert "hospitals" in data


def test_emergency_hospitals_and_ambulances_without_token(client):
    """Test hospital and ambulance lookups work without login."""
    h_resp = client.get("/api/v1/hospitals/nearby?lat=28.6139&lon=77.2090")
    assert h_resp.status_code == 200
    assert len(h_resp.json()["hospitals"]) > 0

    a_resp = client.get("/api/v1/ambulance/nearby?lat=28.6139&lon=77.2090")
    assert a_resp.status_code == 200
    assert len(a_resp.json()["ambulances"]) > 0


def test_emergency_ip_rate_limiting(client):
    """Test IP rate limiting on public emergency endpoints."""
    hit_429 = False
    for _ in range(40):
        resp = client.post(
            "/api/v1/emergency/triage",
            json={"symptoms": [False] * 8, "lat": 28.6139, "lon": 77.2090}
        )
        if resp.status_code == 429:
            hit_429 = True
            assert "Retry-After" in resp.headers or "detail" in resp.json()
            break
    assert hit_429, "Expected IP rate limiter to trigger HTTP 429 on rapid requests"

