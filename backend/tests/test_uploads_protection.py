"""
Test Protection of /uploads directory
--------------------------------------
Asserts that files under /uploads are NOT served publicly over HTTP without authentication.
"""
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_uploads_not_served_statically_without_auth(client):
    """
    Attempting to directly request /uploads/ecg/... must NOT return the file (404/401).
    Public static directory mounting must be disabled.
    """
    # Create a dummy test file in uploads/ecg
    os.makedirs("uploads/ecg", exist_ok=True)
    test_filepath = os.path.join("uploads", "ecg", "sensitive_patient_ecg_test.csv")
    with open(test_filepath, "w", encoding="utf-8") as f:
        f.write("0.1,0.2,0.3,sensitive_patient_data\n")

    try:
        res = client.get("/uploads/ecg/sensitive_patient_ecg_test.csv")
        # In old code: static mount served this with status 200 OK!
        # In new secured code: static mount is removed, returning 404 (or 401).
        assert res.status_code in (404, 401), f"Expected 404 or 401, but got {res.status_code} (file leaked publicly!)"
    finally:
        if os.path.exists(test_filepath):
            os.remove(test_filepath)
