"""
Emergency Triage & Hospital Routing
--------------------------------------
POST /api/v1/emergency/triage   — Submit symptoms → triage + nearby hospitals.
GET  /api/v1/emergency/questions — Get triage questions.
"""
import math
import uuid
import os
import requests
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import TriageEvent, User
from ..schemas import TriageIn, TriageOut
from ..auth import get_current_user, get_optional_current_user, verify_patient_access
from ..rate_limiter import check_rate_limit
from ..ml.triage import assess_emergency, TRIAGE_QUESTIONS
from ..services.places_service import get_places_service

router = APIRouter(prefix="/api/v1/emergency", tags=["emergency"])


class SOSRequest(BaseModel):
    lat: Optional[float] = Field(None, description="Optional caller latitude")
    lon: Optional[float] = Field(None, description="Optional caller longitude")
    radius_km: Optional[float] = Field(default=10.0, ge=1.0, le=50.0, description="Search radius in kilometers")


def fetch_nearby_hospitals(lat: float, lon: float, radius_km: float = 10.0) -> List[dict]:
    """Fetch nearby cardiac hospitals using PlacesService with in-memory caching and offline fallback."""
    service = get_places_service()
    result = service.find_nearby_hospitals(lat=lat, lon=lon, radius_km=radius_km)
    return result.get("hospitals", [])


@router.get("/questions")
async def get_questions(request: Request):
    """Return the 8 triage questions with IP rate limiting."""
    check_rate_limit(request, limit=60, window_seconds=60, scope="emergency_questions")
    return {"questions": TRIAGE_QUESTIONS}


@router.post("/sos")
def emergency_sos(
    request: Request,
    payload: Optional[SOSRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Emergency SOS broadcast & hospital locator.
    Completely public, life-safety endpoint requiring zero login.
    Enforces IP rate limiting with high ceiling for life-safety.
    """
    check_rate_limit(request, limit=60, window_seconds=60, scope="emergency_sos", db=db)
    use_lat = payload.lat if (payload and payload.lat is not None) else 28.6139
    use_lon = payload.lon if (payload and payload.lon is not None) else 77.2090
    use_radius = payload.radius_km if (payload and payload.radius_km is not None) else 10.0
    try:
        hospitals = fetch_nearby_hospitals(use_lat, use_lon, radius_km=use_radius)
    except Exception as exc:
        hospitals = []

    return {
        "status": "emergency_active",
        "emergency_dispatch": False,
        "notice": "THIS API DOES NOT ALERT OR DISPATCH EMERGENCY SERVICES. Dial 112 or your local emergency number directly from your phone.",
        "emergency_hotlines": [
            {"service": "India National Emergency", "number": "112", "type": "universal"},
            {"service": "Ambulance Hotline", "number": "108", "type": "medical"},
            {"service": "Red Cross Emergency", "number": "1800-180-7676", "type": "helpline"},
        ],
        "instructions": [
            "🚨 Call 112 immediately from your phone. Do not delay.",
            "Sit or lie down in a comfortable position. Do NOT drive yourself.",
            "Unlock your front door so emergency responders can enter.",
            "Remain calm and rest quietly until paramedics arrive.",
        ],
        "hospitals": hospitals,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/triage")
def submit_triage(
    data: TriageIn,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Assess emergency severity using NICE CG95 and ACC/AHA rules,
    then fetch real nearby hospitals via Google Places API.
    Life-safety public access: works without login.
    If authenticated, links triage event to user; otherwise does NOT store in database.
    """
    check_rate_limit(request, limit=120, window_seconds=60, scope="emergency_triage", db=db)

    if len(data.symptoms) not in (8, 12):
        raise HTTPException(status_code=422, detail="Expected 8 or 12 symptom and risk factor answers.")

    # ── Clinical assessment
    assessment = assess_emergency(
        symptoms=data.symptoms,
        bp_sys=data.bp_sys,
        hr=data.hr,
    )

    # ── Real hospital lookup (optional enrichment; failsafe on timeout/error)
    hospitals = []
    if data.lat is not None and data.lon is not None:
        try:
            req_radius = data.radius_km if data.radius_km is not None else 10.0
            hospitals = fetch_nearby_hospitals(data.lat, data.lon, radius_km=req_radius)
        except Exception as exc:
            hospitals = []

    # ── Ambulance directory (always include govt services)
    ambulances = [
        {
            "service": "India Emergency (112)",
            "contact": "112",
            "type": "government",
            "eta_info": "Call for ETA — national emergency line",
            "maps_url": None,
            "notes": "National emergency number: connects to police, fire, and medical responders.",
        },
        {
            "service": "Government Ambulance (108)",
            "contact": "108",
            "type": "government",
            "eta_info": "Free ambulance — average 12-15 min urban",
            "maps_url": None,
            "notes": "Free ambulance service available in most Indian states.",
        },
        {
            "service": "Red Cross India",
            "contact": "1800-180-7676",
            "type": "government",
            "eta_info": "Medical emergency helpline",
            "maps_url": None,
            "notes": "Indian Red Cross Society — 24/7 helpline.",
        },
    ]

    triage_id = "unauthenticated"
    # ── Persist event only if caller is authenticated
    if current_user:
        target_id = data.user_id if data.user_id and data.user_id != "default_user" else current_user.id
        verify_patient_access(current_user=current_user, patient_id=target_id, db=db)
        event = TriageEvent(
            id=str(uuid.uuid4()),
            user_id=target_id,
            symptoms_json=str(data.symptoms),
            severity=assessment["severity"],
            confidence=assessment["confidence"],
            risk_score=assessment["risk_score"],
            lat=data.lat,
            lon=data.lon,
            timestamp=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        triage_id = event.id

    return {
        **assessment,
        "hospitals": hospitals,
        "ambulances": ambulances,
        "triage_id": triage_id,
    }


@router.get("/history")
def get_triage_history(
    request: Request,
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get triage history for user or granted patient with access audit logging."""
    target_id = user_id if user_id else current_user.id
    verify_patient_access(current_user=current_user, patient_id=target_id, db=db, request=request)

    events = (
        db.query(TriageEvent)
        .filter(TriageEvent.user_id == target_id)
        .order_by(TriageEvent.timestamp.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "severity": e.severity,
            "confidence": e.confidence,
            "risk_score": e.risk_score,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]
