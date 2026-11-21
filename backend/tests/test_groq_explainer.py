"""
Test Suite: Groq Explainer Resilience & Anti-Hallucination Guardrails
=====================================================================
Validates Groq integration behavior under:
1. Successful grounded explanation (HTTP 200).
2. Groq API downtime / server failure (HTTP 500) -> Fallback to deterministic.
3. Quota exhaustion / Rate limiting (HTTP 429) -> Fallback to deterministic.
4. Malformed provider responses (Invalid JSON) -> Fallback to deterministic.
5. Anti-Hallucination Guardrails (Rejecting invented diagnoses).
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from app.ml.groq_explainer import GroqExplainer


SAMPLE_NORM_ECG = {
    "status": "ok",
    "urgency": "routine",
    "conditions": [
        {"code": "NORM", "name": "Normal ECG", "detected": True, "model_score": 0.95},
        {"code": "MI", "name": "Myocardial Infarction", "detected": False, "model_score": 0.02},
    ],
    "heart_rate_bpm": 70,
    "rhythm": "Normal Sinus Rhythm",
}


def test_groq_explainer_successful_grounded_response():
    """Mock HTTP 200 with valid grounded response from Groq."""
    explainer = GroqExplainer(api_key="mock")

    mock_llm_json = {
        "summary_en": "Your ECG shows a healthy, regular electrical pattern without acute concerns.",
        "summary_hi": "आपकी ईसीजी रिपोर्ट सामान्य है और कोई गंभीर समस्या नहीं है।",
        "key_points": ["Normal electrical activity", "Healthy heart rate of 70 bpm"],
        "next_step": "Maintain your regular annual preventive checks."
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(mock_llm_json)}}]
    }

    with patch("requests.post", return_value=mock_response):
        report = explainer.explain_report(SAMPLE_NORM_ECG)

    assert report["source"] == "groq_validated"
    assert "healthy" in report["summary_en"].lower()
    assert report["urgency"] == "routine"
    assert report["detected_conditions"] == ["NORM"]


def test_groq_explainer_quota_exhaustion_http_429():
    """Validates that HTTP 429 (quota exhaustion) falls back to deterministic report."""
    explainer = GroqExplainer(api_key="mock")

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit reached for model llama-3.3-70b-versatile"

    with patch("requests.post", return_value=mock_response):
        report = explainer.explain_report(SAMPLE_NORM_ECG)

    assert report["source"] == "deterministic_fallback"
    assert "429" in report["fallback_reason"]
    assert "Normal" in report["summary_en"]  # Deterministic summary intact


def test_groq_explainer_provider_server_error_http_500():
    """Validates that HTTP 500 (Groq downtime) falls back to deterministic report."""
    explainer = GroqExplainer(api_key="mock")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("requests.post", return_value=mock_response):
        report = explainer.explain_report(SAMPLE_NORM_ECG)

    assert report["source"] == "deterministic_fallback"
    assert "500" in report["fallback_reason"]
    assert "Normal" in report["summary_en"]


def test_groq_explainer_malformed_json_response():
    """Validates that malformed/non-JSON text from provider falls back safely."""
    explainer = GroqExplainer(api_key="mock")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "This is non-JSON garbage {bad"}}]
    }

    with patch("requests.post", return_value=mock_response):
        report = explainer.explain_report(SAMPLE_NORM_ECG)

    assert report["source"] == "deterministic_fallback"
    assert "Normal" in report["summary_en"]


def test_groq_explainer_rejects_hallucinated_diagnosis():
    """
    CRITICAL SAFETY TEST: If Groq hallucinates 'myocardial infarction' or 'heart attack'
    on a strictly Normal ECG, the output grounding validator must catch and discard it.
    """
    explainer = GroqExplainer(api_key="mock")

    # Hallucinated response claiming a heart attack occurred on a Normal ECG
    hallucinated_llm_json = {
        "summary_en": "You have signs of a massive heart attack and active acute myocardial infarction.",
        "summary_hi": "आपको हार्ट अटैक हुआ है।",
        "key_points": ["Acute coronary damage detected"],
        "next_step": "Immediate coronary artery bypass."
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(hallucinated_llm_json)}}]
    }

    with patch("requests.post", return_value=mock_response):
        report = explainer.explain_report(SAMPLE_NORM_ECG)

    # Hallucination MUST be discarded!
    assert report["source"] == "deterministic_fallback"
    assert report["fallback_reason"] == "grounding_validation_failed"
    assert "massive heart attack" not in report["summary_en"]
    assert "Normal" in report["summary_en"]


def test_groq_explainer_emergency_keyword_triggers_deterministic_notice():
    """Validates that critical emergency user queries trigger immediate 112 notice."""
    explainer = GroqExplainer(api_key="mock")

    res = explainer.explain_chat_message("I have severe crushing chest pain and feel like I am collapsing")
    assert res["is_emergency"] is True
    assert "112" in res["reply"]
    assert res["source"] == "deterministic_emergency_guardrail"
