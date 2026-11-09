"""
Emergency Triage Engine
------------------------
Clinical emergency triage engine loading shared rules from `shared/triage_rules.json`.
Classifies patient urgency into 3 clinical tiers:
- emergency (Call Emergency Services Now)
- see_doctor_today (See a Doctor Today)
- no_emergency_warning_signs (No Emergency Warning Signs Identified)

Clinical References & Standards:
- UK NICE CG95: Chest pain of recent onset assessment and diagnosis.
- ACC/AHA STEMI Guidelines (O'Gara et al., JACC 2013).
- SIGN 93: Acute coronary syndromes.
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

# Load shared clinical rules JSON
_RULES_PATH = Path(os.getenv("TRIAGE_RULES_PATH", Path(__file__).resolve().parents[3] / "shared" / "triage_rules.json"))
if not _RULES_PATH.is_file():
    # Fallback to local shared location if relative structure differs
    alt_path = Path(__file__).resolve().parents[2] / "shared" / "triage_rules.json"
    if alt_path.is_file():
        _RULES_PATH = alt_path

with open(_RULES_PATH, "r", encoding="utf-8") as f:
    RULES: Dict[str, Any] = json.load(f)

# Extract shared structures
TRIAGE_QUESTION_DEFS: List[Dict[str, Any]] = RULES["questions"]
TRIAGE_QUESTIONS: List[str] = [q["text"] for q in TRIAGE_QUESTION_DEFS]
QUESTION_IDS: List[str] = [q["id"] for q in TRIAGE_QUESTION_DEFS]
INSTRUCTIONS: Dict[str, List[str]] = RULES["instructions"]
LOWEST_TIER_STATEMENT: str = RULES["lowest_tier_statement"]
CLINICAL_DISCLAIMER: str = RULES.get("clinical_disclaimer", "")


def assess_emergency(
    symptoms: Union[List[bool], Dict[str, bool]],
    bp_sys: Optional[int] = None,
    hr: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Assess acute cardiac emergency severity using shared triage rules.

    Args:
        symptoms: List of boolean answers (length 12, or legacy 8 padded with False),
                  or dictionary mapping question ID to boolean.
        bp_sys:   Current systolic blood pressure in mmHg (optional).
        hr:       Current heart rate in bpm (optional).

    Returns:
        dict with severity, confidence, risk_score, yes_count, stemi_suspicious,
        combo_triggered, vitals_red_flag, and instructions.
    """
    # ── Normalize answers into {question_id: bool}
    ans_map: Dict[str, bool] = {}
    if isinstance(symptoms, list):
        for idx, q in enumerate(TRIAGE_QUESTION_DEFS):
            if idx < len(symptoms):
                ans_map[q["id"]] = bool(symptoms[idx])
            else:
                ans_map[q["id"]] = False
    elif isinstance(symptoms, dict):
        for q in TRIAGE_QUESTION_DEFS:
            # Check by ID or stringified index
            val = symptoms.get(q["id"])
            if val is None:
                # Try numeric index
                idx = QUESTION_IDS.index(q["id"])
                val = symptoms.get(str(idx), symptoms.get(idx, False))
            ans_map[q["id"]] = bool(val)
    else:
        for q in TRIAGE_QUESTION_DEFS:
            ans_map[q["id"]] = False

    # ── 1. Vital signs evaluation
    thresholds = RULES["rules"]["vital_signs_thresholds"]
    bp_shock = bp_sys is not None and bp_sys < thresholds["bp_sys_shock_below"]
    bp_crisis = bp_sys is not None and bp_sys > thresholds["bp_sys_crisis_above"]
    hr_critical = hr is not None and (hr < thresholds["hr_critical_below"] or hr > thresholds["hr_critical_above"])
    vitals_red_flag = bp_shock or bp_crisis or hr_critical

    # ── 2. Red flag symptom calculation
    red_flag_keys = RULES["rules"]["red_flag_keys"]
    present_red_flags = [k for k in red_flag_keys if ans_map.get(k, False)]
    red_flag_count = len(present_red_flags)
    yes_count = sum(1 for v in ans_map.values() if v)

    # Cardinal STEMI triad suspicion
    stemi_suspicious = bool(
        ans_map.get("crushing_chest_pain")
        and ans_map.get("radiating_pain")
        and (ans_map.get("cold_sweats") or ans_map.get("dyspnea_at_rest"))
    )

    # ── 3. Emergency criteria (ACC/AHA & NICE CG95 cardinal patterns)
    syncope = bool(ans_map.get(RULES["rules"]["emergency_syncope_key"], False))
    sweats_combo = all(ans_map.get(k, False) for k in RULES["rules"]["emergency_sweats_combo"])
    shock_combo = all(ans_map.get(k, False) for k in RULES["rules"]["emergency_shock_combo"])
    persistent_cad_combo = bool(
        red_flag_count >= 1
        and ans_map.get(RULES["rules"]["emergency_persistent_cad_combo"]["requires_history"], False)
        and ans_map.get(RULES["rules"]["emergency_persistent_cad_combo"]["requires_duration"], False)
    )
    two_or_more_red_flags = red_flag_count >= RULES["rules"]["emergency_min_red_flags"]

    is_emergency = (
        vitals_red_flag
        or syncope
        or two_or_more_red_flags
        or sweats_combo
        or shock_combo
        or persistent_cad_combo
    )

    combo_triggered = syncope or two_or_more_red_flags or sweats_combo or shock_combo or persistent_cad_combo

    # ── 4. "See Doctor Today" criteria (if not emergency)
    see_doctor_rules = RULES["rules"]["see_doctor_today_rules"]
    single_red_flag = red_flag_count >= see_doctor_rules["min_red_flags"]

    has_associated_symptom = any(ans_map.get(k, False) for k in see_doctor_rules["associated_symptoms"])
    risk_factor_count = sum(
        1 for k in see_doctor_rules["risk_factors_to_escalate_associated"] if ans_map.get(k, False)
    )
    associated_with_risk_factors = (
        has_associated_symptom
        and (
            risk_factor_count >= see_doctor_rules["min_risk_factors_for_associated"]
            or ans_map.get("known_heart_disease", False)
        )
    )
    associated_with_prolonged_duration = has_associated_symptom and bool(ans_map.get("duration_over_1_hour", False))

    is_see_doctor = (
        single_red_flag
        or associated_with_risk_factors
        or associated_with_prolonged_duration
        or (has_associated_symptom and ans_map.get("age_over_40", False) and ans_map.get("diabetes", False))
    )

    # ── 5. Urgency Tier & Metrics
    if is_emergency:
        severity = "emergency"
        confidence = min(0.99, 0.85 + red_flag_count * 0.03 + (0.05 if vitals_red_flag else 0.0))
        risk_score = min(99.0, 75.0 + red_flag_count * 4.0 + (10.0 if vitals_red_flag else 0.0))
    elif is_see_doctor:
        severity = "see_doctor_today"
        confidence = min(0.88, 0.72 + red_flag_count * 0.05 + risk_factor_count * 0.02)
        risk_score = min(68.0, 38.0 + red_flag_count * 12.0 + risk_factor_count * 5.0)
    else:
        severity = "no_emergency_warning_signs"
        confidence = 0.82
        risk_score = max(3.0, 5.0 + yes_count * 2.0)

    instructions = INSTRUCTIONS[severity]
    tier_info = RULES["tiers"][severity]

    return {
        "severity": severity,
        "confidence": round(float(confidence), 3),
        "risk_score": round(float(risk_score), 1),
        "yes_count": yes_count,
        "stemi_suspicious": stemi_suspicious,
        "combo_triggered": combo_triggered,
        "vitals_red_flag": vitals_red_flag,
        "instructions": instructions,
        "urgency_tier": tier_info["id"],
        "action_headline": tier_info["label"],
    }
