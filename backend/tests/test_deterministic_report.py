"""
Test Suite: Deterministic Structured Report & Advice Generator
==============================================================
Validates that reports and clinical advice are 100% deterministic, bilingual,
free from external LLM dependence, and strictly grounded in local model metrics.
"""

import pytest
from app.ml.report_generator import (
    generate_deterministic_report,
    generate_deterministic_advice,
    DIAGNOSTIC_EXPLAINERS,
    STANDARD_DISCLAIMER
)


def test_deterministic_report_normal_ecg():
    """Validates that a normal ECG generates reassuring, grounded English & Hindi narratives."""
    ecg_data = {
        "status": "ok",
        "urgency": "routine",
        "conditions": [
            {"code": "NORM", "name": "Normal ECG", "detected": True, "model_score": 0.94},
            {"code": "MI", "name": "Myocardial Infarction", "detected": False, "model_score": 0.05},
        ],
        "heart_rate_bpm": 72,
        "rhythm": "Sinus Rhythm",
        "pr_interval_ms": 160,
        "qrs_duration_ms": 88,
        "qtc_ms": 415,
        "st_elevation_leads": [],
        "st_depression_leads": [],
    }

    report = generate_deterministic_report(ecg_data)

    assert report["source"] == "deterministic_engine"
    assert report["urgency"] == "routine"
    assert report["is_emergency"] is False
    assert "Normal" in report["summary_en"]
    assert "सामान्य" in report["summary_hi"]
    assert len(report["key_points"]) > 0
    assert report["disclaimer"] == STANDARD_DISCLAIMER
    assert report["detected_conditions"] == ["NORM"]
    assert report["metrics_summary"]["heart_rate_bpm"] == 72


def test_deterministic_report_myocardial_infarction_escalation():
    """Validates that MI triggers immediate emergency next steps and clinical alerts."""
    ecg_data = {
        "status": "ok",
        "urgency": "emergency",
        "conditions": [
            {"code": "MI", "name": "Myocardial Infarction", "detected": True, "model_score": 0.89},
            {"code": "NORM", "name": "Normal ECG", "detected": False, "model_score": 0.02},
        ],
        "heart_rate_bpm": 105,
        "rhythm": "Sinus Tachycardia",
        "st_elevation_leads": ["V1", "V2", "V3"],
    }

    report = generate_deterministic_report(ecg_data)

    assert report["is_emergency"] is True
    assert report["urgency"] == "emergency"
    assert "MI" in report["detected_conditions"]
    assert "112" in report["next_step"]
    assert "112" in report["next_step_hi"]
    assert any("V1, V2, V3" in pt for pt in report["key_points"])


def test_deterministic_report_multiple_co_occurring_conditions():
    """Validates multi-label synthesis when multiple abnormalities are detected."""
    ecg_data = {
        "status": "ok",
        "urgency": "see_doctor_today",
        "conditions": [
            {"code": "CD", "name": "Conduction Disturbance", "detected": True, "model_score": 0.78},
            {"code": "HYP", "name": "Hypertrophy", "detected": True, "model_score": 0.72},
        ],
        "qrs_duration_ms": 132,
    }

    report = generate_deterministic_report(ecg_data)

    assert "CD" in report["detected_conditions"]
    assert "HYP" in report["detected_conditions"]
    assert "Conduction Disturbance" in report["summary_en"]
    assert "Hypertrophy" in report["summary_en"]


def test_deterministic_report_analysis_unavailable():
    """Validates fallback when ECG input is unusable/flatline without fabricating diagnoses."""
    ecg_data = {
        "status": "analysis_unavailable",
        "abstain_reason": "High frequency noise exceeding clinical amplitude threshold.",
    }

    report = generate_deterministic_report(ecg_data)

    assert report["urgency"] == "unavailable"
    assert report["is_emergency"] is False
    assert report["detected_conditions"] == []
    assert "Unavailable" in report["summary_en"]
    assert "अनुपलब्ध" in report["summary_hi"]


def test_deterministic_advice_elevated_vitals():
    """Validates rule-based vitals advice for hypertensive vitals."""
    vitals = {
        "bp_sys": 155,
        "bp_dia": 95,
        "hr": 84,
        "glucose": 160,
    }

    advice = generate_deterministic_advice(vitals, risk_tier="Elevated", ecg_urgency="see_doctor_today")

    assert advice["risk_tier"] == "Elevated"
    assert advice["source"] == "deterministic_engine"
    assert any("155" in d for d in advice["do_list"])
    assert any("sugar" in d.lower() for d in advice["do_list"])
    assert "24–48 hours" in advice["follow_up"]
