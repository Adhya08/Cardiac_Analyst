"""
Hospital & Ambulance Finder
-----------------------------
GET /api/v1/hospitals/nearby   — Find emergency cardiac care facilities using Geoapify Places API.
GET /api/v1/ambulance/nearby   — Find emergency medical and ambulance dispatch services.
"""
from fastapi import APIRouter, Query, Request, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..rate_limiter import check_rate_limit
from ..services.places_service import get_places_service, haversine_km

router = APIRouter(prefix="/api/v1", tags=["hospitals"])


@router.get("/hospitals/nearby")
def get_nearby_hospitals(
    request: Request,
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_km: float = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Finds the closest emergency care and cardiac facilities with IP rate limiting.
    Uses Geoapify Places API with in-memory caching and offline directory fallback.
    """
    check_rate_limit(request, limit=120, window_seconds=60, scope="hospitals_nearby", db=db)
    places_service = get_places_service()
    result = places_service.find_nearby_hospitals(lat=lat, lon=lon, radius_km=radius_km)

    return {
        "hospitals": result["hospitals"],
        "total_found": result["total_found"],
        "search_center": f"{lat},{lon}",
        "search_radius_km": radius_km,
        "source": result.get("source", "places_service"),
        "attribution": result.get("attribution", "Powered by Geoapify | © OpenStreetMap contributors"),
        "cached": result.get("cached", False),
    }


@router.get("/ambulance/nearby")
def get_nearby_ambulances(
    request: Request,
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    db: Session = Depends(get_db),
):
    """
    Returns government emergency numbers and emergency medical services with IP rate limiting.
    Always includes India 112, 108, and Red Cross.
    """
    check_rate_limit(request, limit=120, window_seconds=60, scope="ambulance_nearby", db=db)
    ambulances = [
        {
            "service": "National Emergency Helpline (112)",
            "contact": "112",
            "type": "government",
            "eta_info": "Immediate national emergency dispatch (Police, Fire, Medical)",
            "maps_url": None,
            "notes": "24/7 all-in-one toll-free emergency dispatch helpline across India.",
        },
        {
            "service": "Government Emergency Ambulance (108)",
            "contact": "108",
            "type": "government",
            "eta_info": "Free govt cardiac ambulance — average 10-15 min dispatch",
            "maps_url": None,
            "notes": "Free state ambulance service with Basic & Advanced Life Support (ALS).",
        },
        {
            "service": "Govt Patient Referral Transport (102)",
            "contact": "102",
            "type": "government",
            "eta_info": "Free medical transfer & hospital admission transport",
            "maps_url": None,
            "notes": "Dedicated 24/7 hospital admission and referral support line.",
        },
        {
            "service": "Indian Red Cross Society Helpline",
            "contact": "1800-180-7676",
            "type": "government",
            "eta_info": "Disaster & critical medical assistance helpline",
            "maps_url": None,
            "notes": "Toll-free humanitarian and emergency medical coordination helpline.",
        },
    ]

    return {"ambulances": ambulances}
