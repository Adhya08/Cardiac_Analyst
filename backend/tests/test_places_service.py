"""
Test Suite: Geoapify Places Service & Navigation Resilience
============================================================
Validates PlacesService behavior under:
1. Successful Geoapify query (GeoJSON parsing, distances, free navigation links).
2. In-Memory TTL Cache hits (zero duplicate network calls).
3. Quota exhaustion (HTTP 429) -> Fallback to curated offline directory.
4. Provider failure (HTTP 500 / timeout) -> Fallback to offline directory.
5. Malformed provider responses (missing geometries/properties) -> Safe parsing.
6. OpenStreetMap & Geoapify attribution enforcement.
7. Free navigation URLs (OSM OSRM & Google Web Directions).
"""

from unittest.mock import patch, MagicMock
import pytest

from app.services.places_service import PlacesService, ATTRIBUTION_NOTICE


MOCK_GEOAPIFY_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Apollo Heart Centre",
                "formatted": "Apollo Hospital, Mathura Road, New Delhi",
                "address_line2": "Mathura Road, New Delhi",
                "lat": 28.5355,
                "lon": 77.2874,
                "distance": 4500,
                "phone": "+91-11-26925858",
                "place_id": "geo_apollo_123"
            }
        },
        {
            "type": "Feature",
            "properties": {
                "name": "Fortis Cardiac Care",
                "formatted": "Okhla Road, New Delhi",
                "address_line2": "Okhla Road, New Delhi",
                "lat": 28.5603,
                "lon": 77.2790,
                "distance": 3200,
                "phone": "+91-11-47135000",
                "place_id": "geo_fortis_456"
            }
        }
    ]
}


def test_places_service_successful_query():
    """Validates successful Geoapify response parsing, distances, and free navigation links."""
    service = PlacesService(api_key="mock")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_GEOAPIFY_GEOJSON

    with patch("requests.get", return_value=mock_resp):
        res = service.find_nearby_hospitals(lat=28.6139, lon=77.2090, radius_km=10.0)

    assert res["source"] == "geoapify"
    assert res["attribution"] == ATTRIBUTION_NOTICE
    assert len(res["hospitals"]) == 2
    # Verify distance sorting
    assert res["hospitals"][0]["distance_km"] <= res["hospitals"][1]["distance_km"]
    # Verify free navigation links
    first = res["hospitals"][0]
    assert "openstreetmap.org" in first["osm_url"]
    assert "google.com/maps/dir" in first["maps_url"]
    assert "api=1" in first["maps_url"]


def test_places_service_in_memory_cache_hit():
    """Validates that a second call with identical coordinates returns cached data without calling API."""
    service = PlacesService(api_key="mock", cache_ttl=60)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_GEOAPIFY_GEOJSON

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # First call: hits network
        res1 = service.find_nearby_hospitals(lat=28.6139, lon=77.2090, radius_km=10.0)
        assert res1["cached"] is False
        assert mock_get.call_count == 1

        # Second call with same coordinates: hits cache
        res2 = service.find_nearby_hospitals(lat=28.6140, lon=77.2091, radius_km=10.0)
        assert res2["cached"] is True
        assert mock_get.call_count == 1  # No additional network call!


def test_places_service_quota_exhaustion_http_429():
    """Validates that HTTP 429 quota exhaustion falls back safely to curated offline directory."""
    service = PlacesService(api_key="mock")

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Monthly API quota exceeded"

    with patch("requests.get", return_value=mock_resp):
        res = service.find_nearby_hospitals(lat=28.6139, lon=77.2090, radius_km=10.0)

    assert "offline_fallback" in res["source"]
    assert len(res["hospitals"]) > 0
    assert any("AIIMS" in h["name"] for h in res["hospitals"])
    assert res["attribution"] == ATTRIBUTION_NOTICE


def test_places_service_provider_error_http_500():
    """Validates that HTTP 500 provider error falls back safely to curated offline directory."""
    service = PlacesService(api_key="mock")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("requests.get", return_value=mock_resp):
        res = service.find_nearby_hospitals(lat=28.6139, lon=77.2090, radius_km=10.0)

    assert "offline_fallback" in res["source"]
    assert len(res["hospitals"]) > 0


def test_places_service_malformed_geojson():
    """Validates resilience against malformed GeoJSON features with missing coordinates."""
    service = PlacesService(api_key="mock")

    malformed_json = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "Broken Hospital"}},  # Missing lat/lon
            {
                "type": "Feature",
                "properties": {
                    "name": "Valid Hospital",
                    "lat": 28.55,
                    "lon": 77.25,
                    "distance": 3000
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = malformed_json

    with patch("requests.get", return_value=mock_resp):
        res = service.find_nearby_hospitals(lat=28.6139, lon=77.2090, radius_km=10.0)

    # Valid hospital parsed safely despite broken sibling feature
    assert len(res["hospitals"]) == 1
    assert res["hospitals"][0]["name"] == "Valid Hospital"


def test_places_service_unconfigured_key_serves_offline_directory():
    """Validates that if GEOAPIFY_API_KEY is not set, offline directory is served cleanly."""
    service = PlacesService(api_key="")

    res = service.find_nearby_hospitals(lat=28.6139, lon=77.2090, radius_km=10.0)
    assert res["source"] == "offline_directory"
    assert len(res["hospitals"]) >= 4
