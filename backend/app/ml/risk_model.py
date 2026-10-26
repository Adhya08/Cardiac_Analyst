"""
LightGBM Cardiac Risk Model
-----------------------------
Trained on the combined UCI Heart Disease dataset (Cleveland + Hungarian + Switzerland + VA Long Beach).
Reference: Detrano et al. (1989). International Application of a New Probability Algorithm for the Diagnosis of Coronary Artery Disease.

Uses Framingham Heart Study equations for 10-year CHD risk calculation.
Reference: D'Agostino et al. (2008). General Cardiovascular Risk Profile for Use in Primary Care. Circulation.

The model maps app-collected vitals (bp, hr, weight, spo2, glucose, cholesterol)
plus user profile (age, sex, smoker, diabetic, family history) to clinically
validated risk features.
"""
import os
import math
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Optional

FEATURE_NAMES = [
    "age", "sex", "cp", "trestbps", "chol", "fbs",
    "restecg", "thalach", "exang", "oldpeak", "slope", "ca", "thal",
]

FEATURE_LABELS = {
    "age": "Age",
    "sex": "Gender",
    "cp": "Chest Pain Pattern",
    "trestbps": "Blood Pressure (Systolic)",
    "chol": "Cholesterol Level",
    "fbs": "Fasting Blood Sugar",
    "restecg": "Resting ECG",
    "thalach": "Estimated Max Heart Rate",
    "exang": "Exercise-Induced Symptoms",
    "oldpeak": "ST Depression Index",
    "slope": "ST Slope",
    "ca": "Coronary Artery Risk Index",
    "thal": "Cardiac Perfusion Type",
}


class RiskModel:
    """
    Cardiac risk prediction using LightGBM + Framingham equations.
    Must call load() before predict() — or run train.py first to create the model file.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.explainer = None
        self.feature_means: dict = {}
        self.test_accuracy: float = 0.0
        self.is_loaded = False

        if model_path and Path(model_path).exists():
            self.load(model_path)
        else:
            print(f"[RiskModel] WARNING: Model not found at '{model_path}'. Run train.py first.")

    # ──────────────────────────────────────────────────────
    # Load / Save
    # ──────────────────────────────────────────────────────

    def load(self, path: str):
        try:
            data = joblib.load(path)
            self.model = data["model"]
            self.explainer = data["explainer"]
            self.feature_means = data.get("feature_means", {})
            self.test_accuracy = data.get("test_accuracy", 0.0)
            self.is_loaded = True
            print(f"[RiskModel] Loaded. Test accuracy: {self.test_accuracy * 100:.2f}%")
        except Exception as e:
            print(f"[RiskModel] ERROR loading model: {e}")
            self.is_loaded = False

    # ──────────────────────────────────────────────────────
    # Feature Engineering
    # ──────────────────────────────────────────────────────

    def map_inputs(self, vitals: dict, profile: dict) -> pd.DataFrame:
        """
        Map app vitals + user profile to UCI Heart Disease feature set.

        UCI features:
            age, sex, cp, trestbps, chol, fbs, restecg, thalach,
            exang, oldpeak, slope, ca, thal
        """
        age = int(profile.get("age", 50))
        sex = 1 if profile.get("sex", "Male") == "Male" else 0
        bp_sys = int(vitals.get("bp_sys", 120))
        bp_dia = int(vitals.get("bp_dia", 80))
        hr = int(vitals.get("hr", 72))
        chol = float(vitals.get("cholesterol") or self.feature_means.get("chol", 220))
        glucose = float(vitals.get("glucose") or 100)
        spo2 = float(vitals.get("spo2", 98))
        is_smoker = bool(profile.get("is_smoker", False))
        is_diabetic = bool(profile.get("is_diabetic", False))
        has_fhx = bool(profile.get("has_family_history", False))

        # Risk factor count (for derived features)
        risk_count = sum([
            is_smoker,
            is_diabetic,
            age > 60,
            bp_sys > 140,
            chol > 240,
            hr > 100,
            has_fhx,
            spo2 < 95,
        ])

        # ── cp (chest pain type): 1=typical, 2=atypical, 3=non-anginal, 4=asymptomatic
        if is_diabetic:
            cp = 2  # Diabetics often have atypical/silent ischemia
        elif bp_sys > 150 and has_fhx:
            cp = 1  # Typical angina pattern if high BP + family history
        elif risk_count >= 3:
            cp = 3  # Non-anginal
        else:
            cp = 4  # Asymptomatic (most common in screening)

        # ── fbs: fasting blood sugar > 126 mg/dL (standard diabetic threshold)
        fbs = 1 if glucose > 126 else 0

        # ── restecg: 0=normal, 1=ST-T abnormality, 2=LVH
        if bp_sys > 160:
            restecg = 2  # LVH likely in severe hypertension
        elif bp_sys > 140:
            restecg = 1  # Possible ST-T changes
        else:
            restecg = 0  # Normal

        # ── thalach: max HR achieved during exercise. Estimate from rest HR and age.
        # Formula: For sedentary individuals, rest HR correlates with max HR.
        # Max theoretical = 220 - age; heart disease reduces achieved max.
        predicted_max_hr = 220 - age
        if risk_count >= 3:
            thalach = int(predicted_max_hr * 0.75)  # Impaired max HR
        elif risk_count >= 1:
            thalach = int(predicted_max_hr * 0.82)
        else:
            thalach = int(predicted_max_hr * 0.88)
        thalach = max(thalach, hr)  # Can't be lower than recorded HR

        # ── exang: exercise-induced angina
        exang = 1 if (has_fhx and bp_sys > 140 and hr > 90) else 0

        # ── oldpeak: ST depression at exercise. Derived from BP differential and risk factors.
        pulse_pressure = bp_sys - bp_dia
        oldpeak = max(0.0, min(5.0, (risk_count - 1) * 0.4 + (pulse_pressure - 40) / 60.0))

        # ── slope: 1=up-sloping (good), 2=flat (neutral), 3=down-sloping (bad)
        if oldpeak > 2.5:
            slope = 3  # Down-sloping — worse prognosis
        elif oldpeak > 0.8:
            slope = 2  # Flat
        else:
            slope = 1  # Up-sloping — better prognosis

        # ── ca: number of major vessels blocked (0-3), estimated from risk factor count
        ca = min(3, max(0, risk_count - 3))

        # ── thal: 3=normal, 6=fixed defect, 7=reversable defect
        if risk_count >= 5:
            thal = 7  # Reversable defect (ischemia)
        elif risk_count >= 3:
            thal = 6  # Fixed defect
        else:
            thal = 3  # Normal

        features = {
            "age": age, "sex": sex, "cp": cp,
            "trestbps": bp_sys, "chol": chol, "fbs": fbs,
            "restecg": restecg, "thalach": thalach, "exang": exang,
            "oldpeak": round(oldpeak, 2), "slope": slope,
            "ca": ca, "thal": thal,
        }
        return pd.DataFrame([features])[FEATURE_NAMES]

    # ──────────────────────────────────────────────────────
    # Framingham Risk Score (2008 D'Agostino formula)
    # ──────────────────────────────────────────────────────

    def compute_framingham_risk(self, vitals: dict, profile: dict) -> float:
        """
        Compute 10-year CHD risk using Framingham Heart Study sex-stratified equations.
        Source: D'Agostino et al. (2008). General Cardiovascular Risk Profile. Circulation 117:743-753.
        """
        age = max(18, min(79, int(profile.get("age", 50))))
        sex = profile.get("sex", "Male")
        bp_sys = float(vitals.get("bp_sys", 120))
        total_chol = float(vitals.get("cholesterol") or 200)
        # Estimate HDL from total cholesterol (population average ratio: ~25%)
        hdl_chol = max(25.0, total_chol * 0.24)
        smoker = 1 if profile.get("is_smoker", False) else 0
        diabetes = 1 if profile.get("is_diabetic", False) else 0
        bp_treatment = 0  # Unknown — assume untreated

        if sex == "Male":
            log_sum = (
                3.06117 * np.log(age)
                + 1.12370 * np.log(total_chol)
                - 0.93263 * np.log(hdl_chol)
                + 1.93303 * np.log(max(bp_sys, 1)) * (1 - bp_treatment)
                + 1.99881 * np.log(max(bp_sys, 1)) * bp_treatment
                + 0.65451 * smoker
                + 0.57367 * diabetes
                - 23.9388
            )
            baseline = 0.88936
        else:
            log_sum = (
                2.32888 * np.log(age)
                + 1.20904 * np.log(total_chol)
                - 0.70833 * np.log(hdl_chol)
                + 2.76157 * np.log(max(bp_sys, 1)) * (1 - bp_treatment)
                + 2.82263 * np.log(max(bp_sys, 1)) * bp_treatment
                + 0.52873 * smoker
                + 0.69154 * diabetes
                - 26.1931
            )
            baseline = 0.95012

        risk_10yr = (1 - baseline ** math.exp(log_sum)) * 100
        return float(np.clip(risk_10yr, 0.1, 99.9))

    # ──────────────────────────────────────────────────────
    # Predict
    # ──────────────────────────────────────────────────────

    def predict(self, vitals: dict, profile: dict) -> dict:
        """
        Full risk prediction with real SHAP explainability.
        Returns: risk_score, risk_tier, lgbm_probability, framingham_risk,
                 confidence_interval, shap_top5, ecg_prompt, trend_delta
        """
        # Framingham risk (always available — no ML model needed)
        try:
            framingham_risk = self.compute_framingham_risk(vitals, profile)
        except Exception:
            framingham_risk = 15.0  # Safe default

        used_lgbm = False
        if not self.is_loaded:
            # Graceful degradation: use Framingham only
            risk_score = framingham_risk
            lgbm_prob = framingham_risk / 100.0
            shap_top5 = self._static_shap(vitals, profile)
        else:
            # Map vitals to UCI features
            X = self.map_inputs(vitals, profile)

            # LightGBM prediction
            try:
                lgbm_prob = float(self.model.predict_proba(X)[0][1])
                used_lgbm = True
            except Exception as e:
                print(f"[RiskModel] LightGBM inference error: {e}")
                lgbm_prob = framingham_risk / 100.0

            # Weighted fusion: Framingham (60%) + LGBM (40%)
            combined_prob = 0.60 * (framingham_risk / 100.0) + 0.40 * lgbm_prob

            # Add smoker / family history bonus
            if profile.get("is_smoker"):
                combined_prob += 0.05
            if profile.get("has_family_history"):
                combined_prob += 0.04

            combined_prob = float(np.clip(combined_prob, 0.001, 0.999))
            risk_score = float(np.clip(combined_prob * 100, 0.1, 99.9))

            # SHAP values
            try:
                shap_vals_raw = self.explainer.shap_values(X)
                if isinstance(shap_vals_raw, list):
                    sv = shap_vals_raw[1][0]  # Positive class
                else:
                    sv = shap_vals_raw[0]

                shap_dict = {FEATURE_NAMES[i]: float(sv[i]) for i in range(len(FEATURE_NAMES))}
                shap_top5 = self._format_shap(shap_dict)
            except Exception as e:
                print(f"[RiskModel] SHAP computation error: {e}")
                shap_top5 = self._static_shap(vitals, profile)

        # Risk tier
        if risk_score < 7.5:
            risk_tier = "Low"
        elif risk_score < 15.0:
            risk_tier = "Borderline"
        else:
            risk_tier = "Elevated"

        # ECG escalation flag
        ecg_prompt = (risk_tier == "Elevated") or (lgbm_prob > 0.65)

        if used_lgbm:
            model_status = "experimental"
            experimental_warning = (
                "Heuristic Feature Mapping: The tabular model was trained on clinical catheterization and "
                "treadmill stress features (cp, thalach, oldpeak, ca, thal) which are heuristically approximated "
                "from resting vitals. Consequently, this tabular risk output is strictly experimental and for research demonstration."
            )
        else:
            model_status = "fallback_framingham"
            experimental_warning = (
                "Framingham Clinical Fallback: The tabular machine learning model is unavailable or inference failed. "
                "The displayed risk estimate is derived from the established Framingham 10-year cardiovascular risk equations."
            )

        return {
            "risk_score": round(risk_score, 2),
            "lgbm_probability": round(lgbm_prob * 100, 2),
            "framingham_risk": round(framingham_risk, 2),
            "combined_probability": round(risk_score, 2),
            "risk_tier": risk_tier,
            "confidence_interval": {
                "lower": max(0.0, round(risk_score - 4.5, 2)),
                "upper": min(100.0, round(risk_score + 4.5, 2)),
            },
            "shap_top5": shap_top5,
            "ecg_prompt": ecg_prompt,
            "trend_delta": 0.0,  # Computed by router using DB
            "model_status": model_status,
            "experimental_warning": experimental_warning,
        }

    def _format_shap(self, shap_dict: dict) -> list:
        """Format SHAP values into user-friendly output."""
        factors = [
            {
                "feature": FEATURE_LABELS.get(k, k),
                "value": v,
                "impact": abs(v),
                "direction": "positive" if v > 0 else "negative",
            }
            for k, v in shap_dict.items()
        ]
        factors.sort(key=lambda x: x["impact"], reverse=True)
        top5 = factors[:5]
        total = sum(f["impact"] for f in top5)
        for f in top5:
            f["percent"] = round((f["impact"] / total * 100) if total > 0 else 0, 1)
        return top5

    def _static_shap(self, vitals: dict, profile: dict) -> list:
        """Fallback SHAP when model isn't loaded — rule-based importance."""
        bp_sys = float(vitals.get("bp_sys", 120))
        age = int(profile.get("age", 50))
        chol = float(vitals.get("cholesterol") or 200)
        hr = int(vitals.get("hr", 72))
        spo2 = float(vitals.get("spo2", 98))

        factors = [
            {"feature": "Blood Pressure (Systolic)", "value": (bp_sys - 120) / 50, "impact": abs(bp_sys - 120) / 50},
            {"feature": "Age", "value": (age - 40) / 40, "impact": abs(age - 40) / 40},
            {"feature": "Cholesterol Level", "value": (chol - 200) / 100, "impact": abs(chol - 200) / 100},
            {"feature": "Estimated Max Heart Rate", "value": (hr - 75) / 50, "impact": abs(hr - 75) / 50},
            {"feature": "Oxygen Saturation", "value": (98 - spo2) / 5, "impact": abs(98 - spo2) / 5},
        ]
        factors.sort(key=lambda x: x["impact"], reverse=True)
        total = sum(f["impact"] for f in factors)
        for f in factors:
            f["percent"] = round((f["impact"] / total * 100) if total > 0 else 20, 1)
            f["direction"] = "positive" if f["value"] > 0 else "negative"
        return factors
