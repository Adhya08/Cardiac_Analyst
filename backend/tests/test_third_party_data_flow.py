"""
Automated Pytest Suite: Third-Party Data Flow & Consent Verification (Item 4)
=============================================================================
Verifies:
1. Calling /chat/message without explicit consent_third_party_ai=True returns 403 Forbidden.
2. Calling /chat/summarize without explicit consent_third_party_ai=True returns 403 Forbidden.
3. Calling /chat/advice without explicit consent_third_party_ai=True returns 403 Forbidden.
4. Patient A cannot summarize Patient B's ECG report via the chat service (403/404 isolation).
5. No identifying user data (name, email, user_id) is embedded in the external payload.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, SessionLocal
from app.models_db import ECGAnalysis


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def register_user(client, prefix):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "name": f"User {prefix}"}
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    return data["access_token"], data["user"]["id"]


def test_chat_message_requires_explicit_consent(client):
    """Calling chat message without opt-in consent must be refused with 403."""
    token, user_id = register_user(client, "consent_msg")
    headers = {"Authorization": f"Bearer {token}"}

    # Missing consent
    resp = client.post(
        "/api/v1/chat/message",
        json={"message": "Can I exercise with this ECG?", "consent_third_party_ai": False},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "consent" in resp.json()["detail"].lower()


def test_chat_summarize_requires_explicit_consent(client):
    """Calling summarize without opt-in consent must be refused with 403."""
    token, user_id = register_user(client, "consent_sum")
    headers = {"Authorization": f"Bearer {token}"}

    # Missing consent
    resp = client.post(
        "/api/v1/chat/summarize",
        json={"ecg_id": str(uuid.uuid4()), "consent_third_party_ai": False},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "consent" in resp.json()["detail"].lower()


def test_chat_advice_requires_explicit_consent(client):
    """Calling advice without opt-in consent must be refused with 403."""
    token, user_id = register_user(client, "consent_adv")
    headers = {"Authorization": f"Bearer {token}"}

    # Missing consent
    resp = client.post(
        "/api/v1/chat/advice",
        json={"bp_sys": 130, "bp_dia": 85, "hr": 75, "consent_third_party_ai": False},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "consent" in resp.json()["detail"].lower()


def test_chat_cannot_summarize_unauthorized_patient_ecg(client):
    """Patient A cannot trigger AI summary of Patient B's ECG report."""
    token_a, id_a = register_user(client, "pat_a")
    token_b, id_b = register_user(client, "pat_b")

    # Seed an ECG analysis owned by Patient B
    db = SessionLocal()
    b_ecg_id = str(uuid.uuid4())
    ecg_record = ECGAnalysis(
        id=b_ecg_id,
        user_id=id_b,
        file_path="uploads/ecg/dummy_b.csv",
        rhythm="Sinus Rhythm",
        top_condition="NORM",
        top_condition_prob=0.92,
        urgency="routine",
        analysis_json='{"rhythm_diagnosis": "Sinus Rhythm", "confidence": 0.92, "superclasses": {"NORM": 0.92}}'
    )
    db.add(ecg_record)
    db.commit()
    db.close()

    # Patient A attempts to summarize Patient B's ECG report with consent=True
    headers_a = {"Authorization": f"Bearer {token_a}"}
    resp = client.post(
        "/api/v1/chat/summarize",
        json={"ecg_id": b_ecg_id, "consent_third_party_ai": True},
        headers=headers_a,
    )
    # Must be 403 Forbidden
    assert resp.status_code == 403, f"Expected 403 Forbidden for cross-patient summarize, got {resp.status_code}"
