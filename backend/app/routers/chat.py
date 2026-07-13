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
from ..models_db import ECGAnalysis
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
    user_id: str = Field(default="default_user")


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


class AdviceResponse(BaseModel):
    advice: str
    do_list: List[str]
    avoid_list: List[str]
    follow_up: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_ecg_analysis(ecg_id: str, db: Session) -> Optional[dict]:
    """Load a stored ECG analysis dict by session ID."""
    record = db.query(ECGAnalysis).filter(ECGAnalysis.id == ecg_id).first()
    if record and record.analysis_json:
        return json.loads(record.analysis_json)
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def chat_health():
    """Check whether Sarvam AI is configured and reachable."""
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
    db: Session = Depends(get_db),
):
    """
    Patient Q&A — ask anything about your ECG or cardiac health.
    Optionally pass ecg_id to give the AI context of your latest ECG report.
    """
    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Load ECG context if requested
    ecg_context = None
    if req.ecg_id:
        ecg_context = _fetch_ecg_analysis(req.ecg_id, db)
        if ecg_context is None:
            raise HTTPException(
                status_code=404,
                detail=f"ECG session '{req.ecg_id}' not found.",
            )

    # Convert history to plain dicts
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
    db: Session = Depends(get_db),
):
    """
    Generate a plain-language, patient-friendly summary of an ECG report.
    Supports English, Hindi, and bilingual (en-hi) output.
    """
    try:
        assistant = get_sarvam_assistant()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    ecg_analysis = _fetch_ecg_analysis(req.ecg_id, db)
    if ecg_analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"ECG session '{req.ecg_id}' not found.",
        )

    result = assistant.summarize_report(ecg_analysis, language=req.language)

    return SummarizeResponse(
        summary_en=result.get("summary_en", ""),
        summary_hi=result.get("summary_hi", ""),
        key_points=result.get("key_points", []),
        next_step=result.get("next_step", "Consult your cardiologist."),
    )


@router.post("/advice", response_model=AdviceResponse)
async def get_advice(req: AdviceRequest):
    """
    Generate personalised cardiac lifestyle advice based on patient vitals and risk tier.
    """
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
