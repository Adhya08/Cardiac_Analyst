"""
Automated Pytest Suite: Server-Side Consent Management (Fix 1c - Item 2)
========================================================================
Verifies:
1. Client-supplied 'consent_third_party_ai: true' flag is NOT trusted alone.
   If no server-side consent is stored for the user, requests are rejected with 403.
2. Endpoint POST /api/v1/consent/grant stores persistent consent (type, granted=True, timestamp, policy_version).
3. Endpoint POST /api/v1/consent/revoke marks consent revoked (granted=False).
4. Revoking consent immediately blocks subsequent calls to /api/v1/chat/* with 403 Forbidden.
5. GET /api/v1/consent returns current user's consent status.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, SessionLocal


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


def test_chat_rejected_when_no_server_side_consent_even_if_client_claims_true(client):
    """
    Vulnerability check: In the old code, if client simply sent 'consent_third_party_ai: True',
    the backend trusted it without any server-side consent record.
    With server-side consent, this MUST be rejected with 403 Forbidden.
    """
    token, user_id = register_user(client, "no_server_consent")
    headers = {"Authorization": f"Bearer {token}"}

    # Client tries to bypass by sending consent_third_party_ai = True
    resp = client.post(
        "/api/v1/chat/message",
        json={"message": "Is my heart rate normal?", "consent_third_party_ai": True},
        headers=headers,
    )
    assert resp.status_code == 403, f"Expected 403 Forbidden without server consent, got {resp.status_code}: {resp.text}"
    assert "consent" in resp.json()["detail"].lower()


def test_grant_and_verify_server_side_consent(client):
    """Granting consent creates a persistent record with policy version and timestamp."""
    token, user_id = register_user(client, "grant_consent")
    headers = {"Authorization": f"Bearer {token}"}

    # Grant consent
    grant_resp = client.post(
        "/api/v1/consent/grant",
        json={"consent_type": "third_party_ai", "policy_version": "v1.1"},
        headers=headers,
    )
    assert grant_resp.status_code == 200, f"Expected 200 OK, got: {grant_resp.text}"
    grant_data = grant_resp.json()
    assert grant_data["granted"] is True
    assert grant_data["consent_type"] == "third_party_ai"
    assert grant_data["policy_version"] == "v1.1"

    # Query consent status
    status_resp = client.get("/api/v1/consent?consent_type=third_party_ai", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["granted"] is True


def test_revoke_consent_immediately_blocks_chat(client):
    """Revoking consent immediately revokes access to chat endpoints."""
    token, user_id = register_user(client, "revoke_consent")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Grant consent
    client.post(
        "/api/v1/consent/grant",
        json={"consent_type": "third_party_ai", "policy_version": "v1.0"},
        headers=headers,
    )

    # Verify status is granted
    st1 = client.get("/api/v1/consent?consent_type=third_party_ai", headers=headers)
    assert st1.json()["granted"] is True

    # 2. Revoke consent
    revoke_resp = client.post(
        "/api/v1/consent/revoke",
        json={"consent_type": "third_party_ai"},
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["granted"] is False

    # 3. Verify status is revoked
    st2 = client.get("/api/v1/consent?consent_type=third_party_ai", headers=headers)
    assert st2.json()["granted"] is False

    # 4. Attempting to chat must now return 403 Forbidden
    chat_resp = client.post(
        "/api/v1/chat/message",
        json={"message": "Can I jog today?"},
        headers=headers,
    )
    assert chat_resp.status_code == 403
    assert "revoked" in chat_resp.json()["detail"].lower() or "consent" in chat_resp.json()["detail"].lower()
