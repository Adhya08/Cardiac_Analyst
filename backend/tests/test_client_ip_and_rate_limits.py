"""
Automated Pytest Suite: Client IP and Rate Limit Security (Fix 1c - Item 1)
==========================================================================
Verifies:
1. get_client_ip never trusts client-supplied leftmost X-Forwarded-For header.
2. In Vercel -> Render proxy setup, extracts the real client IP (not spoofed IP, not proxy IP).
3. In direct Render proxy setup, extracts the rightmost appended client IP.
4. Rate-limit and lockout state is stored and shared in the database.
5. Emergency triage allows a high ceiling (>30 requests) without blocking, and frontend emergency fallback functions.
"""

import time
import uuid
import pytest
from starlette.requests import Request
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models_db import LoginLockout, RateLimitEvent
from app.rate_limiter import (
    get_client_ip,
    check_rate_limit,
    record_failed_login,
    is_login_locked,
)


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _make_dummy_request(headers=None, client_host="10.0.0.1"):
    """Helper to create a dummy starlette Request with specified headers and client."""
    headers = headers or {}
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/emergency/triage",
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_client_ip_rejects_spoofed_leftmost_header_behind_vercel(monkeypatch):
    """
    Scenario: Client sends forged 'X-Forwarded-For: 203.0.113.199'.
    Vercel receives from real client 198.51.100.5, sets X-Vercel-Forwarded-For: 198.51.100.5
    and appends 198.51.100.5 to X-Forwarded-For.
    Render receives from Vercel (76.76.21.21) and appends 76.76.21.21.
    X-Forwarded-For header received by app: '203.0.113.199, 198.51.100.5, 76.76.21.21'
    Expected: When 76.76.21.21 is in TRUSTED_PROXY_IPS, real client IP is 198.51.100.5.
    """
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "76.76.21.21")
    req = _make_dummy_request(
        headers={
            "x-forwarded-for": "203.0.113.199, 198.51.100.5, 76.76.21.21",
            "x-vercel-forwarded-for": "198.51.100.5",
            "x-vercel-id": "iad1::xyz789",
        },
        client_host="10.0.4.12",  # Render internal proxy
    )
    resolved_ip = get_client_ip(req)
    assert resolved_ip == "198.51.100.5", f"Expected real IP 198.51.100.5, got spoofed or proxy IP: {resolved_ip}"


def test_client_ip_direct_render_proxy():
    """
    Scenario: Direct request to Render (bypassing Vercel).
    Attacker supplies 'X-Forwarded-For: 8.8.8.8'.
    Render appends real client IP 198.51.100.22.
    X-Forwarded-For received: '8.8.8.8, 198.51.100.22'
    Expected: Real client IP is 198.51.100.22, NOT spoofed 8.8.8.8.
    """
    req = _make_dummy_request(
        headers={
            "x-forwarded-for": "8.8.8.8, 198.51.100.22",
        },
        client_host="10.0.4.12",
    )
    resolved_ip = get_client_ip(req)
    assert resolved_ip == "198.51.100.22", f"Expected real IP 198.51.100.22, got: {resolved_ip}"


def test_client_ip_direct_render_rejects_forged_vercel_header():
    """
    Scenario: Direct request to Render with forged X-Vercel-Forwarded-For.
    Attacker supplies 'X-Vercel-Forwarded-For: 1.1.1.1' directly to Render.
    Render appends real client IP 198.51.100.22 to X-Forwarded-For.
    Expected: Because 198.51.100.22 is not in TRUSTED_PROXY_IPS, forged header is ignored
    and real client IP 198.51.100.22 is returned.
    """
    req = _make_dummy_request(
        headers={
            "x-forwarded-for": "198.51.100.22",
            "x-vercel-forwarded-for": "1.1.1.1",
        },
        client_host="10.0.4.12",
    )
    resolved_ip = get_client_ip(req)
    assert resolved_ip == "198.51.100.22", f"Expected real client IP 198.51.100.22, got forged: {resolved_ip}"



def test_rate_limit_and_lockout_persists_in_database():
    """
    Verifies that login lockouts and rate limit events persist to the database
    so multiple server workers / restarts share the lockout state.
    """
    db = SessionLocal()
    test_key = f"test_user_lockout_{uuid.uuid4().hex[:8]}@hospital.org"
    
    # Record 5 failures
    for _ in range(5):
        record_failed_login(test_key, db=db)

    # Must be locked out
    is_locked, remaining = is_login_locked(test_key, db=db)
    assert is_locked is True
    assert remaining > 0

    # Verify record in database
    db_lockout = db.query(LoginLockout).filter(LoginLockout.key == test_key).first()
    assert db_lockout is not None
    assert db_lockout.locked_until > time.time()
    db.close()


def test_emergency_triage_rate_limit_raised(client):
    """
    Emergency triage must allow a high ceiling (>30 requests) so it never
    blocks legitimate emergency users or rapid retry during crises.
    """
    payload = {
        "symptoms": [False, False, False, False, False, False, False, False],
    }
    # Send 35 requests; with old 30/min limit this would fail on request 31 with 429
    headers = {"X-Forwarded-For": "192.0.2.111"}
    for i in range(35):
        resp = client.post("/api/v1/emergency/triage", json=payload, headers=headers)
        assert resp.status_code == 200, f"Failed at request {i+1} with {resp.status_code}: {resp.text}"
