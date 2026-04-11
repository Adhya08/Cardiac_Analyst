import json
from typing import Dict, List, Any, Optional

class VitalsValidator:
    """
    Clinical Data Validation & Correction Engine.
    Detects unrealistic/dangerous health inputs and suggests medically plausible corrections.
    """

    def __init__(self):
        # ── Global Validation Thresholds
        self.rules = {
            "height": {"min": 130, "max": 220},
            "weight": {"min": 30, "max": 200},
            "bmi":    {"min": 10, "max": 60},
            "sbp":    {"min": 70, "max": 250},
            "dbp":    {"min": 40, "max": 150},
            "spo2":   {"min": 70, "max": 100},
            "hr":     {"min": 30, "max": 200},
        }

    def validate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate inputs and return structured correction report.
        """
        issues = []
        insights = []
        status = "valid"
        confidence = "high"
        
        # ── 1. Basic Range Validation
        corrected = inputs.copy()
        
        # Height
        h = inputs.get("height_cm")
        if h:
            if h < self.rules["height"]["min"]:
                issues.append(f"Height ({h}cm) is below physiological minimum for an adult.")
                corrected["height_cm"] = 160  # Suggested fallback
                insights.append("Height seems too low. Did you mean 160 cm?")
                status = "warning"
            elif h > self.rules["height"]["max"]:
                issues.append(f"Height ({h}cm) is above physiological maximum.")
                corrected["height_cm"] = 175
                insights.append("Height is unusually high. Suggested correction to 175cm.")
                status = "warning"

        # Weight
        w = inputs.get("weight")
        if w:
            if w < self.rules["weight"]["min"]:
                issues.append(f"Weight ({w}kg) is critically low for a clinical assessment.")
                corrected["weight"] = 65
                insights.append("Weight seems unrealistic. Suggested average 65kg.")
                status = "warning"
            elif w > self.rules["weight"]["max"]:
                issues.append(f"Weight ({w}kg) exceeds clinical monitoring thresholds (200kg+).")
                status = "warning"

        # BMI Derived Logic
        if h and w:
            bmi = w / ((h / 100) ** 2)
            if bmi < self.rules["bmi"]["min"]:
                issues.append(f"Calculated BMI ({bmi:.1f}) is below survival threshold (10).")
                status = "invalid"
                confidence = "medium"
            elif bmi > self.rules["bmi"]["max"]:
                issues.append(f"Calculated BMI ({bmi:.1f}) indicates extreme morbid obesity (>60).")
                status = "warning"

        # Blood Pressure Plausibility
        sbp = inputs.get("bp_sys")
        dbp = inputs.get("bp_dia")
        if sbp and dbp:
            if dbp >= sbp:
                issues.append("Diastolic BP cannot be higher than or equal to Systolic BP.")
                status = "invalid"
            if sbp < self.rules["sbp"]["min"]:
                issues.append(f"Systolic BP ({sbp}) is too low (Hypotensive Shock range).")
                status = "warning"
            if dbp < self.rules["dbp"]["min"]:
                issues.append(f"Diastolic BP ({dbp}) is below plausible threshold.")
                status = "warning"

        # Vitals
        spo2 = inputs.get("spo2")
        if spo2 and (spo2 < self.rules["spo2"]["min"]):
            issues.append(f"SpO2 ({spo2}%) indicates critical respiratory failure.")
            status = "warning"

        hr = inputs.get("hr")
        if hr and (hr < self.rules["hr"]["min"] or hr > self.rules["hr"]["max"]):
            issues.append(f"Heart Rate ({hr}) is outside plausible range (30-200).")
            status = "warning"

        # ── Final Report
        return {
            "status": status,
            "issues": issues,
            "corrected_values": corrected,
            "insights": insights,
            "confidence": confidence,
            "derived_bmi": round(w / ((h / 100) ** 2), 1) if h and w else None
        }

if __name__ == "__main__":
    # Test case
    validator = VitalsValidator()
    test_data = {
        "height_cm": 100,
        "weight": 70,
        "bp_sys": 120,
        "bp_dia": 130,
        "hr": 75,
        "spo2": 98
    }
    print(json.dumps(validator.validate(test_data), indent=2))
