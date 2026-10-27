"""
Sarvam AI Chat & Report Router
--------------------------------
POST /api/v1/chat/message       — Patient Q&A chat (with optional ECG context)
POST /api/v1/chat/summarize     — Generate plain-language ECG report summary
POST /api/v1/chat/advice        — Generate personalised lifestyle advice from vitals
GET  /api/v1/chat/health        — Check Sarvam AI availability
"""
import os
import json
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import ECGAnalysis, User, UserConsent
from ..auth import get_current_user, verify_patient_access
from ..ml.sarvam_assistant import get_sarvam_assistant

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Patient's message")
    ecg_id: Optional[str] = Field(None, description="ECG session ID to inject as context")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Prior conversation turns")
    consent_third_party_ai: Optional[bool] = Field(
        None,
        description="Optional client-side consent flag; server-side stored consent is authoritative."
    )


class ChatResponse(BaseModel):
    reply: str
    is_emergency: bool
    emergency_notice: Optional[str] = None


class SummarizeRequest(BaseModel):
    ecg_id: str = Field(..., description="ECG session ID to summarize")
    language: str = Field(
        default="en",
        pattern="^(en|hi|en-hi)$",
        description="Response language: 'en', 'hi', or 'en-hi' (bilingual)",
    )
    consent_third_party_ai: Optional[bool] = Field(
        None,
        description="Optional client-side consent flag; server-side stored consent is authoritative."
    )


class SummarizeResponse(BaseModel):
    summary_en: str
    summary_hi: str
    key_points: List[str]
    next_step: str


class AdviceRequest(BaseModel):
    bp_sys: Optional[int] = Field(None, description="Systolic BP mmHg")
    bp_dia: Optional[int] = Field(None, description="Diastolic BP mmHg")
    hr: Optional[int] = Field(None, description="Heart rate bpm")
    spo2: Optional[float] = Field(None, description="SpO2 %")
    glucose: Optional[float] = Field(None, description="Glucose mg/dL")
    cholesterol: Optional[float] = Field(None, description="Cholesterol mg/dL")
    weight: Optional[float] = Field(None, description="Weight kg")
    risk_tier: str = Field(default="Borderline", description="Low | Borderline | Elevated")
    ecg_urgency: Optional[str] = Field(None, description="routine | see_doctor_today | emergency")
    consent_third_party_ai: Optional[bool] = Field(
        None,
        description="Optional client-side consent flag; server-side stored consent is authoritative."
    )


class AdviceResponse(BaseModel):
    advice: str
    do_list: List[str]
    avoid_list: List[str]
    follow_up: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_verified_ecg_analysis(ecg_id: str, current_user: User, db: Session) -> Optional[dict]:
    """Load a stored ECG analysis dict, strictly enforcing ownership or clinician access."""
    record = db.query(ECGAnalysis).filter(ECGAnalysis.id == ecg_id).first()
    if not record:
        return None
    verify_patient_access(current_user=current_user, patient_id=record.user_id, db=db)
    if record.analysis_json:
        return json.loads(record.analysis_json)
    return None


def check_server_side_consent(user_id: str, db: Session, client_flag: Optional[bool] = None) -> None:
    """
    Checks stored server-side consent record in the database.
    Rejects with 403 Forbidden if consent is missing, revoked, or client explicitly opted out.
    """
    if client_flag is False:
        raise HTTPException(
            status_code=403,
            detail="Third-party AI processing disabled: request explicitly opted out via consent flag.",
        )

    latest = (
        db.query(UserConsent)
        .filter(UserConsent.user_id == user_id, UserConsent.consent_type == "third_party_ai")
        .order_by(UserConsent.timestamp.desc())
        .first()
    )
    if not latest or not latest.granted:
        raise HTTPException(
            status_code=403,
            detail=(
                "Third-party AI processing disabled: Server-side consent has not been granted or has been revoked. "
                "You must grant consent via /api/v1/consent/grant to use cloud assistant features."
            ),
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def chat_health():
    """Check whether Sarvam AI is configured and reachable (public status probe, no user data)."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        return {"status": "unavailable", "reason": "SARVAM_API_KEY not set"}
    return {
        "status": "available",
        "model": "sarvam-m",
        "provider": "Sarvam AI",
        "base_url": "https://api.sarvam.ai/v1",
    }


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Patient Q&A — ask anything about cardiac health.
    Strictly authenticated.
    Requires server-side stored consent before transmitting de-identified queries to Sarvam AI.
    """
    check_server_side_consent(current_user.id, db, req.consent_third_party_ai)

    # Load verified ECG context if requested (Access control verified before external call)
    ecg_context = None
    if req.ecg_id:
        ecg_context = _fetch_verified_ecg_analysis(req.ecg_id, current_user, db)
        if ecg_context is None:
            raise HTTPException(
                status_code=404,
                detail=f"ECG session '{req.ecg_id}' not found.",
            )

    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Convert history to plain dicts (no identifying personal info)
    history = [{"role": m.role, "content": m.content} for m in (req.history or [])]

    result = assistant.patient_chat(
        user_message=req.message,
        ecg_context=ecg_context,
        chat_history=history,
    )

    emergency_notice = None
    if result["is_emergency"]:
        emergency_notice = (
            "🚨 This sounds like a medical emergency. "
            "Please call 112 (India) or go to the nearest emergency room immediately."
        )

    return ChatResponse(
        reply=result["reply"],
        is_emergency=result["is_emergency"],
        emergency_notice=emergency_notice,
    )


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_ecg(
    req: SummarizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a plain-language summary of an ECG report.
    Strictly authenticated and verified to patient record.
    Requires server-side stored consent.
    """
    check_server_side_consent(current_user.id, db, req.consent_third_party_ai)

    # Access control verification before external API assistant initialization
    ecg_analysis = _fetch_verified_ecg_analysis(req.ecg_id, current_user, db)
    if ecg_analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"ECG session '{req.ecg_id}' not found.",
        )

    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Only anonymized clinical metrics are sent to Sarvam AI (no name, email, IP, user_id)
    result = assistant.summarize_report(ecg_analysis, language=req.language)

    return SummarizeResponse(
        summary_en=result.get("summary_en", ""),
        summary_hi=result.get("summary_hi", ""),
        key_points=result.get("key_points", []),
        next_step=result.get("next_step", "Consult your cardiologist."),
    )


@router.post("/advice", response_model=AdviceResponse)
async def get_advice(
    req: AdviceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate personalised cardiac lifestyle advice based on patient vitals and risk tier.
    Strictly authenticated and requires server-side stored consent.
    """
    check_server_side_consent(current_user.id, db, req.consent_third_party_ai)

    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    vitals = {
        "bp_sys": req.bp_sys,
        "bp_dia": req.bp_dia,
        "hr": req.hr,
        "spo2": req.spo2,
        "glucose": req.glucose,
        "cholesterol": req.cholesterol,
        "weight": req.weight,
    }

    result = assistant.generate_advice(
        vitals=vitals,
        risk_tier=req.risk_tier,
        ecg_urgency=req.ecg_urgency,
    )

    return AdviceResponse(
        advice=result.get("advice", ""),
        do_list=result.get("do_list", []),
        avoid_list=result.get("avoid_list", []),
        follow_up=result.get("follow_up", "Consult your cardiologist."),
    )
