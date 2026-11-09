"""
SQLAlchemy ORM Models — Database table definitions.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, LargeBinary
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="patient")  # "patient" | "clinician" | "admin"
    invite_code = Column(String(32), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    name = Column(String, default="User")
    age = Column(Integer, default=45)
    sex = Column(String, default="Male")
    is_smoker = Column(Boolean, default=False)
    is_diabetic = Column(Boolean, default=False)
    has_family_history = Column(Boolean, default=False)
    height_cm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VitalsLog(Base):
    __tablename__ = "vitals_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, default="default_user", index=True)
    bp_sys = Column(Integer, nullable=False)
    bp_dia = Column(Integer, nullable=False)
    hr = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    spo2 = Column(Float, nullable=False)
    glucose = Column(Float, nullable=True)
    cholesterol = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=False)
    risk_tier = Column(String, nullable=False)
    lgbm_probability = Column(Float, nullable=True)
    framingham_risk = Column(Float, nullable=True)
    shap_json = Column(Text, nullable=True)
    ecg_prompt = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class ECGAnalysis(Base):
    __tablename__ = "ecg_analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, default="default_user", index=True)
    file_path = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_data = Column(LargeBinary, nullable=True)  # Raw digital ECG signal bytes stored in DB
    urgency = Column(String, default="see_doctor_today")
    heart_rate_bpm = Column(Integer, nullable=True)
    rhythm = Column(String, nullable=True)
    qtc_ms = Column(Integer, nullable=True)
    image_quality = Column(String, nullable=True)
    top_condition = Column(String, nullable=True)
    top_condition_prob = Column(Float, nullable=True)
    analysis_json = Column(Text, nullable=True)  # Full JSON stored here
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class TriageEvent(Base):
    __tablename__ = "triage_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, default="default_user", index=True)
    symptoms_json = Column(Text, nullable=True)
    severity = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class PatientClinicianGrant(Base):
    __tablename__ = "patient_clinician_grants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, index=True, nullable=False)
    clinician_id = Column(String, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RateLimitEvent(Base):
    """Persistent sliding-window rate limit event tracking."""
    __tablename__ = "rate_limit_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(128), index=True, nullable=False)  # e.g., "scope:client_ip"
    scope = Column(String(32), index=True, nullable=False)
    timestamp = Column(Float, index=True, nullable=False)


class LoginLockout(Base):
    """Persistent brute-force login lockout state."""
    __tablename__ = "login_lockouts"

    key = Column(String(128), primary_key=True)  # client IP or normalized email
    locked_until = Column(Float, nullable=False)
    failure_count = Column(Integer, default=0)
    last_failure_at = Column(Float, nullable=False)


class UserConsent(Base):
    """Persistent server-side user consent tracking."""
    __tablename__ = "user_consents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    consent_type = Column(String(64), index=True, nullable=False)  # e.g., "third_party_ai"
    granted = Column(Boolean, default=False, nullable=False)
    policy_version = Column(String(32), default="v1.0", nullable=False)
    ip_address = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class AccessAuditLog(Base):
    """
    HIPAA-compliant health record access audit log.
    Records every access to patient data by someone other than the patient.
    Stores zero health data (no ECG signals, risk scores, or clinical symptoms).
    """
    __tablename__ = "access_audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    accessor_user_id = Column(String(64), index=True, nullable=False)
    accessor_email = Column(String(128), nullable=True)
    patient_user_id = Column(String(64), index=True, nullable=False)
    endpoint = Column(String(128), nullable=False)
    ip_address = Column(String(64), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


