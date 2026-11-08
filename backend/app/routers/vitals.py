"""
Vitals API Router
------------------
POST /api/v1/vitals        — Log vitals, run LightGBM risk model, return SHAP.
GET  /api/v1/vitals/history — 30-day vitals history with trend analysis.
GET  /api/v1/user/profile  — Get user profile.
PUT  /api/v1/user/profile  — Update user profile.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import VitalsLog, User, AccessAuditLog
from ..schemas import VitalsIn, VitalsOut, UserProfileIn, UserProfileOut
from ..auth import get_current_user, verify_patient_access
from ..ml.risk_model import RiskModel
from ..ml.vitals_validator import VitalsValidator
from ..ml.risk_auditor import RiskAuditor

router = APIRouter(prefix="/api/v1", tags=["vitals"])

# Singleton model instance (loaded once at startup)
_risk_model: Optional[RiskModel] = None
_vitals_validator: Optional[VitalsValidator] = None
_risk_auditor: Optional[RiskAuditor] = None


def get_risk_model() -> RiskModel:
    global _risk_model
    if _risk_model is None:
        possible_paths = [
            "backend/models_saved/risk_model.pkl",
            "models_saved/risk_model.pkl",
            os.path.join(os.path.dirname(__file__), "..", "..", "models_saved", "risk_model.pkl"),
            os.path.join(os.getcwd(), "backend", "models_saved", "risk_model.pkl"),
            os.path.join(os.getcwd(), "models_saved", "risk_model.pkl"),
        ]
        chosen = next((p for p in possible_paths if os.path.exists(p)), "models_saved/risk_model.pkl")
        _risk_model = RiskModel(model_path=chosen)
    return _risk_model


def get_vitals_validator() -> VitalsValidator:
    global _vitals_validator
    if _vitals_validator is None:
        _vitals_validator = VitalsValidator()
    return _vitals_validator


def get_risk_auditor() -> RiskAuditor:
    global _risk_auditor
    if _risk_auditor is None:
        _risk_auditor = RiskAuditor()
    return _risk_auditor


# ─────────────────────────────────────────────────────────
# User Profile Endpoints
# ─────────────────────────────────────────────────────────

@router.get("/user/profile")
async def get_profile(
    user_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve profile and clinical demographics with strict authentication and grant checks."""
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db)

    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "age": user.age,
        "sex": user.sex,
        "is_smoker": user.is_smoker,
        "is_diabetic": user.is_diabetic,
        "has_family_history": user.has_family_history,
        "height_cm": user.height_cm,
    }


@router.put("/user/profile")
async def update_profile(
    profile: UserProfileIn,
    user_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile and demographics for current user or granted patient."""
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db)

    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        user = User(id=target_id)
        db.add(user)

    allowed_fields = {"name", "age", "sex", "is_smoker", "is_diabetic", "has_family_history", "height_cm"}
    for key, value in profile.model_dump().items():
        if key in allowed_fields and hasattr(user, key):
            setattr(user, key, value)

    user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Profile updated", "user_id": target_id}


# ─────────────────────────────────────────────────────────
# Vitals Endpoints
# ─────────────────────────────────────────────────────────

@router.post("/vitals")
async def log_vitals(
    vitals: VitalsIn,
    user_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Log vitals → run LightGBM + Framingham risk model → return SHAP explanation.
    Strictly authenticated: logged to current user or explicitly granted patient.
    """
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db)

    # Get user
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        user = User(id=target_id, name="User", age=45, sex="Male")
        db.add(user)
        db.commit()

    profile = {
        "age": user.age,
        "sex": user.sex,
        "is_smoker": user.is_smoker,
        "is_diabetic": user.is_diabetic,
        "has_family_history": user.has_family_history,
    }

    vitals_dict = vitals.model_dump()

    # 1. Validate Inputs (Clinical Data Correction AI)
    validator = get_vitals_validator()
    # Add height from profile for BMI calculation
    val_input = {**vitals_dict, "height_cm": user.height_cm}
    validation_report = validator.validate(val_input)

    if validation_report["status"] == "invalid":
        raise HTTPException(status_code=400, detail={
            "error": "Physiologically impossible vitals detected.",
            "issues": validation_report["issues"]
        })

    # Run ML risk model
    try:
        model = get_risk_model()
        risk_result = model.predict(vitals_dict, profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk model inference failed: {str(e)}")

    # 3. Clinical Audit (Expert Review AI)
    auditor = get_risk_auditor()
    audit_report = auditor.audit(vitals_dict, profile, risk_result)

    # Compute trend_delta from previous reading
    previous = (
        db.query(VitalsLog)
        .filter(VitalsLog.user_id == target_id)
        .order_by(VitalsLog.timestamp.desc())
        .first()
    )

    if previous:
        risk_result["trend_delta"] = round(risk_result["risk_score"] - previous.risk_score, 2)

    # Persist to database
    record = VitalsLog(
        id=str(uuid.uuid4()),
        user_id=target_id,
        bp_sys=vitals.bp_sys,
        bp_dia=vitals.bp_dia,
        hr=vitals.hr,
        weight=vitals.weight,
        spo2=vitals.spo2,
        glucose=vitals.glucose,
        cholesterol=vitals.cholesterol,
        risk_score=risk_result["risk_score"],
        risk_tier=risk_result["risk_tier"],
        lgbm_probability=risk_result["lgbm_probability"],
        framingham_risk=risk_result["framingham_risk"],
        shap_json=str(risk_result["shap_top5"]),
        ecg_prompt=risk_result["ecg_prompt"],
        timestamp=datetime.utcnow(),
    )
    db.add(record)
    db.commit()

    return {
        **risk_result,
        "id": record.id,
        "vitals": vitals_dict,
        "validation_report": validation_report,
        "clinical_audit": audit_report,
        "timestamp": record.timestamp.isoformat(),
    }


@router.get("/vitals/history")
async def get_vitals_history(
    request: Request,
    user_id: Optional[str] = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get vitals history for the last N days with strict authentication and clinician grant checks."""
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db, request=request)

    since = datetime.utcnow() - timedelta(days=days)

    records = (
        db.query(VitalsLog)
        .filter(VitalsLog.user_id == target_id, VitalsLog.timestamp >= since)
        .order_by(VitalsLog.timestamp.desc())
        .all()
    )

    history = [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "bp_sys": r.bp_sys,
            "bp_dia": r.bp_dia,
            "hr": r.hr,
            "weight": r.weight,
            "spo2": r.spo2,
            "glucose": r.glucose,
            "cholesterol": r.cholesterol,
            "risk_score": r.risk_score,
            "risk_tier": r.risk_tier,
        }
        for r in records
    ]

    # Trend: compare last 7 days vs prior 7 days
    recent = [r.bp_sys for r in records[:7]] if records else []
    older = [r.bp_sys for r in records[7:14]] if len(records) > 7 else []
    bp_trend = (sum(recent) / len(recent) - sum(older) / len(older)) if recent and older else 0.0

    risk_history = [
        {"timestamp": r.timestamp.isoformat(), "risk_score": r.risk_score, "risk_tier": r.risk_tier}
        for r in records
    ]

    return {
        "records": history,
        "count": len(history),
        "trend": {"bp_sys_trend": round(bp_trend, 1)},
        "risk_history": risk_history,
    }


@router.get("/user/access-log")
async def get_patient_access_log(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns audit log of all access events to the current patient's records
    by clinicians or other authorized users.
    Contains zero health data.
    """
    logs = (
        db.query(AccessAuditLog)
        .filter(AccessAuditLog.patient_user_id == current_user.id)
        .order_by(AccessAuditLog.timestamp.desc())
        .all()
    )
    return [
        {
            "id": l.id,
            "accessor_user_id": l.accessor_user_id,
            "accessor_email": l.accessor_email,
            "patient_user_id": l.patient_user_id,
            "endpoint": l.endpoint,
            "timestamp": l.timestamp.isoformat(),
            "ip_address": l.ip_address,
        }
        for l in logs
    ]
