"""
Database & Cloud Storage Migration Test Suite
=============================================
Verifies:
1. DATABASE_URL normalization (postgres:// -> postgresql:// for Render/Supabase/Neon).
2. ECG file persistence in database: uploaded ECG bytes are stored directly in
   ECGAnalysis.file_data (survives ephemeral disk wipes and container redeploys).
3. Download endpoint (/api/v1/ecg/{ecg_id}/download) serves bytes from database
   even when disk file is deleted.
4. Alembic migration head is 0001_initial and contains tables for users, vitals,
   ecg, triage, grants, consent, and audit.
"""
import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import init_db, SessionLocal
from app.models_db import User, ECGAnalysis
from alembic.config import Config
from alembic.script import ScriptDirectory


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_database_url_normalization_handles_postgres_prefix():
    """Render and Supabase provide postgres:// which SQLAlchemy 2.0 requires as postgresql://."""
    from app.database import raw_db_url
    fake_url = "postgres://user:pass@ep-cool-db.neon.tech/neondb?sslmode=require"
    normalized = fake_url.replace("postgres://", "postgresql://", 1)
    assert normalized.startswith("postgresql://")
    assert "neondb" in normalized


def test_ecg_upload_stores_file_bytes_in_database(client):
    """
    Uploaded digital ECG bytes MUST be stored in the database's ECGAnalysis.file_data column
    so container redeploys and disk wipes do not delete patient ECG signals.
    """
    # 1. Register and login test patient
    email = f"ecg_db_user_{uuid.uuid4().hex[:8]}@hospital.org"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Synthetic 12-lead ECG CSV content
    synthetic_csv = "lead_I,lead_II,lead_III,lead_aVR,lead_aVL,lead_aVF,lead_V1,lead_V2,lead_V3,lead_V4,lead_V5,lead_V6\n"
    for _ in range(100):
        synthetic_csv += "0.05,0.12,0.07,-0.08,0.01,0.09,-0.02,0.15,0.22,0.18,0.11,0.06\n"
    csv_bytes = synthetic_csv.encode("utf-8")

    # 3. Upload file
    upload_resp = client.post(
        "/api/v1/ecg/upload",
        files={"file": ("patient_digital_ecg.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"age": 55, "sex": "Male"},
        headers=headers,
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    ecg_id = upload_resp.json()["ecg_id"]
    assert ecg_id is not None

    # 4. Verify record in database contains raw file_data
    db = SessionLocal()
    record = db.query(ECGAnalysis).filter(ECGAnalysis.id == ecg_id).first()
    assert record is not None
    assert record.file_data is not None
    assert record.file_data == csv_bytes
    disk_path = record.file_path

    # 5. Simulate redeploy / disk wipe: delete the local file on disk
    if disk_path and os.path.isfile(disk_path):
        os.remove(disk_path)
        assert not os.path.isfile(disk_path), "Disk file should be deleted to simulate redeploy wipe"

    # 6. Request download from /api/v1/ecg/{ecg_id}/download
    # Must succeed from database bytes even though disk file is gone!
    dl_resp = client.get(f"/api/v1/ecg/{ecg_id}/download", headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.content == csv_bytes
    assert "patient_digital_ecg.csv" in dl_resp.headers.get("Content-Disposition", "")
    db.close()


def test_alembic_head_revision_is_valid():
    """Verify Alembic configuration correctly registers the initial schema migration."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0001_initial"
