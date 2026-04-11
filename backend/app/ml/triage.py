"""
Emergency Triage Engine
------------------------
Rule-based triage using NICE CG95 guidelines + ACC/AHA STEMI criteria.
Classifies patient urgency: normal | see_doctor | emergency.

Clinical References:
- NICE CG95 (2010): Chest pain of recent onset assessment and diagnosis.
- ACC/AHA 2013 STEMI Guidelines: O'Gara et al., JACC 2013;61:e78-e140.
- SIGN 93 (2016): Acute coronary syndromes.
"""
from typing import List, Dict, Any


# ── The 8 triage questions shown to user (in exact order)
TRIAGE_QUESTIONS = [
    "Are you experiencing crushing or squeezing chest pain?",           # Q0
    "Does the pain radiate to your left arm, jaw, or shoulder?",       # Q1
    "Are you short of breath even while resting?",                     # Q2
    "Are you feeling nauseous or lightheaded / dizzy?",                # Q3
    "Is your heart racing or beating irregularly?",                    # Q4
    "Are you sweating profusely or having cold sweats?",               # Q5
    "Have you fainted or nearly fainted recently?",                    # Q6
    "Is your vision blurry or are you confused?",                      # Q7
]

# ── High-risk symptom combinations (NICE CG95 + ACC/AHA)
# Each set: if ALL indices in the set are YES → emergency
EMERGENCY_COMBOS = [
    {0, 1, 5},   # Chest pain + radiation + diaphoresis (STEMI cardinal triad)
    {0, 1, 2},   # Chest pain + radiation + dyspnea (ACS)
    {0, 2, 5},   # Chest pain + dyspnea + diaphoresis (STEMI/HF)
    {0, 4, 5},   # Chest pain + palpitations + diaphoresis (VT / ACS)
    {6},         # Syncope alone (VT, complete heart block, AS)
    {0, 7},      # Chest pain + confusion (cardiogenic shock)
]

# ── If ≥ 5 YES answers → emergency regardless
EMERGENCY_THRESHOLD = 5

# ── Instructions by severity
INSTRUCTIONS = {
    "emergency": [
        "🚨 Call 112 IMMEDIATELY. Do not wait.",
        "Sit or lie down. Do NOT try to drive yourself.",
        "Unlock your front door for the ambulance crew.",
        "If available and not allergic: chew ONE aspirin (75–325 mg) right now.",
        "Keep this screen visible to show emergency responders.",
        "Send your location to a trusted family member.",
    ],
    "see_doctor": [
        "Visit a cardiologist or emergency department within 24 hours.",
        "Rest completely — avoid physical exertion.",
        "If symptoms worsen at any point, call 112 immediately.",
        "Do not drive — arrange transport with someone else.",
        "Keep a log of your symptoms: onset time, severity (1-10), duration.",
    ],
    "normal": [
        "Your symptoms appear low-risk at this time.",
        "Monitor yourself and rest if you feel unwell.",
        "Maintain your daily vitals log to detect trends.",
        "Schedule a routine check-up with your doctor within the week.",
        "Call 112 if any new or worsening symptoms develop.",
    ],
}


def assess_emergency(
    symptoms: List[bool],
    bp_sys: int = None,
    hr: int = None,
) -> Dict[str, Any]:
    """
    Triage assessment based on NICE CG95 + ACC/AHA guidelines.

    Args:
        symptoms:  List of 8 boolean answers (True = YES).
        bp_sys:    Current systolic BP (optional).
        hr:        Current heart rate (optional).

    Returns:
        dict with severity, confidence, risk_score, instructions, etc.
    """
    yes_indices = {i for i, v in enumerate(symptoms) if v}
    yes_count = len(yes_indices)

    # ── Vital signs red flags
    bp_shock = bp_sys is not None and bp_sys < 90
    bp_hypertensive_crisis = bp_sys is not None and bp_sys > 180
    hr_critical = hr is not None and (hr < 40 or hr > 150)
    vitals_red_flag = bp_shock or bp_hypertensive_crisis or hr_critical

    # ── STEMI-specific rule: Q0 + Q1 required for classic STEMI suspicion
    stemi_suspicious = 0 in yes_indices and 1 in yes_indices

    # ── Check emergency combos
    combo_triggered = any(combo.issubset(yes_indices) for combo in EMERGENCY_COMBOS)

    # ── Determine severity
    if combo_triggered or yes_count >= EMERGENCY_THRESHOLD or vitals_red_flag:
        severity = "emergency"
        if combo_triggered and stemi_suspicious:
            confidence_base = 0.95
        elif combo_triggered:
            confidence_base = 0.88
        elif vitals_red_flag:
            confidence_base = 0.90
        else:
            confidence_base = 0.80
        confidence = min(0.99, confidence_base + yes_count * 0.01)
        risk_score = min(99.9, 75 + yes_count * 3.0 + (10 if vitals_red_flag else 0))

    elif yes_count >= 3 or (0 in yes_indices) or (2 in yes_indices) or (4 in yes_indices and 6 in yes_indices):
        # 0: Chest pain, 2: Shortness of breath at rest, 4+6: Racing heart + syncope
        severity = "see_doctor"
        confidence = 0.68 + yes_count * 0.04
        risk_score = 35 + yes_count * 5.0

    else:
        severity = "normal"
        confidence = 0.75 + (1 - yes_count / 8) * 0.20
        risk_score = max(2.0, 5.0 + yes_count * 4.5)

    return {
        "severity": severity,
        "confidence": round(float(confidence), 3),
        "risk_score": round(float(risk_score), 1),
        "yes_count": yes_count,
        "stemi_suspicious": stemi_suspicious,
        "combo_triggered": combo_triggered,
        "vitals_red_flag": vitals_red_flag,
        "instructions": INSTRUCTIONS[severity],
    }
