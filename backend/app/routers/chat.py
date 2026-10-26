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
from ..models_db import ECGAnalysis, User
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
    consent_third_party_ai: bool = Field(
        False,
        description="Explicit opt-in consent to transmit de-identified query to third-party AI (Sarvam AI)"
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
    consent_third_party_ai: bool = Field(
        False,
        description="Explicit opt-in consent to transmit de-identified ECG report to third-party AI"
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
    consent_third_party_ai: bool = Field(
        False,
        description="Explicit opt-in consent to transmit de-identified vitals metrics to third-party AI"
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
    Requires explicit user opt-in consent before transmitting de-identified queries to Sarvam AI.
    """
    if not req.consent_third_party_ai:
        raise HTTPException(
            status_code=403,
            detail=(
                "Third-party AI processing disabled without explicit patient consent. "
                "You must opt in by checking 'consent_third_party_ai' to consult the cloud assistant."
            ),
        )

    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Load verified ECG context if requested
    ecg_context = None
    if req.ecg_id:
        ecg_context = _fetch_verified_ecg_analysis(req.ecg_id, current_user, db)
        if ecg_context is None:
            raise HTTPException(
                status_code=404,
                detail=f"ECG session '{req.ecg_id}' not found.",
            )

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
    Requires explicit user opt-in consent.
    """
    if not req.consent_third_party_ai:
        raise HTTPException(
            status_code=403,
            detail=(
                "Third-party AI processing disabled without explicit patient consent. "
                "You must opt in by checking 'consent_third_party_ai' to generate an AI summary."
            ),
        )

    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    ecg_analysis = _fetch_verified_ecg_analysis(req.ecg_id, current_user, db)
    if ecg_analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"ECG session '{req.ecg_id}' not found.",
        )

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
):
    """
    Generate personalised cardiac lifestyle advice based on patient vitals and risk tier.
    Strictly authenticated and requires explicit opt-in consent.
    """
    if not req.consent_third_party_ai:
        raise HTTPException(
            status_code=403,
            detail=(
                "Third-party AI processing disabled without explicit patient consent. "
                "You must opt in by checking 'consent_third_party_ai' to receive AI lifestyle advice."
            ),
        )

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
