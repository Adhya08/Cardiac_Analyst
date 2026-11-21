"""
Deterministic Structured Report Generator
=========================================
Generates complete clinical and patient-friendly reports from validated local model
findings without any dependence on external LLMs or third-party APIs.

Follows strict medical AI safety rules:
1. Purely deterministic logic and pre-validated medical dictionaries (zero hallucination).
2. Bilingual generation (English and Hindi).
3. Directly reflects model probabilities, thresholds, intervals, and urgency tiers.
"""

from typing import Dict, Any, List, Optional

DIAGNOSTIC_EXPLAINERS = {
    "NORM": {
        "title_en": "Normal Electrical Pattern",
        "title_hi": "सामान्य हृदय ताल (नॉर्मल ईसीजी)",
        "analogy_en": "The electrical rhythm of the heart is smooth, orderly, and firing within standard physiological limits.",
        "analogy_hi": "दिल की विद्युत ताल सामान्य, नियमित और स्वस्थ सीमाओं के भीतर काम कर रही है।",
        "details_en": "No acute repolarization abnormalities, conduction blocks, or ischemic patterns were detected.",
        "details_hi": "कोई तीव्र असामान्यता, रुकावट या इस्केमिक संकेत नहीं पाए गए हैं।",
        "action_en": "Continue routine healthy lifestyle habits and scheduled medical checkups.",
        "action_hi": "स्वस्थ जीवनशैली बनाए रखें और नियमित स्वास्थ्य जांच कराते रहें।",
    },
    "MI": {
        "title_en": "Myocardial Infarction / Ischemia Pattern",
        "title_hi": "हृदय की मांसपेशी में रक्त प्रवाह की कमी / हार्ट अटैक का संकेत (MI)",
        "analogy_en": "Electrical recordings show potential acute or recent blood flow impairment to a region of the heart muscle.",
        "analogy_hi": "ईसीजी से पता चलता है कि दिल की मांसपेशियों को पर्याप्त रक्त और ऑक्सीजन नहीं मिल पा रही हो सकती है।",
        "details_en": "Critical findings detected. Pathological Q-waves or significant ST segment deviations were observed.",
        "details_hi": "गंभीर संकेत मिले हैं। एसटी-सेगमेंट या क्यू-वेव में असामान्य बदलाव देखे गए हैं।",
        "action_en": "URGENT: Cease physical exertion, sit or lie down, call emergency services (112) or go to the nearest hospital immediately.",
        "action_hi": "अति आवश्यक: तुरंत आराम से बैठें, कोई श्रम न करें और तत्काल 112 पर कॉल करें या नजदीकी आपातकालीन अस्पताल जाएं।",
    },
    "STTC": {
        "title_en": "ST/T-Wave Changes (Repolarization Changes)",
        "title_hi": "एसटी/टी-वेव परिवर्तन (दिल की रिकवरी में बदलाव)",
        "analogy_en": "The heart's electrical recharging cycle between beats differs slightly from standard baseline patterns.",
        "analogy_hi": "हर धड़कन के बाद दिल के इलेक्ट्रिकल रीचार्ज होने का चरण थोड़ा बदला हुआ है।",
        "details_en": "Non-specific ST segment or T-wave elevation/depression observed. May reflect transient ischemia, strain, or electrolyte shifts.",
        "details_hi": "एसटी या टी-वेव में बदलाव देखे गए हैं, जो तनाव, मामूली रक्त प्रवाह में बदलाव या इलेक्ट्रोलाइट्स के कारण हो सकता है।",
        "action_en": "Rest quietly, avoid intense exercise, and schedule a medical consultation within 24–48 hours.",
        "action_hi": "आराम करें, भारी काम से बचें और 24-48 घंटों के भीतर डॉक्टर से परामर्श लें।",
    },
    "CD": {
        "title_en": "Conduction Disturbance / Block",
        "title_hi": "कंडक्शन डिले / इलेक्ट्रिकल सिग्नल में देरी",
        "analogy_en": "Electrical signals coordinating heart contraction are traveling through alternative or slowed pathways.",
        "analogy_hi": "दिल को धड़कने का संकेत देने वाले कुदरती विद्युत मार्ग में थोड़ी देरी या घुमाव देखा गया है।",
        "details_en": "Widened QRS complex or prolonged PR interval consistent with bundle branch block or fascicular delay.",
        "details_hi": "क्यूआरएस कॉम्प्लेक्स या पीआर इंटरवल में फैलाव देखा गया है जो बंडल ब्रांच ब्लॉक से मेल खाता है।",
        "action_en": "Consult a cardiologist for clinical correlation. If feeling faint or dizzy, seek immediate medical attention.",
        "action_hi": "कार्डियोलॉजिस्ट से जांच कराएं। यदि चक्कर या बेहोशी महसूस हो तो तुरंत आपातकालीन सहायता लें।",
    },
    "HYP": {
        "title_en": "Ventricular Hypertrophy (Heart Wall Thickening)",
        "title_hi": "दिल की दीवार का मोटा होना (हाइपरट्रॉफी)",
        "analogy_en": "The muscular wall of the heart has thickened, commonly caused by prolonged high blood pressure or aortic resistance.",
        "analogy_hi": "दिल की मांसपेशी की दीवारें सामान्य से मोटी हो गई हैं, जो अक्सर लंबे समय से हाई बीपी के कारण होता है।",
        "details_en": "High voltage QRS amplitudes meeting Sokolow-Lyon or Cornell voltage criteria.",
        "details_hi": "उच्च वोल्टेज आयाम दिल के वेंट्रिकल के आकार में वृद्धि का संकेत देते हैं।",
        "action_en": "Monitor blood pressure regularly, take prescribed antihypertensive medications, and consult your physician.",
        "action_hi": "नियमित रूप से बीपी मापें, निर्धारित दवाएं लें और अपने डॉक्टर से परामर्श लें।",
    },
}

STANDARD_DISCLAIMER = (
    "Cardiac Analyst is an educational research prototype and NOT a certified medical device. "
    "This report is generated algorithmically for clinician reference and must never replace qualified clinical judgement."
)


def generate_deterministic_report(ecg_analysis: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
    """
    Generate a 100% deterministic, grounded report from validated ECG analysis data.
    """
    status = ecg_analysis.get("status", "ok")
    urgency = ecg_analysis.get("urgency", "routine")
    is_emergency = urgency == "emergency"
    
    # 1. Handle unreadable or failed analysis
    if status == "analysis_unavailable":
        abstain_reason = ecg_analysis.get("abstain_reason", "Signal quality unusable or corrupted.")
        summary_en = f"ECG Analysis Unavailable: {abstain_reason} Please acquire a clean 10-second 12-lead recording."
        summary_hi = "ईसीजी विश्लेषण अनुपलब्ध: सिग्नल गुणवत्ता अस्पष्ट है। कृपया एक साफ 12-लीड ईसीजी रिकॉर्डिंग पुनः प्राप्त करें।"
        return {
            "summary_en": summary_en,
            "summary_hi": summary_hi,
            "key_points": [
                "Analysis could not be completed reliably due to signal noise or flatline.",
                "Zero automated diagnoses or probabilities were generated.",
                "Ensure proper electrode skin contact and repeat the recording."
            ],
            "next_step": "Repeat the ECG recording with proper electrode adhesion.",
            "urgency": "unavailable",
            "is_emergency": False,
            "detected_conditions": [],
            "metrics_summary": {},
            "disclaimer": STANDARD_DISCLAIMER,
            "source": "deterministic_engine"
        }

    # 2. Extract detected conditions
    conditions = ecg_analysis.get("conditions", [])
    detected = [c for c in conditions if c.get("detected") is True]
    detected_codes = [c.get("code") for c in detected if c.get("code")]
    
    # Fallback to model_scores or top condition if conditions list is empty
    if not detected_codes:
        model_scores = ecg_analysis.get("model_scores", {})
        for code, score in model_scores.items():
            if code != "NORM" and score >= 0.50:
                detected_codes.append(code)

    if not detected_codes:
        detected_codes = ["NORM"]

    # 3. Format clinical metrics
    hr = ecg_analysis.get("heart_rate_bpm")
    rhythm = ecg_analysis.get("rhythm", "Unknown Rhythm")
    pr = ecg_analysis.get("pr_interval_ms")
    qrs = ecg_analysis.get("qrs_duration_ms")
    qtc = ecg_analysis.get("qtc_ms")
    ste_leads = ecg_analysis.get("st_elevation_leads", [])
    std_leads = ecg_analysis.get("st_depression_leads", [])

    metrics_bullets = []
    if hr is not None:
        metrics_bullets.append(f"Heart Rate: {hr} bpm ({rhythm})")
    if pr is not None:
        metrics_bullets.append(f"PR Interval: {pr} ms")
    if qrs is not None:
        metrics_bullets.append(f"QRS Duration: {qrs} ms")
    if qtc is not None:
        metrics_bullets.append(f"QTc (Bazett): {qtc} ms")
    if ste_leads:
        metrics_bullets.append(f"ST Elevation Leads: {', '.join(ste_leads)}")
    if std_leads:
        metrics_bullets.append(f"ST Depression Leads: {', '.join(std_leads)}")

    # 4. Synthesize English & Hindi Narrative
    primary_code = "MI" if "MI" in detected_codes else detected_codes[0]
    exp = DIAGNOSTIC_EXPLAINERS.get(primary_code, DIAGNOSTIC_EXPLAINERS["NORM"])

    summary_en_parts = []
    summary_hi_parts = []

    # Title & main message
    summary_en_parts.append(f"Primary Finding: {exp['title_en']}.")
    summary_en_parts.append(exp["analogy_en"])
    summary_en_parts.append(exp["details_en"])

    summary_hi_parts.append(f"मुख्य निष्कर्ष: {exp['title_hi']}।")
    summary_hi_parts.append(exp["analogy_hi"])
    summary_hi_parts.append(exp["details_hi"])

    # If multiple abnormalities detected
    if len(detected_codes) > 1 and "NORM" not in detected_codes:
        secondary_codes = [c for c in detected_codes if c != primary_code]
        secondary_names_en = [DIAGNOSTIC_EXPLAINERS.get(c, {}).get("title_en", c) for c in secondary_codes]
        secondary_names_hi = [DIAGNOSTIC_EXPLAINERS.get(c, {}).get("title_hi", c) for c in secondary_codes]
        summary_en_parts.append(f"Additional co-occurring patterns identified: {'; '.join(secondary_names_en)}.")
        summary_hi_parts.append(f"अतिरिक्त सहवर्ती लक्षण: {'; '.join(secondary_names_hi)}।")

    # 5. Build key takeaways list
    key_points = []
    for code in detected_codes:
        c_exp = DIAGNOSTIC_EXPLAINERS.get(code, DIAGNOSTIC_EXPLAINERS["NORM"])
        score_val = ecg_analysis.get("model_scores", {}).get(code)
        score_str = f" (Confidence: {score_val:.1%})" if score_val is not None else ""
        key_points.append(f"{c_exp['title_en']}{score_str}: {c_exp['details_en']}")

    if metrics_bullets:
        key_points.append("Measured Electrophysiology: " + "; ".join(metrics_bullets[:3]))

    # 6. Recommended next step based on urgency
    if urgency == "emergency":
        next_step_en = "URGENT: Call 112 or proceed to the nearest emergency cardiac catheterization facility immediately."
        next_step_hi = "अति आवश्यक: तुरंत 112 पर कॉल करें या निकटतम आपातकालीन अस्पताल जाएं।"
    elif urgency == "see_doctor_today":
        next_step_en = "Consult a cardiologist or qualified physician today for clinical evaluation and confirmation."
        next_step_hi = "आज ही किसी हृदय रोग विशेषज्ञ से परामर्श लें।"
    else:
        next_step_en = exp["action_en"]
        next_step_hi = exp["action_hi"]

    key_points.append(f"Next Action: {next_step_en}")

    return {
        "summary_en": " ".join(summary_en_parts),
        "summary_hi": " ".join(summary_hi_parts),
        "key_points": key_points,
        "next_step": next_step_en,
        "next_step_hi": next_step_hi,
        "urgency": urgency,
        "is_emergency": is_emergency,
        "detected_conditions": detected_codes,
        "metrics_summary": {
            "heart_rate_bpm": hr,
            "rhythm": rhythm,
            "pr_interval_ms": pr,
            "qrs_duration_ms": qrs,
            "qtc_ms": qtc,
            "st_elevation_leads": ste_leads,
            "st_depression_leads": std_leads,
        },
        "disclaimer": STANDARD_DISCLAIMER,
        "source": "deterministic_engine"
    }


def generate_deterministic_advice(vitals: Dict[str, Any], risk_tier: str, ecg_urgency: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate deterministic lifestyle and vitals guidance based on clinical rules.
    """
    bp_sys = vitals.get("bp_sys")
    bp_dia = vitals.get("bp_dia")
    hr = vitals.get("hr")
    glucose = vitals.get("glucose")
    cholesterol = vitals.get("cholesterol")

    do_list = []
    avoid_list = []

    if bp_sys and bp_sys >= 140:
        do_list.append(f"Systolic BP is elevated ({bp_sys} mmHg). Rest quietly and recheck in 15 minutes.")
        avoid_list.append("Avoid caffeinated beverages, excess sodium (> 2g/day), and high-stress situations.")

    if glucose and glucose >= 140:
        do_list.append(f"Monitor blood sugar regularly (last recorded {glucose} mg/dL).")
        avoid_list.append("Avoid refined sugars, sweetened beverages, and simple carbohydrates.")

    # General healthy cardiovascular habits
    do_list.extend([
        "Maintain regular daily hydration (1.5 - 2 liters unless fluid restricted)",
        "Engage in moderate-intensity walking (30 mins/day) if permitted by physician",
        "Record morning and evening blood pressure at resting state"
    ])
    avoid_list.extend([
        "Avoid sudden unconditioned strenuous physical exertion",
        "Avoid skipping prescribed cardiovascular medications"
    ])

    if ecg_urgency == "emergency":
        follow_up = "CRITICAL: Urgent medical evaluation required immediately. Do not delay."
    elif ecg_urgency == "see_doctor_today" or risk_tier == "Elevated":
        follow_up = "Schedule a clinical cardiology consultation within 24–48 hours."
    else:
        follow_up = "Continue periodic routine monitoring and annual preventive checkups."

    advice_text = (
        f"Your recorded vitals place your cardiovascular screening tier at '{risk_tier}'. "
        f"Follow evidence-based lifestyle modifications, adhere to prescribed regimens, "
        f"and discuss these parameters with your healthcare provider."
    )

    return {
        "advice": advice_text,
        "do_list": do_list[:4],
        "avoid_list": avoid_list[:4],
        "follow_up": follow_up,
        "risk_tier": risk_tier,
        "source": "deterministic_engine"
    }
