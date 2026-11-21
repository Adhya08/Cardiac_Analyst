"""
Geoapify Places Service with In-Memory Caching & Offline Fallbacks
==================================================================
Discovers nearby emergency hospitals and cardiac facilities using Geoapify Places API.

Key Engineering Features:
1. Geoapify Integration: Uses v2/places with category healthcare.hospital.
2. In-Memory TTL Cache: Stores results keyed by quantized coordinates (~1km grid)
   for 30 minutes, preventing redundant API calls and conserving quota.
3. Resilient Error Handling: Automatically falls back to a curated emergency directory
   upon quota exhaustion (HTTP 429), API downtime, invalid key, or timeout.
4. Zero Paid Routing API: Generates free browser-based navigation intent URLs
   (OpenStreetMap OSRM and standard Google Maps web directions).
5. OpenStreetMap & Geoapify Data Attribution strictly included.
"""

import os
import math
import time
import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger("cardiac_analyst.places")

GEOAPIFY_API_URL = "https://api.geoapify.com/v2/places"
DEFAULT_CACHE_TTL_SECONDS = 1800  # 30 minutes

# Curated, accredited cardiac emergency centers used when provider is unavailable,
# quota is exhausted, or coordinates are default regional fallback.
CURATED_OFFLINE_HOSPITALS = [
    {
        "name": "All India Institute of Medical Sciences (AIIMS) - Emergency Cardiac Center",
        "address": "Sri Aurobindo Marg, Ansari Nagar, New Delhi, Delhi 110029",
        "lat": 28.5672,
        "lon": 77.2100,
        "rating": 4.8,
        "total_ratings": 320,
        "open_now": True,
        "contact": "+91-11-26588500",
        "place_id": "curated_aiims",
    },
    {
        "name": "Fortis Escorts Heart Institute (24x7 Cath Lab & Emergency)",
        "address": "Okhla Road, Sukhdev Vihar, New Delhi, Delhi 110025",
        "lat": 28.5603,
        "lon": 77.2790,
        "rating": 4.6,
        "total_ratings": 280,
        "open_now": True,
        "contact": "+91-11-47135000",
        "place_id": "curated_fortis",
    },
    {
        "name": "Indraprastha Apollo Hospital - Interventional Cardiology",
        "address": "Sarita Vihar, Delhi Mathura Road, New Delhi, Delhi 110076",
        "lat": 28.5355,
        "lon": 77.2874,
        "rating": 4.7,
        "total_ratings": 410,
        "open_now": True,
        "contact": "+91-11-26925858",
        "place_id": "curated_apollo",
    },
    {
        "name": "Max Super Speciality Hospital - Emergency & Cardiac Care",
        "address": "1, 2, Press Enclave Marg, Saket, New Delhi, Delhi 110017",
        "lat": 28.5284,
        "lon": 77.2115,
        "rating": 4.5,
        "total_ratings": 195,
        "open_now": True,
        "contact": "+91-11-26515050",
        "place_id": "curated_max",
    },
    {
        "name": "Medanta - The Medicity (Cardiac Emergency)",
        "address": "CH Bakhtawar Singh Rd, Sector 38, Gurugram, Haryana 122001",
        "lat": 28.4398,
        "lon": 77.0427,
        "rating": 4.6,
        "total_ratings": 520,
        "open_now": True,
        "contact": "+91-124-4141414",
        "place_id": "curated_medanta",
    },
]

ATTRIBUTION_NOTICE = "Powered by Geoapify | © OpenStreetMap contributors"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def generate_free_navigation_links(user_lat: float, user_lon: float, dest_lat: float, dest_lon: float, name: str) -> Dict[str, str]:
    """
    Generates browser-based navigation links without calling any paid routing APIs.
    """
    encoded_name = requests.utils.quote(name)
    return {
        # Universal web directions intent (free browser redirect, no Directions API query)
        "maps_url": f"https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lon}&destination={dest_lat},{dest_lon}",
        # OpenStreetMap OSRM routing link (completely open-source)
        "osm_url": f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={user_lat}%2C{user_lon}%3B{dest_lat}%2C{dest_lon}",
        # Generic geo URI for mobile devices
        "geo_uri": f"geo:{dest_lat},{dest_lon}?q={encoded_name}"
    }


class PlacesService:
    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS, timeout: float = 2.5):
        self.api_key = api_key or os.getenv("GEOAPIFY_API_KEY", "")
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, lat: float, lon: float, radius_km: float) -> str:
        # Quantize to ~1km resolution to increase cache hit rate
        return f"{round(lat, 2)}:{round(lon, 2)}:{int(radius_km)}"

    def get_fallback_hospitals(self, user_lat: float, user_lon: float, max_radius_km: float = 35.0) -> List[Dict[str, Any]]:
        results = []
        for h in CURATED_OFFLINE_HOSPITALS:
            dist = haversine_km(user_lat, user_lon, h["lat"], h["lon"])
            # Only include fallback hospitals if within radius (e.g. caller is in the Delhi NCR region)
            if dist <= max_radius_km:
                links = generate_free_navigation_links(user_lat, user_lon, h["lat"], h["lon"], h["name"])
                results.append({
                    **h,
                    "distance_km": dist,
                    "rating": None,  # Truthful: omit unverified ratings
                    "total_ratings": None,
                    "open_now": None,  # Call to confirm emergency availability
                    "maps_url": links["maps_url"],
                    "osm_url": links["osm_url"],
                    "geo_uri": links["geo_uri"],
                })
        results.sort(key=lambda x: x["distance_km"])
        return results

    def find_nearby_hospitals(self, lat: float, lon: float, radius_km: float = 10.0) -> Dict[str, Any]:
        cache_key = self._get_cache_key(lat, lon, radius_km)
        now = time.time()

        # Check Cache
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["timestamp"] < self.cache_ttl:
                logger.info(f"Serving nearby hospitals from cache for {cache_key}")
                return {
                    **entry["data"],
                    "cached": True,
                }

        # If API key not present, check if caller is within regional directory radius
        if not self.api_key or not self.api_key.strip():
            logger.info("GEOAPIFY_API_KEY not configured. Checking regional directory within radius.")
            hospitals = self.get_fallback_hospitals(lat, lon, max_radius_km=radius_km)
            res = {
                "hospitals": hospitals,
                "total_found": len(hospitals),
                "source": "offline_directory" if hospitals else "none_in_radius",
                "attribution": ATTRIBUTION_NOTICE,
                "cached": False,
            }
            return res

        radius_meters = int(min(max(radius_km, 1.0), 50.0) * 1000)
        params = {
            "categories": "healthcare.hospital",
            "filter": f"circle:{lon},{lat},{radius_meters}",
            "bias": f"proximity:{lon},{lat}",
            "limit": 12,
            "apiKey": self.api_key.strip(),
        }

        try:
            resp = requests.get(GEOAPIFY_API_URL, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                logger.warning("Geoapify Places API quota exceeded (HTTP 429).")
                hospitals = self.get_fallback_hospitals(lat, lon, max_radius_km=radius_km)
                return {
                    "hospitals": hospitals,
                    "total_found": len(hospitals),
                    "source": "offline_fallback_quota_exceeded",
                    "attribution": ATTRIBUTION_NOTICE,
                    "cached": False,
                }
            if resp.status_code != 200:
                logger.warning(f"Geoapify Places API error (HTTP {resp.status_code}).")
                hospitals = self.get_fallback_hospitals(lat, lon, max_radius_km=radius_km)
                return {
                    "hospitals": hospitals,
                    "total_found": len(hospitals),
                    "source": "offline_fallback_api_error",
                    "attribution": ATTRIBUTION_NOTICE,
                    "cached": False,
                }

            data = resp.json()
            features = data.get("features", [])
            hospitals = []

            for feat in features:
                props = feat.get("properties", {})
                h_name = props.get("name") or props.get("formatted", "Healthcare Facility")
                h_lat = props.get("lat")
                h_lon = props.get("lon")

                if h_lat is None or h_lon is None:
                    continue

                dist_m = props.get("distance")
                dist_km = round(dist_m / 1000.0, 1) if dist_m is not None else haversine_km(lat, lon, h_lat, h_lon)

                # Strict radius enforcement
                if dist_km > radius_km:
                    continue

                links = generate_free_navigation_links(lat, lon, h_lat, h_lon, h_name)
                contact = props.get("contact", {}).get("phone") if isinstance(props.get("contact"), dict) else props.get("phone")

                hospitals.append({
                    "name": h_name,
                    "address": props.get("address_line2") or props.get("formatted") or "Emergency Care Facility",
                    "lat": h_lat,
                    "lon": h_lon,
                    "distance_km": dist_km,
                    "rating": None,  # Truthful: omit unverified ratings
                    "total_ratings": None,
                    "open_now": None,  # Unverified by basic places lookup; call to confirm emergency care
                    "contact": contact,
                    "place_id": props.get("place_id", f"geo_{h_lat}_{h_lon}"),
                    "maps_url": links["maps_url"],
                    "osm_url": links["osm_url"],
                    "geo_uri": links["geo_uri"],
                })

            if not hospitals:
                logger.info(f"Zero facilities found in {radius_km}km radius. Checking regional directory.")
                hospitals = self.get_fallback_hospitals(lat, lon, max_radius_km=radius_km)

            hospitals.sort(key=lambda x: x["distance_km"])
            result_payload = {
                "hospitals": hospitals[:8],
                "total_found": len(hospitals),
                "source": "geoapify" if hospitals else "none_in_radius",
                "attribution": ATTRIBUTION_NOTICE,
            }

            # Cache successful response
            self._cache[cache_key] = {
                "timestamp": now,
                "data": result_payload,
            }

            return {
                **result_payload,
                "cached": False,
            }

        except Exception as e:
            logger.warning(f"Error querying Geoapify Places ({e}).")
            hospitals = self.get_fallback_hospitals(lat, lon, max_radius_km=radius_km)
            return {
                "hospitals": hospitals,
                "total_found": len(hospitals),
                "source": "offline_fallback_exception",
                "attribution": ATTRIBUTION_NOTICE,
                "cached": False,
            }


_places_service_instance: Optional[PlacesService] = None

def get_places_service() -> PlacesService:
    global _places_service_instance
    if _places_service_instance is None:
        _places_service_instance = PlacesService()
    return _places_service_instance
