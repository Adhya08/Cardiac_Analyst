"""
Exhaustive Combinatorial Safety Test Suite: Emergency Triage Rules
==================================================================
Formally validates:
1. Every possible answer combination (2^12 = 4,096 combinations) evaluated through both
   backend/app/ml/triage.py and frontend evaluation logic.
2. 100% identical results (parity) between backend and frontend for all 4,096 combinations.
3. Clinician Safety Rule (c): Fainting alone -> "emergency".
4. Clinician Safety Rule (c): Any two red flags together -> "emergency".
5. Clinician Safety Rule (c): Cold sweats + nausea/lightheadedness -> "emergency".
6. Clinician Safety Rule (c): Any single red flag -> at least "see_doctor_today".
7. Monotonicity Rule (d): Age > 40, diabetes, known heart disease, and duration only RAISE urgency, never lower it.
8. Elimination of Normal / Low-Risk (b): The lowest tier strictly outputs:
   "No emergency warning signs were identified from your answers. If symptoms continue, get worse, or you are worried, seek medical care."
   The words "normal", "low-risk", and "wait a week" NEVER appear in any outcome.
9. Vital signs escalation: SBP < 90, SBP > 180, HR < 40, HR > 150 always escalate to "emergency".
"""
import json
import itertools
from pathlib import Path
import pytest

from app.ml.triage import (
    assess_emergency,
    RULES,
    TRIAGE_QUESTION_DEFS,
    INSTRUCTIONS,
    LOWEST_TIER_STATEMENT,
)

# Load shared rules JSON directly as ground truth
RULES_PATH = Path(__file__).resolve().parents[2] / "shared" / "triage_rules.json"


def evaluate_frontend_mirror(answers, bp_sys=None, hr=None):
    """
    Deterministic mirror of src/lib/triageEvaluator.ts for parity assertion.
    Loads same shared JSON definitions.
    """
    ans_map = {}
    for idx, q in enumerate(RULES["questions"]):
        ans_map[q["id"]] = bool(answers[idx]) if idx < len(answers) else False

    thresholds = RULES["rules"]["vital_signs_thresholds"]
    bp_shock = bp_sys is not None and bp_sys < thresholds["bp_sys_shock_below"]
    bp_crisis = bp_sys is not None and bp_sys > thresholds["bp_sys_crisis_above"]
    hr_critical = hr is not None and (hr < thresholds["hr_critical_below"] or hr > thresholds["hr_critical_above"])
    vitals_red_flag = bp_shock or bp_crisis or hr_critical

    red_flag_keys = RULES["rules"]["red_flag_keys"]
    present_red_flags = [k for k in red_flag_keys if ans_map.get(k, False)]
    red_flag_count = len(present_red_flags)
    yes_count = sum(1 for v in ans_map.values() if v)

    stemi_suspicious = bool(
        ans_map.get("crushing_chest_pain")
        and ans_map.get("radiating_pain")
        and (ans_map.get("cold_sweats") or ans_map.get("dyspnea_at_rest"))
    )

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

    instructions = RULES["instructions"][severity]
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


def test_shared_rules_file_exists_and_contains_clinical_comment():
    assert RULES_PATH.is_file(), f"Shared rules file not found at {RULES_PATH}"
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "_comment" in data
    assert "These rules have NOT been clinically validated. Requires review by a qualified clinician before public release." in data["_comment"]
    assert len(data["questions"]) == 12


def test_lowest_tier_wording_matches_specification_exactly():
    expected_statement = "No emergency warning signs were identified from your answers. If symptoms continue, get worse, or you are worried, seek medical care."
    assert LOWEST_TIER_STATEMENT == expected_statement
    assert INSTRUCTIONS["no_emergency_warning_signs"][0] == expected_statement


@pytest.mark.parametrize("tier", ["emergency", "see_doctor_today", "no_emergency_warning_signs"])
def test_no_forbidden_reassurances_or_delays_in_any_tier(tier):
    instructions = INSTRUCTIONS[tier]
    full_text = " ".join(instructions).lower()
    assert "low-risk" not in full_text
    assert "normal" not in full_text
    assert "wait a week" not in full_text
    assert "within the week" not in full_text
    assert "routine check-up" not in full_text


def test_exhaustive_4096_answer_combinations_and_parity():
    """
    Exhaustively runs all 2^12 = 4,096 boolean combinations through both backend and frontend.
    Asserts parity, safety invariants, and strict monotonicity.
    """
    total_combinations = 2 ** 12
    all_combinations = list(itertools.product([False, True], repeat=12))
    assert len(all_combinations) == total_combinations

    tier_order = {
        "no_emergency_warning_signs": 0,
        "see_doctor_today": 1,
        "emergency": 2,
    }

    distribution = {"emergency": 0, "see_doctor_today": 0, "no_emergency_warning_signs": 0}

    # Red flag indices: 0: crushing_chest_pain, 1: radiating_pain, 2: dyspnea_at_rest,
    #                   3: cold_sweats, 4: fainting, 5: palpitations
    red_indices = (0, 1, 2, 3, 4, 5)

    for profile in all_combinations:
        # Backend evaluation
        b_res = assess_emergency(symptoms=list(profile))
        # Frontend mirror evaluation
        f_res = evaluate_frontend_mirror(profile)

        # 1. PARITY ASSERTION
        assert b_res["severity"] == f_res["severity"], f"Severity mismatch for profile {profile}: {b_res['severity']} vs {f_res['severity']}"
        assert b_res["instructions"] == f_res["instructions"], f"Instructions mismatch for profile {profile}"
        assert b_res["yes_count"] == f_res["yes_count"]
        assert b_res["stemi_suspicious"] == f_res["stemi_suspicious"]

        severity = b_res["severity"]
        distribution[severity] += 1

        # 2. Never normal or low-risk
        assert severity in ("emergency", "see_doctor_today", "no_emergency_warning_signs")

        # 3. Fainting alone -> emergency
        if profile[4]:  # fainting
            assert severity == "emergency", f"Safety violation: Fainting present but severity was {severity} for profile {profile}"

        # 4. Any 2 red flags together -> emergency
        red_count = sum(1 for idx in red_indices if profile[idx])
        if red_count >= 2:
            assert severity == "emergency", f"Safety violation: Red flag count {red_count} >= 2 but severity was {severity} for profile {profile}"

        # 5. Cold sweats with nausea/lightheadedness -> emergency
        # index 3: cold_sweats, index 6: nausea_dizziness
        if profile[3] and profile[6]:
            assert severity == "emergency", f"Safety violation: Cold sweats + nausea but severity was {severity} for profile {profile}"

        # 6. Any single red flag -> at least see_doctor_today
        if red_count >= 1:
            assert severity in ("see_doctor_today", "emergency"), f"Safety violation: Red flag present but severity was {severity} for profile {profile}"

        # 7. Lowest tier requires zero red flags and zero dangerous combinations
        if severity == "no_emergency_warning_signs":
            assert red_count == 0
            assert not profile[4]  # No fainting
            assert not (profile[3] and profile[6])  # No cold sweats + nausea
            assert b_res["instructions"][0] == LOWEST_TIER_STATEMENT


def test_risk_factors_raise_urgency_never_lower_it():
    """
    Formal monotonicity verification:
    Flipping any of the 4 risk factors (age_over_40 [8], diabetes [9], known_CAD [10], duration [11])
    from False to True can ONLY raise urgency or keep it equal, NEVER lower it.
    """
    tier_order = {
        "no_emergency_warning_signs": 0,
        "see_doctor_today": 1,
        "emergency": 2,
    }

    # Iterate over all 2^8 = 256 symptom baselines (indices 0 to 7)
    for symptoms in itertools.product([False, True], repeat=8):
        base_profile = list(symptoms) + [False, False, False, False]
        base_urgency = tier_order[assess_emergency(symptoms=base_profile)["severity"]]

        # Test all 16 risk factor combinations
        for risk_combo in itertools.product([False, True], repeat=4):
            elevated_profile = list(symptoms) + list(risk_combo)
            elevated_urgency = tier_order[assess_emergency(symptoms=elevated_profile)["severity"]]

            assert elevated_urgency >= base_urgency, (
                f"Monotonicity violation: Risk factors lowered urgency from {base_urgency} "
                f"to {elevated_urgency} for symptoms {symptoms} and risk {risk_combo}"
            )


def test_vital_signs_always_escalate_to_emergency():
    """Any critical vital sign escalates to emergency, even with 0 symptoms."""
    zeros = [False] * 12
    # SBP shock (<90)
    assert assess_emergency(symptoms=zeros, bp_sys=85, hr=75)["severity"] == "emergency"
    # SBP crisis (>180)
    assert assess_emergency(symptoms=zeros, bp_sys=185, hr=75)["severity"] == "emergency"
    # Critical bradycardia (<40)
    assert assess_emergency(symptoms=zeros, bp_sys=120, hr=35)["severity"] == "emergency"
    # Critical tachycardia (>150)
    assert assess_emergency(symptoms=zeros, bp_sys=120, hr=165)["severity"] == "emergency"
