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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import TriageEvent
from ..schemas import TriageIn, TriageOut
from ..ml.triage import assess_emergency, TRIAGE_QUESTIONS

router = APIRouter(prefix="/api/v1/emergency", tags=["emergency"])
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_hospitals_from_google(lat: float, lon: float) -> List[dict]:
    """Real Google Places Nearby Search for cardiac hospitals."""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 15000,  # 15 km
        "type": "hospital",
        "keyword": "cardiac heart cardiology emergency",
        "key": GOOGLE_MAPS_API_KEY,
        "rankby": "prominence",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hospitals = []
        for place in data.get("results", [])[:8]:
            g = place.get("geometry", {}).get("location", {})
            h_lat, h_lon = g.get("lat", 0), g.get("lng", 0)
            dist = haversine_km(lat, lon, h_lat, h_lon)
            name = place.get("name", "Unknown Hospital")
            place_id = place.get("place_id", "")
            hospitals.append({
                "name": name,
                "address": place.get("vicinity", ""),
                "lat": h_lat,
                "lon": h_lon,
                "distance_km": round(dist, 1),
                "rating": place.get("rating"),
                "total_ratings": place.get("user_ratings_total", 0),
                "open_now": place.get("opening_hours", {}).get("open_now"),
                "maps_url": (
                    f"https://www.google.com/maps/search/?api=1"
                    f"&query={requests.utils.quote(name)}"
                    f"&query_place_id={place_id}"
                ),
                "contact": "Call hospital for ICU/cath lab availability",
                "place_id": place_id,
            })
        hospitals.sort(key=lambda h: h["distance_km"])
        return hospitals[:5]
    except Exception as e:
        print(f"[Emergency] Google Places API error: {e}")
        return []


@router.get("/questions")
async def get_questions():
    """Return the 8 triage questions."""
    return {"questions": TRIAGE_QUESTIONS}


@router.post("/triage")
def submit_triage(
    data: TriageIn,
    db: Session = Depends(get_db),
):
    """
    Assess emergency severity using NICE CG95 and ACC/AHA rules,
    then fetch real nearby hospitals via Google Places API.
    """
    if len(data.symptoms) != 8:
        raise HTTPException(status_code=422, detail="Exactly 8 symptom answers required.")

    # ── Clinical assessment
    assessment = assess_emergency(
        symptoms=data.symptoms,
        bp_sys=data.bp_sys,
        hr=data.hr,
    )

    # ── Real hospital lookup (if location provided)
    hospitals = []
    if data.lat is not None and data.lon is not None:
        hospitals = fetch_hospitals_from_google(data.lat, data.lon)

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

    # ── Persist event
    event = TriageEvent(
        id=str(uuid.uuid4()),
        user_id=data.user_id,
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

    return {
        **assessment,
        "hospitals": hospitals,
        "ambulances": ambulances,
        "triage_id": event.id,
    }
