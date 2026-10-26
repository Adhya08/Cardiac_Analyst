"""
ECG Upload & Analysis Router
------------------------------
POST /api/v1/ecg/upload   — Upload digital 12-lead ECG record (CSV, NPY, JSON) → Local ResNet1D analysis.
GET  /api/v1/ecg/history  — Get ECG session history.
GET  /api/v1/ecg/{ecg_id} — Get full analysis for a session.
"""
import os
import uuid
import json
from datetime import datetime
from typing import Optional

import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import ECGAnalysis, User
from ..schemas import ECGOut
from ..auth import get_current_user, verify_patient_access
from ..ml.ecg_analyzer import get_ecg_analyzer

router = APIRouter(prefix="/api/v1/ecg", tags=["ecg"])

UPLOAD_DIR = "uploads/ecg"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", response_model=ECGOut)
async def upload_ecg(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(default=None),
    age: int = Form(default=50),
    sex: str = Form(default="Male"),
    conditions: str = Form(default=""),
    bp_sys: Optional[int] = Form(default=None),
    hr: Optional[int] = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a digital 12-lead ECG record (CSV, NPY, JSON).
    Strictly authenticated: record saved for current user or granted patient.
    """
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db)
    filename_orig = file.filename or "ecg.csv"
    content_type = file.content_type or "text/csv"

    # ── Read file bytes
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")

    # ── Check empty file
    if len(content) == 0:
        analyzer = get_ecg_analyzer()
        err_res = analyzer._build_unavailable_response(
            reason="Uploaded file is completely empty (0 bytes).",
            quality="unusable"
        )
        return err_res

    # ── Save upload to disk
    ecg_id = str(uuid.uuid4())
    raw_ext = os.path.splitext(filename_orig)[1].lstrip(".").lower()
    allowed_exts = {"csv", "json", "npy", "txt"}
    ext = raw_ext if raw_ext in allowed_exts else "csv"
    saved_filename = f"{ecg_id}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, saved_filename)

    try:
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)
    except Exception as e:
        print(f"[Upload] Warning saving file to disk: {e}")

    # ── Patient Context
    patient_context = {
        "age": age,
        "sex": sex,
        "conditions": conditions,
        "bp_sys": bp_sys,
        "hr": hr,
    }

    # ── Execute Local Deterministic Inference via ECGAnalyzer
    analyzer = get_ecg_analyzer()
    result = analyzer.analyze_digital_ecg(
        file_bytes=content,
        filename=filename_orig,
        content_type=content_type,
        patient_context=patient_context
    )

    # ── Determine top condition (prefer abnormal if detected)
    top_cond = None
    top_score = 0.0
    for c in result.get("conditions", []):
        score = float(c.get("model_score", 0.0))
        if score > top_score and c.get("code") != "NORM":
            top_score = score
            top_cond = c.get("name")
    if top_cond is None and result.get("conditions"):
        top_cond = result["conditions"][0].get("name")
        top_score = float(result["conditions"][0].get("model_score", 0.0))

    result["ecg_id"] = ecg_id

    # ── Persist to Database
    try:
        record = ECGAnalysis(
            id=ecg_id,
            user_id=target_id,
            file_path=filepath,
            file_name=filename_orig,
            urgency=result.get("urgency", "routine"),
            heart_rate_bpm=result.get("heart_rate_bpm"),
            rhythm=result.get("rhythm"),
            qtc_ms=result.get("qtc_ms"),
            image_quality=result.get("quality_status", "fair"),
            top_condition=top_cond,
            top_condition_prob=top_score,
            analysis_json=json.dumps(result),
            timestamp=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Database] Warning persisting ECG record: {e}")
        result["ecg_id"] = None
        result["persistence_error"] = f"Failed to persist analysis to database: {str(e)}"

    return result


@router.get("/history")
async def get_ecg_history(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all ECG sessions for a user, ordered by most recent with strict authentication and grant checks."""
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db)

    records = (
        db.query(ECGAnalysis)
        .filter(ECGAnalysis.user_id == target_id)
        .order_by(ECGAnalysis.timestamp.desc())
        .all()
    )

    sessions = [
        {
            "ecg_id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "urgency": r.urgency,
            "heart_rate_bpm": r.heart_rate_bpm,
            "rhythm": r.rhythm,
            "qtc_ms": r.qtc_ms,
            "image_quality": r.image_quality,
            "top_condition": r.top_condition,
            "top_condition_prob": r.top_condition_prob,
            "file_name": r.file_name,
        }
        for r in records
    ]
    return {"ecg_sessions": sessions, "total": len(sessions)}


@router.get("/{ecg_id}", response_model=ECGOut)
async def get_ecg_analysis(
    ecg_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full analysis for a specific ECG session with strict authentication and grant checks."""
    record = db.query(ECGAnalysis).filter(ECGAnalysis.id == ecg_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ECG session not found.")

    verify_patient_access(current_user=current_user, patient_id=record.user_id, db=db)

    result = json.loads(record.analysis_json) if record.analysis_json else {}
    result["ecg_id"] = record.id
    if "status" not in result:
        result["status"] = "ok"
    if "quality_status" not in result:
        result["quality_status"] = record.image_quality or "good"
    if "model_scores" not in result:
        result["model_scores"] = {}
    return result
