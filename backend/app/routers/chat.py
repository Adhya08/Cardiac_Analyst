"""
Structured Report & Grounded Patient Explainer Router
-----------------------------------------------------
POST /api/v1/chat/message       — Patient Q&A chat (strictly grounded in verified ECG context)
POST /api/v1/chat/summarize     — Deterministic report generator + optional Groq patient explanation
POST /api/v1/chat/advice        — Evidence-based lifestyle and vitals guidance
GET  /api/v1/chat/health        — Report engine and AI provider health probe
"""
import os
import json
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import ECGAnalysis, User, UserConsent
from ..auth import get_current_user, verify_patient_access
from ..ml.report_generator import generate_deterministic_report, generate_deterministic_advice
from ..ml.groq_explainer import get_groq_explainer

logger = logging.getLogger("cardiac_analyst.chat")
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
    source: Optional[str] = "groq_chat"


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
    source: Optional[str] = "deterministic_engine"
    urgency: Optional[str] = "routine"
    is_emergency: Optional[bool] = False


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
    source: Optional[str] = "deterministic_engine"


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
    """Check report generator status and Groq AI availability."""
    groq = get_groq_explainer()
    return {
        "status": "available",
        "report_engine": "deterministic_structured_generator",
        "groq_status": "available" if groq.is_available else "offline_fallback_active",
        "model": groq.model if groq.is_available else "deterministic",
        "provider": "Groq API (Free Tier)" if groq.is_available else "Local Deterministic Engine",
    }


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Patient Q&A — grounded in verified ECG findings.
    Strictly authenticated. Verifies data subject (patient) consent prior to external transmission.
    """
    target_patient_id = current_user.id
    ecg_context = None

    if req.ecg_id:
        record = db.query(ECGAnalysis).filter(ECGAnalysis.id == req.ecg_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"ECG session '{req.ecg_id}' not found.")
        verify_patient_access(current_user=current_user, patient_id=record.user_id, db=db)
        target_patient_id = record.user_id
        if record.analysis_json:
            ecg_context = json.loads(record.analysis_json)

    check_server_side_consent(target_patient_id, db, req.consent_third_party_ai)

    groq = get_groq_explainer()
    history = [{"role": m.role, "content": m.content} for m in (req.history or [])]
    result = groq.explain_chat_message(
        message=req.message,
        ecg_analysis=ecg_context,
        chat_history=history,
    )

    emergency_notice = None
    if result.get("is_emergency"):
        emergency_notice = (
            "🚨 This sounds like a medical emergency. "
            "Please call 112 (India) or go to the nearest emergency room immediately."
        )

    return ChatResponse(
        reply=result["reply"],
        is_emergency=result.get("is_emergency", False),
        emergency_notice=emergency_notice,
        source=result.get("source", "groq_chat"),
    )


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_ecg(
    req: SummarizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a plain-language summary of an ECG report.
    - Requires authenticated access.
    - If the data subject (patient) granted consent and Groq is available, explains with anti-hallucination guardrails.
    - If patient has not consented to cloud transmission, or Groq is unconfigured/rate-limited,
      safely returns the 100% deterministic local structured report (zero external data flow).
    """
    # Explicit consent check upfront (raises 403 if caller opted out or lacks active server-side consent)
    check_server_side_consent(current_user.id, db, req.consent_third_party_ai)

    record = db.query(ECGAnalysis).filter(ECGAnalysis.id == req.ecg_id).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"ECG session '{req.ecg_id}' not found.",
        )
    verify_patient_access(current_user=current_user, patient_id=record.user_id, db=db)

    # If clinician is viewing a patient's record, verify that data subject (patient) also granted consent
    if record.user_id != current_user.id:
        check_server_side_consent(record.user_id, db, req.consent_third_party_ai)

    ecg_analysis = json.loads(record.analysis_json) if record.analysis_json else None
    if not ecg_analysis:
        raise HTTPException(
            status_code=404,
            detail=f"ECG analysis data for session '{req.ecg_id}' is empty.",
        )

    groq = get_groq_explainer()
    if groq.is_available:
        result = groq.explain_report(ecg_analysis, language=req.language)
    else:
        # 100% Deterministic structured report
        result = generate_deterministic_report(ecg_analysis, language=req.language)

    return SummarizeResponse(
        summary_en=result.get("summary_en", ""),
        summary_hi=result.get("summary_hi", ""),
        key_points=result.get("key_points", []),
        next_step=result.get("next_step", "Consult your cardiologist."),
        source=result.get("source", "deterministic_engine"),
        urgency=result.get("urgency", "routine"),
        is_emergency=result.get("is_emergency", False),
    )


@router.post("/advice", response_model=AdviceResponse)
async def get_advice(
    req: AdviceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate personalised cardiac lifestyle advice based on patient vitals and risk tier.
    Uses deterministic evidence-based rules with zero dependence on external LLMs.
    """
    check_server_side_consent(current_user.id, db, req.consent_third_party_ai)
    vitals = {
        "bp_sys": req.bp_sys,
        "bp_dia": req.bp_dia,
        "hr": req.hr,
        "spo2": req.spo2,
        "glucose": req.glucose,
        "cholesterol": req.cholesterol,
        "weight": req.weight,
    }

    result = generate_deterministic_advice(
        vitals=vitals,
        risk_tier=req.risk_tier,
        ecg_urgency=req.ecg_urgency,
    )

    return AdviceResponse(
        advice=result.get("advice", ""),
        do_list=result.get("do_list", []),
        avoid_list=result.get("avoid_list", []),
        follow_up=result.get("follow_up", "Consult your cardiologist."),
        source=result.get("source", "deterministic_engine"),
    )
