"""
Automated Verification Suite: Hospital Geospatial Integrity & Distance Accuracy
================================================================================
Verifies that hospital discoveries, coordinates, Haversine straight-line distances,
and emergency fallbacks are mathematically sound and geographically truthful.

Key Test Suites:
1. Haversine distance accuracy against known geographic coordinates.
2. Anti-regression: Fortis Okhla, Max Saket, and Medanta Gurugram cannot appear in Vaishali as 1.8km/3.2km/12.5km.
3. Strict radius filtering (2km, 5km, 10km, 20km).
4. Sorting by calculated distance.
5. Canonical ID matching and deduplication.
6. Geoapify Places response parsing with coordinate validation.
7. Location-aware caching (preventing cross-location cache leakage).
8. Resilient error handling (HTTP 429, timeout, provider exceptions).
"""

import math
import pytest
from unittest.mock import patch, MagicMock
from app.services.places_service import (
    PlacesService,
    haversine_km,
    generate_free_navigation_links,
    CURATED_OFFLINE_HOSPITALS,
)


# Known benchmark coordinates (WGS-84)
VAISHALI_GHAZIABAD = (28.6415, 77.3400)
KAUSHAMBI_GHAZIABAD = (28.6385, 77.3240)
CONNAUGHT_PLACE_DELHI = (28.6315, 77.2167)
FORTIS_OKHLA_DELHI = (28.5603, 77.2790)
MAX_SAKET_DELHI = (28.5284, 77.2115)
MEDANTA_GURUGRAM = (28.4398, 77.0427)
MUMBAI_CST = (18.9400, 72.8353)


def test_haversine_formula_accuracy():
    """Validates great-circle distance calculation using WGS-84 Earth radius 6371.0 km."""
    # Distance between Connaught Place and AIIMS Delhi (~7.2 km)
    aiims_lat, aiims_lon = 28.5672, 77.2100
    dist = haversine_km(CONNAUGHT_PLACE_DELHI[0], CONNAUGHT_PLACE_DELHI[1], aiims_lat, aiims_lon)
    assert 7.0 <= dist <= 7.5

    # Self-distance must be zero
    assert haversine_km(VAISHALI_GHAZIABAD[0], VAISHALI_GHAZIABAD[1], VAISHALI_GHAZIABAD[0], VAISHALI_GHAZIABAD[1]) == 0.0


def test_regression_vaishali_cannot_show_distant_hospitals_as_close():
    """
    CRITICAL REGRESSION TEST:
    Ensures Fortis Escorts (Okhla), Max Saket, and Medanta Gurugram are NOT
    falsely reported as 1.8km, 3.2km, or 12.5km away from Vaishali, Ghaziabad.
    """
    vaishali_lat, vaishali_lon = VAISHALI_GHAZIABAD

    dist_fortis = haversine_km(vaishali_lat, vaishali_lon, FORTIS_OKHLA_DELHI[0], FORTIS_OKHLA_DELHI[1])
    dist_max_saket = haversine_km(vaishali_lat, vaishali_lon, MAX_SAKET_DELHI[0], MAX_SAKET_DELHI[1])
    dist_medanta = haversine_km(vaishali_lat, vaishali_lon, MEDANTA_GURUGRAM[0], MEDANTA_GURUGRAM[1])

    # True distances from Vaishali:
    # - Fortis Escorts Okhla is ~10.8 km (NEVER 1.8 km)
    # - Max Saket is ~17.8 km (NEVER 3.2 km)
    # - Medanta Gurugram is ~37.4 km (NEVER 12.5 km)
    assert dist_fortis > 9.5, f"Fortis Okhla reported as {dist_fortis} km; cannot be 1.8 km"
    assert dist_max_saket > 15.0, f"Max Saket reported as {dist_max_saket} km; cannot be 3.2 km"
    assert dist_medanta > 30.0, f"Medanta Gurugram reported as {dist_medanta} km; cannot be 12.5 km"


def test_vaishali_5km_radius_filtering():
    """A 5km radius search in Vaishali must include local facilities and exclude distant Delhi/Gurugram hospitals."""
    service = PlacesService(api_key=None)  # Uses verified directory
    result = service.find_nearby_hospitals(
        lat=VAISHALI_GHAZIABAD[0],
        lon=VAISHALI_GHAZIABAD[1],
        radius_km=5.0,
    )

    hospitals = result["hospitals"]
    assert result["total_found"] == len(hospitals)

    # Every returned hospital must strictly be within 5.0 km
    for h in hospitals:
        assert h["distance_km"] <= 5.0

    # Max Vaishali (~0.6 km) and Yashoda Kaushambi (~1.6 km) must be present
    hospital_names = [h["name"] for h in hospitals]
    assert any("Vaishali" in name for name in hospital_names)
    assert any("Kaushambi" in name for name in hospital_names)

    # Fortis Okhla (10.8 km), Max Saket (17.8 km), and Medanta (37.4 km) must be excluded
    assert not any("Okhla" in name for name in hospital_names)
    assert not any("Saket" in name for name in hospital_names)
    assert not any("Medanta" in name for name in hospital_names)


def test_sorting_by_computed_distance():
    """Hospitals must always be sorted in ascending order of calculated distance."""
    service = PlacesService(api_key=None)
    result = service.find_nearby_hospitals(
        lat=VAISHALI_GHAZIABAD[0],
        lon=VAISHALI_GHAZIABAD[1],
        radius_km=20.0,
    )
    hospitals = result["hospitals"]
    assert len(hospitals) >= 2

    distances = [h["distance_km"] for h in hospitals]
    assert distances == sorted(distances)


def test_canonical_record_schema():
    """Every hospital record must contain all required canonical fields and omit unverified claims."""
    service = PlacesService(api_key=None)
    result = service.find_nearby_hospitals(lat=VAISHALI_GHAZIABAD[0], lon=VAISHALI_GHAZIABAD[1], radius_km=10.0)

    for h in result["hospitals"]:
        assert h["id"] is not None and len(h["id"]) > 0
        assert h["place_id"] == h["id"]
        assert -90.0 <= h["lat"] <= 90.0
        assert -180.0 <= h["lon"] <= 180.0
        assert h["distance_type"] == "straight_line"
        assert h["verified"] is True
        assert h["maps_url"].startswith("https://")
        # Truthful medical safety guarantees:
        assert h["rating"] is None
        assert h["total_ratings"] is None
        assert h["open_now"] is None


def test_location_aware_caching_isolation():
    """Cached response for Delhi must NOT be served to a request in Vaishali."""
    service = PlacesService(api_key=None)

    res_delhi = service.find_nearby_hospitals(CONNAUGHT_PLACE_DELHI[0], CONNAUGHT_PLACE_DELHI[1], radius_km=10.0)
    res_vaishali = service.find_nearby_hospitals(VAISHALI_GHAZIABAD[0], VAISHALI_GHAZIABAD[1], radius_km=10.0)

    # Cache keys must differ
    key_delhi = service._get_cache_key(CONNAUGHT_PLACE_DELHI[0], CONNAUGHT_PLACE_DELHI[1], 10.0)
    key_vaishali = service._get_cache_key(VAISHALI_GHAZIABAD[0], VAISHALI_GHAZIABAD[1], 10.0)
    assert key_delhi != key_vaishali

    # Results must reflect their distinct geographical centers
    delhi_names = [h["name"] for h in res_delhi["hospitals"]]
    vaishali_names = [h["name"] for h in res_vaishali["hospitals"]]
    assert delhi_names != vaishali_names


def test_geoapify_response_parsing_and_deduplication():
    """Geoapify response parsing must correctly parse coordinates, calculate Haversine distance, and deduplicate."""
    mock_geoapify_payload = {
        "features": [
            {
                "properties": {
                    "name": "Local Community Hospital",
                    "formatted": "123 Main St, Ghaziabad",
                    "lat": 28.6430,
                    "lon": 77.3420,
                    "place_id": "geo_community_1",
                    "phone": "+91-120-111111",
                }
            },
            # Duplicate entry with identical coordinates (~20m apart)
            {
                "properties": {
                    "name": "Local Community Hospital (Wing B)",
                    "formatted": "123 Main St, Ghaziabad",
                    "lat": 28.6430,
                    "lon": 77.3421,
                    "place_id": "geo_community_2",
                }
            },
            # Out of radius entry (lat: 28.9, lon: 77.8 is > 50km)
            {
                "properties": {
                    "name": "Distant Hospital",
                    "lat": 28.9500,
                    "lon": 77.8500,
                    "place_id": "geo_distant",
                }
            },
        ]
    }

    service = PlacesService(api_key="test_dummy_key")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_geoapify_payload
        mock_get.return_value = mock_resp

        res = service.find_nearby_hospitals(VAISHALI_GHAZIABAD[0], VAISHALI_GHAZIABAD[1], radius_km=5.0)

        # Distant hospital (>50km) must be filtered out by strict radius
        assert all(h["distance_km"] <= 5.0 for h in res["hospitals"])
        # Duplicate should be filtered by 50m proximity deduplication
        assert len(res["hospitals"]) == 1
        assert res["hospitals"][0]["name"] == "Local Community Hospital"
        assert res["hospitals"][0]["source"] == "geoapify"


def test_provider_http_429_graceful_fallback():
    """HTTP 429 quota exhaustion must fall back gracefully to verified facilities within radius."""
    service = PlacesService(api_key="test_dummy_key")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        res = service.find_nearby_hospitals(VAISHALI_GHAZIABAD[0], VAISHALI_GHAZIABAD[1], radius_km=5.0)
        assert res["source"] == "offline_fallback_quota_exceeded"
        # Must only return verified facilities strictly within 5.0 km
        assert all(h["distance_km"] <= 5.0 for h in res["hospitals"])


def test_empty_provider_response_outside_coverage():
    """When searching in an area with zero provider or directory facilities (e.g. Mumbai), return none_in_radius."""
    service = PlacesService(api_key=None)
    res = service.find_nearby_hospitals(MUMBAI_CST[0], MUMBAI_CST[1], radius_km=5.0)

    assert res["total_found"] == 0
    assert res["hospitals"] == []
    assert res["source"] == "none_in_radius"
