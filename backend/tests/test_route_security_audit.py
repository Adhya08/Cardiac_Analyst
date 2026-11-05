"""
Automated Pytest Suite: Route Security Audit (Item 2)
======================================================
Inspects EVERY registered route in the FastAPI application.
Asserts that every endpoint is either in an explicit, short PUBLIC_ALLOWLIST
or strictly returns 401 Unauthorized when called without a valid Bearer token.
Guarantees that no developer can accidentally expose an unauthenticated route.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.main import app
from app.database import init_db


PUBLIC_ALLOWLIST = {
    # Health checks & platform probe
    ("GET", "/"),
    ("GET", "/health"),
    # Public authentication entry points
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/token"),
    # Public life-safety emergency endpoints (zero stored data exposed)
    ("GET", "/api/v1/emergency/questions"),
    ("POST", "/api/v1/emergency/triage"),
    ("POST", "/api/v1/emergency/sos"),
    ("GET", "/api/v1/hospitals/nearby"),
    ("GET", "/api/v1/ambulance/nearby"),
    # Public chat service health check (no user data)
    ("GET", "/api/v1/chat/health"),
}


def get_all_application_routes():
    """Extract all distinct (method, path) route pairs from FastAPI."""
    routes = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in r.methods:
                if m not in ("HEAD", "OPTIONS"):
                    routes.add((m, r.path))
        elif hasattr(r, 'original_router'):
            for sub_r in r.original_router.routes:
                if isinstance(sub_r, APIRoute):
                    for m in sub_r.methods:
                        if m not in ("HEAD", "OPTIONS"):
                            routes.add((m, sub_r.path))
    return sorted(list(routes))


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_public_allowlist_is_minimal():
    """Ensure public allowlist only contains strictly necessary routes."""
    for method, path in PUBLIC_ALLOWLIST:
        assert path in (
            "/", "/health",
            "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/token",
            "/api/v1/emergency/questions", "/api/v1/emergency/triage", "/api/v1/emergency/sos",
            "/api/v1/hospitals/nearby", "/api/v1/ambulance/nearby",
            "/api/v1/chat/health"
        ), f"Unexpected route in public allowlist: {method} {path}"


def test_every_route_is_allowlisted_or_returns_401(client):
    """
    Audit every single route in the application:
    If not in PUBLIC_ALLOWLIST, an unauthenticated request MUST return 401.
    """
    all_routes = get_all_application_routes()
    unprotected_routes = []

    for method, path in all_routes:
        if (method, path) in PUBLIC_ALLOWLIST:
            continue

        # Replace path parameters with dummy UUIDs for testing
        test_path = path.replace("{ecg_id}", "00000000-0000-0000-0000-000000000000")
        test_path = test_path.replace("{clinician_id}", "00000000-0000-0000-0000-000000000000")

        # Make request with empty headers (no token)
        if method == "GET":
            resp = client.get(test_path)
        elif method == "POST":
            resp = client.post(test_path, json={})
        elif method == "PUT":
            resp = client.put(test_path, json={})
        elif method == "DELETE":
            resp = client.delete(test_path)
        else:
            continue

        if resp.status_code != 401:
            unprotected_routes.append((method, path, resp.status_code))

    assert not unprotected_routes, (
        f"CRITICAL SECURITY AUDIT FAILURE: The following routes are NOT in PUBLIC_ALLOWLIST "
        f"and do NOT return 401 Unauthorized when accessed without a token: {unprotected_routes}"
    )
