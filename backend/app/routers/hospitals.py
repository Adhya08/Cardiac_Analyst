"""
Hospital & Ambulance Finder
-----------------------------
GET /api/v1/hospitals/nearby   — Find hospitals near given coordinates.
GET /api/v1/ambulance/nearby   — Find ambulance services near given coordinates.
"""
import math
import os
import requests

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

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
async def get_nearby_hospitals(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_km: float = Query(default=10, ge=1, le=50),
    requires: Optional[str] = Query(default=None, description="Filter: cath_lab, icu"),
):
    """
    Fetch nearby cardiac hospitals using Google Places Nearby Search API.
    Returns real hospital data: name, address, distance, Google Maps link, rating.
    """
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=500, detail="Google Maps API key not configured.")

    radius_m = min(int(radius_km * 1000), 50000)

    # Primary search: cardiac hospitals
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": radius_m,
        "type": "hospital",
        "keyword": "cardiac cardiology heart hospital",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Google Maps API request failed: {e}")

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise HTTPException(
            status_code=502,
            detail=f"Google Places API error: {data.get('status')} — {data.get('error_message', '')}",
        )

    hospitals = []
    for place in data.get("results", [])[:10]:
        g = place.get("geometry", {}).get("location", {})
        h_lat, h_lon = g.get("lat", 0.0), g.get("lng", 0.0)
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
            "contact": "Please call hospital for ICU/cath lab availability",
            "place_id": place_id,
            "note": "ICU bed count & cath lab availability: call hospital directly (not available via public API)",
        })

    hospitals.sort(key=lambda h: h["distance_km"])

    return {
        "hospitals": hospitals[:5],
        "total_found": len(hospitals),
        "search_radius_km": radius_km,
        "api_status": data.get("status"),
    }


@router.get("/ambulance/nearby")
async def get_nearby_ambulances(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
):
    """
    Returns government emergency numbers + nearby private ambulance services.
    Always includes India 112 and 108 as first options.
    """
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
