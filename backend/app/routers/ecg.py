"""
ECG Upload & Analysis Router
------------------------------
POST /api/v1/ecg/upload   — Upload ECG image → Gemini Vision analysis.
GET  /api/v1/ecg/history  — Get ECG session history.
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
from ..models_db import ECGAnalysis
from ..ml.ecg_analyzer import ECGAnalyzer

router = APIRouter(prefix="/api/v1/ecg", tags=["ecg"])

UPLOAD_DIR = "uploads/ecg"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/webp", "application/pdf",
}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

def get_ecg_analyzer() -> ECGAnalyzer:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    return ECGAnalyzer(api_key=api_key)


@router.post("/upload")
async def upload_ecg(
    file: UploadFile = File(...),
    user_id: str = Form(default="default_user"),
    age: int = Form(default=50),
    sex: str = Form(default="Male"),
    conditions: str = Form(default=""),
    bp_sys: Optional[int] = Form(default=None),
    hr: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Upload ECG image/PDF → analyze with Gemini 2.0 Flash Vision → return structured report.
    All analysis is REAL — no mock data.
    """
    # ── Validate file type
    content_type = file.content_type or "image/jpeg"
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{content_type}'. Accepted: JPG, PNG, WebP, PDF.",
        )

    # ── Read file bytes
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")
    if len(content) < 1024:
        raise HTTPException(status_code=422, detail="File too small — appears to be empty or corrupt.")

    # ── Save to disk
    ecg_id = str(uuid.uuid4())
    ext = (file.filename or "ecg.jpg").split(".")[-1].lower()
    filename = f"{ecg_id}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    # ── Patient context for Gemini prompt
    patient_context = {
        "age": age,
        "sex": sex,
        "conditions": conditions,
        "bp_sys": bp_sys,
        "hr": hr,
    }

    # ── Run real Gemini Vision analysis
    try:
        analyzer = get_ecg_analyzer()
        result = analyzer.analyze_ecg(content, patient_context, content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ECG analysis failed: {str(e)}")

    # ── Determine top condition
    top_cond = None
    top_prob = 0.0
    for c in result.get("conditions", []):
        if float(c.get("probability", 0)) > top_prob:
            top_prob = float(c.get("probability", 0))
            top_cond = c.get("name")

    # ── Persist to database
    record = ECGAnalysis(
        id=ecg_id,
        user_id=user_id,
        file_path=filepath,
        file_name=file.filename,
        urgency=result.get("urgency", "see_doctor_today"),
        heart_rate_bpm=result.get("heart_rate_bpm"),
        rhythm=result.get("rhythm"),
        qtc_ms=result.get("qtc_ms"),
        image_quality=result.get("image_quality", "fair"),
        top_condition=top_cond,
        top_condition_prob=top_prob,
        analysis_json=json.dumps(result),
        timestamp=datetime.utcnow(),
    )
    db.add(record)
    db.commit()

    # Add ecg_id to result
    result["ecg_id"] = ecg_id
    result["file_url"] = f"/uploads/ecg/{filename}"
    return result


@router.get("/history")
async def get_ecg_history(
    user_id: str = "default_user",
    db: Session = Depends(get_db),
):
    """Get all ECG sessions for a user, ordered by most recent."""
    records = (
        db.query(ECGAnalysis)
        .filter(ECGAnalysis.user_id == user_id)
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
            "file_url": f"/uploads/ecg/{r.id}.{(r.file_name or 'ecg.jpg').split('.')[-1]}",
            "file_name": r.file_name,
        }
        for r in records
    ]
    return {"ecg_sessions": sessions, "total": len(sessions)}


@router.get("/{ecg_id}")
async def get_ecg_analysis(
    ecg_id: str,
    db: Session = Depends(get_db),
):
    """Get full analysis for a specific ECG session."""
    record = db.query(ECGAnalysis).filter(ECGAnalysis.id == ecg_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ECG session not found.")

    result = json.loads(record.analysis_json) if record.analysis_json else {}
    result["ecg_id"] = record.id
    return result
