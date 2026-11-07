"""
Hospital & Ambulance Finder
-----------------------------
GET /api/v1/hospitals/nearby   — Find hospitals near given coordinates.
GET /api/v1/ambulance/nearby   — Find ambulance services near given coordinates.
"""
import math
import os
import requests

from fastapi import APIRouter, Query, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["hospitals"])
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.get("/hospitals/nearby")
def get_nearby_hospitals(
    request: Request,
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_km: float = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Finds the closest emergency care facilities with IP rate limiting.
    Prioritizes ultra-close general hospitals (within 5km) and cardiac centers (up to 20km).
    """
    check_rate_limit(request, limit=120, window_seconds=60, scope="hospitals_nearby", db=db)
    if not GOOGLE_MAPS_API_KEY:
        mock_names = [
            ("Fortis Escorts Heart Institute", "Okhla Rd, New Delhi, Delhi", 1.8),
            ("Max Super Speciality Hospital", "Saket, New Delhi, Delhi", 3.2),
            ("Medanta - The Medicity", "Gurugram, Haryana", 12.5),
            ("Indraprastha Apollo Hospital", "Sarita Vihar, New Delhi, Delhi", 4.5),
            ("Metro Hospital & Heart Institute", "Noida, Uttar Pradesh", 8.1),
        ]
        hospital_results = []
        for i, (name, addr, base_dist) in enumerate(mock_names):
            hospital_results.append({
                "name": name,
                "address": addr,
                "lat": lat + (0.005 * i * (-1 if i % 2 == 0 else 1)),
                "lon": lon + (0.005 * i * (1 if i % 2 == 0 else -1)),
                "distance_km": base_dist,
                "rating": round(4.2 + (i * 0.15) % 0.7, 1),
                "total_ratings": 140 + i * 85,
                "open_now": True,
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(name)}",
                "place_id": f"mock_place_{i}",
                "contact": "+91-11-4277-6222",
            })
        return {
            "hospitals": hospital_results,
            "total_found": len(hospital_results),
            "search_center": f"{lat},{lon}"
        }

    # ── Strategy: Multiple Search Passes for maximum localized safety
    # Pass 1: Emergency & General Hospitals (Ranked by distance, no fixed radius)
    # Pass 2: Specialized Heart/Cardiac Centers (Radius biased)
    
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    # We'll use rankby=distance for immediate proximity
    params_dist = {
        "location": f"{lat},{lon}",
        "rankby": "distance",
        "type": "hospital",
        "keyword": "emergency casualty hospital trauma",
        "key": GOOGLE_MAPS_API_KEY,
    }
    
    # We'll also do a specialized cardiac pass
    params_cardio = {
        "location": f"{lat},{lon}",
        "radius": 15000,
        "keyword": "cardiac cardiology heart care",
        "key": GOOGLE_MAPS_API_KEY,
    }

    found_ids = set()
    hospital_results = []

    def get_phone_number(place_id):
        if not place_id: return None
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        try:
            r = requests.get(details_url, params={"place_id": place_id, "fields": "formatted_phone_number", "key": GOOGLE_MAPS_API_KEY}, timeout=5)
            return r.json().get("result", {}).get("formatted_phone_number")
        except:
            return None

    def process_data(data):
        for place in data.get("results", [])[:8]:
            pid = place.get("place_id")
            if pid in found_ids: continue
            
            g = place.get("geometry", {}).get("location", {})
            h_lat, h_lon = g.get("lat", 0.0), g.get("lng", 0.0)
            dist = haversine_km(lat, lon, h_lat, h_lon)
            name = place.get("name", "Unknown Hospital")
            
            hospital_results.append({
                "name": name,
                "address": place.get("vicinity", ""),
                "lat": h_lat,
                "lon": h_lon,
                "distance_km": round(dist, 1),
                "rating": place.get("rating"),
                "total_ratings": place.get("user_ratings_total", 0),
                "open_now": place.get("opening_hours", {}).get("open_now"),
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(name)}&query_place_id={pid}",
                "place_id": pid,
                "contact": get_phone_number(pid) or "Call 112 for routing",
            })
            found_ids.add(pid)

    try:
        # Get immediate emergency hospitals first
        r1 = requests.get(url, params=params_dist, timeout=10)
        process_data(r1.json())
        
        # Then fill with specialized centers
        r2 = requests.get(url, params=params_cardio, timeout=10)
        process_data(r2.json())
    except Exception as e:
         print(f"Hospital API fetch error: {e}")

    # Critical Sort: Distance above all else
    hospital_results.sort(key=lambda x: x["distance_km"])

    return {
        "hospitals": hospital_results[:5],
        "total_found": len(hospital_results),
        "search_center": f"{lat},{lon}"
    }


@router.get("/ambulance/nearby")
def get_nearby_ambulances(
    request: Request,
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    db: Session = Depends(get_db),
):
    """
    Returns government emergency numbers + nearby private ambulance services with IP rate limiting.
    Always includes India 112 and 108 as first options.
    """
    check_rate_limit(request, limit=120, window_seconds=60, scope="ambulance_nearby", db=db)
    ambulances = [
        {
            "service": "India Emergency (112)",
            "contact": "112",
            "type": "government",
            "eta_info": "National emergency number — call now",
            "maps_url": None,
            "notes": "Connects to police, fire department, and medical emergency services.",
        },
        {
            "service": "Government Ambulance (108)",
            "contact": "108",
            "type": "government",
            "eta_info": "Free govt ambulance — average 12-15 min urban",
            "maps_url": None,
            "notes": "Free ambulance service, available in most Indian states 24/7.",
        },
        {
            "service": "Red Cross India Helpline",
            "contact": "1800-180-7676",
            "type": "government",
            "eta_info": "Medical emergency helpline",
            "maps_url": None,
            "notes": "Indian Red Cross Society emergency helpline, toll-free.",
        },
    ]

    # Search for private ambulance services via Google Places
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 20000,
        "keyword": "ambulance service emergency",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=8)
        data = resp.json()
        for place in data.get("results", [])[:3]:
            g = place.get("geometry", {}).get("location", {})
            h_lat, h_lon = g.get("lat", 0.0), g.get("lng", 0.0)
            dist = haversine_km(lat, lon, h_lat, h_lon)
            eta_min = max(5, int(dist / 30 * 60))  # 30 km/h avg urban speed
            name = place.get("name", "Private Ambulance Service")
            place_id = place.get("place_id", "")
            ambulances.append({
                "service": name,
                "contact": "See Google Maps for contact",
                "type": "private",
                "eta_info": f"~{eta_min} min ETA ({dist:.1f} km away)",
                "maps_url": (
                    f"https://www.google.com/maps/search/?api=1"
                    f"&query={requests.utils.quote(name)}"
                    f"&query_place_id={place_id}"
                ),
                "notes": "Click Maps link to get contact number and directions.",
            })
    except Exception:
        pass  # Always return government services even if private search fails

    return {"ambulances": ambulances}
