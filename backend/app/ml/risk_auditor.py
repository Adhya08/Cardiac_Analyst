import json
from typing import Dict, List, Any, Optional

class RiskAuditor:
    """
    Clinical Audit & Model Correction AI.
    Reviews ML model outputs against medical logic to detect underestimations or logical failures.
    """

    def __init__(self):
        pass

    def audit(self, inputs: Dict[str, Any], profile: Dict[str, Any], model_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audit the risk prediction and detect discrepancies.
        """
        issues = []
        root_causes = []
        fixes = []
        is_model_wrong = False
        severity = "low"
        confidence = "medium"

        # ── 1. Extract values
        age = profile.get("age", 50)
        sbp = inputs.get("bp_sys", 120)
        glucose = inputs.get("glucose", 100)
        chol = inputs.get("cholesterol", 200)
        
        lgbm_prob = model_outputs.get("lgbm_probability", 0)
        fram_risk = model_outputs.get("framingham_risk", 0)
        final_risk = model_outputs.get("risk_score", 0)
        shap_values = model_outputs.get("shap_top5", [])

        # ── 2. Clinical Sanity Check
        expected_risk = "Low"
        if sbp > 180 or glucose > 200 or age > 75:
            expected_risk = "Critical"
        elif sbp > 150 or glucose > 150 or age > 65:
            expected_risk = "High"
        elif sbp > 135 or glucose > 120:
            expected_risk = "Moderate"

        # ── 3. Detect Dangerous Underestimation
        if expected_risk in ["High", "Critical"] and final_risk < 15:
            is_model_wrong = True
            severity = "high"
            issues.append(f"Model outputs '{model_outputs['risk_tier']}' despite critical markers (SBP: {sbp}, Glucose: {glucose}).")
            root_causes.append("Model blending problem: Framingham weighting may be diluting acute LightGBM signals.")
            fixes.append("Increase LightGBM weighting in the ensemble when SBP > 160 or Glucose > 180.")
            fixes.append("Add a rule-based override (High Risk) for Hypertensive Crisis thresholds.")

        # ── 4. SHAP Direction Validation
        for factor in shap_values:
            feat = factor.get("feature", "").lower()
            direction = factor.get("direction")
            
            # Glucose should not decrease risk if it's high
            if "glucose" in feat or "sugar" in feat:
                if glucose > 126 and direction == "negative":
                    is_model_wrong = True
                    issues.append("Inverse logic detected: High glucose is incorrectly reducing risk score.")
                    root_causes.append("Feature encoding issue or non-monotonic tree splits.")
                    fixes.append("Normalize glucose using log scale to reduce outlier skew.")
                    fixes.append("Enforce Monotonic Constraints on Glucose features in LightGBM params.")

            # Same for BP
            if "blood pressure" in feat or "sbp" in feat:
                if sbp > 140 and direction == "negative":
                    is_model_wrong = True
                    issues.append("Inverse logic detected: High blood pressure is reducing risk score.")
                    root_causes.append("SHAP miscalculation or data leakage from medication usage.")
                    fixes.append("Check for 'treatment' feature leakage in training data.")

        # ── 5. Confidence Assessment
        if is_model_wrong:
            confidence = "high"
        
        return {
            "expected_risk": expected_risk,
            "model_risk": model_outputs.get("risk_tier", "Unknown"),
            "is_model_wrong": is_model_wrong,
            "severity": severity,
            "issues_detected": issues,
            "root_causes": root_causes,
            "fixes": fixes,
            "confidence": confidence
        }

if __name__ == "__main__":
    # Test case
    auditor = RiskAuditor()
    test_inputs = {"bp_sys": 190, "glucose": 250}
    test_profile = {"age": 70}
    test_outputs = {
        "risk_score": 8.5,
        "risk_tier": "Low",
        "lgbm_probability": 0.1,
        "framingham_risk": 5.0,
        "shap_top5": [
            {"feature": "Fasting Blood Sugar", "direction": "negative", "impact": 0.5}
        ]
    }
    print(json.dumps(auditor.audit(test_inputs, test_profile, test_outputs), indent=2))
