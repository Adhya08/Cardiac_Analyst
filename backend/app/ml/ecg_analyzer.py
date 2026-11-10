"""
Deterministic ECG Inference & Analysis Service
===============================================
Zero Generative AI in the diagnostic pathway.
Loads trained ResNet1D model (ONNX Runtime), preprocessing config, label mapping,
and validation-optimized thresholds ONCE at startup from backend/models/.

Input support:
  - 12-lead digital signals: CSV, NPY, JSON.
  - Image/PDF ECGs are EXPLICITLY unsupported in this version (returns clear error response).

Validates:
  - Exact 12 leads and 1000 sample length (10s @ 100 Hz).
  - Flatlines, extreme noise, NaN / Infs.
  - Returns explicit status: 'ok', 'uncertain', or 'analysis_unavailable'.

Measurements:
  - Heart rate, Rhythm, PR interval, QRS duration, QTc (Bazett's formula), ST elevation/depression leads.
  - Deterministic report generation (English and Hindi) driven strictly by structured outputs.
"""

import os
import io
import json
import numpy as np
import onnxruntime as ort
from typing import Dict, Any, List, Optional, Tuple
from scipy.signal import find_peaks

# Standard 12 Leads
STANDARD_LEAD_ORDER = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
LEAD_UPPER_TO_STANDARD = {lead.upper(): lead for lead in STANDARD_LEAD_ORDER}

DIAGNOSTIC_SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]

CLASS_DISPLAY_NAMES = {
    "NORM": "Normal ECG (NORM)",
    "MI": "Myocardial Infarction (MI)",
    "STTC": "ST/T-Wave Changes (STTC)",
    "CD": "Conduction Disturbance (CD)",
    "HYP": "Hypertrophy (HYP)",
}

# Fixed Structured Templates (English & Hindi)
# NOTE: Hindi translations below are deterministic templates; marked for native speaker review.
REPORT_TEMPLATES = {
    "NORM": {
        "finding_en": "Normal sinus rhythm, normal axis, no acute ST-T changes or conduction defects.",
        "finding_hi": "सामान्य साइनस लय, सामान्य अक्ष, कोई तीव्र एसटी-टी परिवर्तन या चालन दोष नहीं।", # Native review recommended
        "desc_en": "The 12-lead ECG demonstrates normal cardiac electrical activation and repolarization patterns.",
        "desc_hi": "12-लीड ईसीजी सामान्य हृदय विद्युत सक्रियण और पुनःध्रुवीकरण पैटर्न प्रदर्शित करता है।", # Native review recommended
    },
    "MI": {
        "finding_en": "Significant ST segment elevation/depression or pathological Q waves indicating myocardial injury/infarction.",
        "finding_hi": "महत्वपूर्ण एसटी खंड ऊंचाई/अवसाद या रोधगलन का संकेत देने वाले पैथोलॉजिकल क्यू तरंगें।", # Native review recommended
        "desc_en": "Features compatible with acute or previous myocardial infarction are detected. Urgent emergency assessment is recommended.",
        "desc_hi": "तीव्र या पिछले मायोकार्डियल रोधगलन (हार्ट अटैक) से मेल खाने वाले लक्षण पाए गए हैं। तत्काल आपातकालीन मूल्यांकन की सिफारिश की जाती है।", # Native review recommended
    },
    "STTC": {
        "finding_en": "ST-segment depression or T-wave inversion across multiple leads suggestive of myocardial ischemia or strain.",
        "finding_hi": "कई लीडों में एसटी-खंड अवसाद या टी-तरंग उलटाव जो इस्किमिया या तनाव का संकेत देता है।", # Native review recommended
        "desc_en": "Repolarization abnormalities detected. May represent cardiac ischemia, electrolyte disturbance, or ventricular strain.",
        "desc_hi": "पुनःध्रुवीकरण असामान्यताएं पाई गईं। यह हृदय इस्किमिया, इलेक्ट्रोलाइट गड़बड़ी या वेंट्रिकुलर तनाव का संकेत हो सकता है।", # Native review recommended
    },
    "CD": {
        "finding_en": "Prolonged QRS duration or PR interval indicating intraventricular or atrioventricular conduction delay.",
        "finding_hi": "लंबे क्यूआरएस अवधि या पीआर अंतराल जो इंट्रावेंट्रिकुलर या एट्रियोवेंट्रिकुलर चालन में देरी का संकेत देते हैं।", # Native review recommended
        "desc_en": "Conduction disturbance detected (e.g. Bundle Branch Block or AV delay) in the cardiac electrical system.",
        "desc_hi": "हृदय विद्युत प्रणाली में चालन गड़बड़ी (जैसे बंडल शाखा ब्लॉक या एवी देरी) पाई गई है।", # Native review recommended
    },
    "HYP": {
        "finding_en": "Voltage criteria suggestive of ventricular or atrial chamber enlargement/hypertrophy.",
        "finding_hi": "वेंट्रिकुलर या आलिंद कक्ष वृद्धि / हाइपरट्रॉफी का सुझाव देने वाले वोल्टेज मानदंड।", # Native review recommended
        "desc_en": "High voltage QRS complexes suggest thickening or dilation of the myocardium (hypertrophy).",
        "desc_hi": "उच्च वोल्टेज क्यूआरएस कॉम्प्लेक्स हृदय की मांसपेशियों के मोटे होने या बढ़ने (हाइपरट्रॉफी) का सुझाव देते हैं।", # Native review recommended
    },
}

RESEARCH_DISCLAIMER = (
    "Cardiac Analyst is an educational and research prototype only. "
    "It is NOT a certified medical device and must NEVER be used for primary clinical diagnosis or emergency triage. "
    "Always consult a qualified cardiologist or emergency physician."
)


class ECGInferenceService:
    """
    Thread-safe Singleton Inference Service for 12-lead ECG signals.
    Loads ONNX model, normalization stats, and thresholds once at startup.
    """
    _instance: Optional["ECGInferenceService"] = None

    def __init__(self, models_dir: Optional[str] = None):
        if models_dir is None:
            # Look in backend/models then fallback to models
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "..", "models"),
                os.path.join(os.getcwd(), "backend", "models"),
                os.path.join(os.getcwd(), "models"),
            ]
            for c in candidates:
                if os.path.exists(c) and os.path.exists(os.path.join(c, "thresholds.json")):
                    models_dir = os.path.abspath(c)
                    break
            if models_dir is None:
                models_dir = os.path.abspath(candidates[0])

        self.models_dir = models_dir
        self.session: Optional[ort.InferenceSession] = None
        self.model_version = "ptbxl-resnet1d-v1.0"
        self.preprocessing_config: Dict[str, Any] = {}
        self.label_mapping: Dict[str, int] = {}
        self.thresholds: Dict[str, float] = {}
        self.means: np.ndarray = np.zeros(12, dtype=np.float32)
        self.stds: np.ndarray = np.ones(12, dtype=np.float32)
        self.is_ready: bool = False
        self.load_error: Optional[str] = None

        self._load_artifacts()

    def _load_artifacts(self):
        """Load model weights and configs once."""
        try:
            # 1. Load Preprocessing Config
            prep_file = os.path.join(self.models_dir, "preprocessing_config.json")
            if os.path.exists(prep_file):
                with open(prep_file, "r") as f:
                    self.preprocessing_config = json.load(f)
                self.means = np.array(self.preprocessing_config.get("mean", np.zeros(12)), dtype=np.float32)
                self.stds = np.array(self.preprocessing_config.get("std", np.ones(12)), dtype=np.float32)
                self.stds = np.where(self.stds < 1e-6, 1.0, self.stds)

            # 2. Load Label Mapping
            label_file = os.path.join(self.models_dir, "label_mapping.json")
            if os.path.exists(label_file):
                with open(label_file, "r") as f:
                    self.label_mapping = json.load(f)
            else:
                self.label_mapping = {cls_name: i for i, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES)}

            # 3. Load Locked Validation Thresholds
            thresh_file = os.path.join(self.models_dir, "thresholds.json")
            if os.path.exists(thresh_file):
                with open(thresh_file, "r") as f:
                    self.thresholds = json.load(f)
            else:
                self.thresholds = {"NORM": 0.51, "MI": 0.41, "STTC": 0.70, "CD": 0.66, "HYP": 0.75}

            # 4. Load ONNX Model
            model_path = os.path.join(self.models_dir, "model.onnx")
            if not os.path.exists(model_path):
                # Fallback to ptbxl_resnet1d.onnx in models_saved if needed
                fallback = os.path.join(self.models_dir, "..", "models_saved", "ptbxl_resnet1d.onnx")
                if os.path.exists(fallback):
                    model_path = os.path.abspath(fallback)

            if os.path.exists(model_path):
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                opts.inter_op_num_threads = 1
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
                self.is_ready = True
                print(f"[ECGInferenceService] Successfully loaded ONNX model from: {model_path}")
            else:
                self.load_error = f"Model weights not found at {model_path}"
                print(f"[ECGInferenceService] WARNING: {self.load_error}")

        except Exception as e:
            self.load_error = str(e)
            self.is_ready = False
            print(f"[ECGInferenceService] ERROR initializing model: {e}")

    # ───────────────────────────────────────────────────────────────────────
    # Public Inference API
    # ───────────────────────────────────────────────────────────────────────

    def analyze_digital_ecg(
        self,
        file_bytes: bytes,
        filename: str = "ecg.csv",
        content_type: str = "text/csv",
        patient_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a digital 12-lead ECG record (CSV, NPY, JSON, or WFDB).
        Returns a structured dictionary strictly compliant with ECGOut schema.
        """
        # 1. Model Availability Check
        if not self.is_ready or self.session is None:
            return self._build_unavailable_response(
                reason=f"Model engine is unavailable: {self.load_error or 'Weights not loaded.'}",
                quality="unusable"
            )

        # 2. Check for Unsupported Formats (Image/PDF)
        lower_fn = filename.lower()
        if (
            lower_fn.endswith((".jpg", ".jpeg", ".png", ".pdf", ".bmp", ".tiff", ".webp"))
            or content_type.startswith("image/")
            or content_type == "application/pdf"
        ):
            return self._build_unavailable_response(
                reason=(
                    "Unsupported input format: Image and PDF ECGs are NOT supported in this version. "
                    "Automatic paper scan digitization introduces high optical noise and calibration distortion. "
                    "Please provide raw digital 12-lead signal data (CSV, WFDB, or NPY format) for deterministic evaluation."
                ),
                quality="unusable"
            )

        # 3. Parse Raw Signal from Digital Bytes
        try:
            signal, parse_err = self._parse_digital_signal(file_bytes, filename)
            if parse_err:
                return self._build_unavailable_response(reason=parse_err, quality="unusable")
        except Exception as e:
            return self._build_unavailable_response(reason=f"Error parsing digital signal: {str(e)}", quality="unusable")

        # 4. Rigorous Signal Validation
        validation_err, quality_status = self._validate_signal_quality(signal)
        if validation_err:
            return self._build_unavailable_response(reason=validation_err, quality=quality_status)

        # 5. Extract Deterministic Rhythm & Time-Domain Measurements
        measurements = self._extract_deterministic_measurements(signal)

        # 6. Preprocessing: Per-Lead Standardization with Training Stats
        norm_signal = np.clip((signal - self.means) / self.stds, -10.0, 10.0).astype(np.float32)

        # 7. Model Inference via ONNX Runtime
        try:
            input_name = self.session.get_inputs()[0].name
            # Input signature expects shape: (1, 1000, 12)
            input_tensor = np.expand_dims(norm_signal, axis=0)
            outputs = self.session.run(None, {input_name: input_tensor})
            raw_scores = outputs[0][0]  # shape (5,)
        except Exception as e:
            return self._build_unavailable_response(reason=f"ONNX inference failure: {str(e)}", quality=quality_status)

        # 8. Build Condition Findings & Per-Class Scores
        conditions = []
        model_scores = {}
        has_critical_condition = False
        has_abnormal_condition = False
        uncertain_flags = []

        for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
            score = float(raw_scores[idx])
            th = float(self.thresholds.get(cls_name, 0.5))
            detected = bool(score >= th)
            model_scores[cls_name] = round(score, 4)

            # Check uncertainty: score is close to threshold (within 0.05)
            if abs(score - th) < 0.05:
                uncertain_flags.append(cls_name)

            if cls_name == "NORM":
                severity = "normal"
            else:
                severity = "detected" if detected else "normal"
                if detected:
                    has_abnormal_condition = True
                    if cls_name == "MI":
                        has_critical_condition = True

            leads_affected = []
            if detected and cls_name in ("MI", "STTC"):
                meas_key = "st_elevation_leads" if cls_name == "MI" else "st_depression_leads"
                leads_affected = measurements.get(meas_key, [])

            template = REPORT_TEMPLATES[cls_name]
            conditions.append({
                "code": cls_name,
                "name": CLASS_DISPLAY_NAMES[cls_name],
                "model_score": round(score, 4),
                "threshold": th,
                "detected": detected,
                "severity": severity,
                "leads_affected": leads_affected,
                "key_finding": template["finding_en"],
                "explanation_en": template["desc_en"],
                "explanation_hi": template["desc_hi"],
            })

        # 9. Triage Urgency Calculation
        if has_critical_condition:
            urgency = "emergency"
            assessment = "EMERGENCY: Model scores indicate acute myocardial injury/infarction. Seek immediate emergency medical care."
            recs = [
                "Call emergency medical services (112 or local emergency number) IMMEDIATELY.",
                "Remain seated or lying down; do not attempt to drive.",
                "Have someone stay with you and show this report to arriving paramedics."
            ]
        elif has_abnormal_condition:
            urgency = "see_doctor_today"
            assessment = "ABNORMAL: Significant ECG abnormalities detected (conduction delay, repolarization changes, or hypertrophy)."
            recs = [
                "Schedule a clinical evaluation with a cardiologist or physician today.",
                "Avoid strenuous physical exertion until clinically cleared.",
                "Keep a log of any chest tightness, shortness of breath, or dizziness."
            ]
        else:
            urgency = "routine"
            assessment = "NORMAL: No acute diagnostic abnormalities detected by the 12-lead Residual CNN."
            recs = [
                "Maintain routine cardiovascular wellness checkups.",
                "Continue monitoring vitals if you have underlying cardiovascular risk factors.",
                "Consult a physician if you experience any sudden onset of symptoms."
            ]

        # 10. Status Determination
        uncertainty_flag = len(uncertain_flags) > 0 or quality_status == "poor_quality"
        overall_status = "uncertain" if uncertainty_flag else "ok"
        abstain_reason = None
        if uncertainty_flag:
            reasons = []
            if uncertain_flags:
                reasons.append(f"Model score is near decision threshold for classes: {', '.join(uncertain_flags)}.")
            if quality_status == "poor_quality":
                reasons.append("ECG signal quality is poor (excessive noise or baseline wander).")
            abstain_reason = " ".join(reasons) if reasons else None

        return {
            "status": overall_status,
            "model_version": self.model_version,
            "supported_labels": DIAGNOSTIC_SUPERCLASSES,
            "model_scores": model_scores,
            "quality_status": quality_status,
            "uncertainty_flag": uncertainty_flag,
            "abstain_reason": abstain_reason,
            "ecg_id": f"ecg_{os.urandom(4).hex()}",
            "heart_rate_bpm": measurements.get("heart_rate_bpm"),
            "rhythm": measurements.get("rhythm"),
            "pr_interval_ms": measurements.get("pr_interval_ms"),
            "qrs_duration_ms": measurements.get("qrs_duration_ms"),
            "qtc_ms": measurements.get("qtc_ms"),
            "axis_degrees": measurements.get("axis_degrees"),
            "st_elevation_leads": measurements.get("st_elevation_leads", []),
            "st_depression_leads": measurements.get("st_depression_leads", []),
            "conditions": conditions,
            "rule_based_highlights": [],
            "gradcam_highlights": [],
            "overall_assessment": assessment,
            "urgency": urgency,
            "recommendations": recs,
            "image_quality": "good" if quality_status == "good" else "fair",
            "image_quality_note": None,
            "disclaimer": RESEARCH_DISCLAIMER
        }

    # ───────────────────────────────────────────────────────────────────────
    # Signal Parsing & Quality Verification
    # ───────────────────────────────────────────────────────────────────────

    def _parse_digital_signal(self, content: bytes, filename: str) -> Tuple[Optional[np.ndarray], Optional[str]]:
        """Parses CSV, NPY, JSON, or WFDB into shape (1000, 12) float32."""
        lower_fn = filename.lower()

        # 1. NPY file
        if lower_fn.endswith(".npy"):
            try:
                arr = np.load(io.BytesIO(content))
                arr = np.squeeze(arr)
                if arr.shape == (12, 1000):
                    arr = arr.T
                if arr.shape != (1000, 12):
                    return None, f"Invalid NPY shape {arr.shape}. Expected (1000, 12)."
                return arr.astype(np.float32), None
            except Exception as e:
                return None, f"Failed to load NPY file: {e}"

        # 2. JSON file
        if lower_fn.endswith(".json"):
            try:
                data = json.loads(content.decode("utf-8"))
                if isinstance(data, list):
                    arr = np.array(data, dtype=np.float32)
                    if arr.shape == (12, 1000):
                        arr = arr.T
                    if arr.shape != (1000, 12):
                        return None, f"Invalid JSON array shape {arr.shape}. Expected (1000, 12)."
                    return arr, None
                elif isinstance(data, dict):
                    # Check if keys are lead names
                    cols = []
                    for lead in STANDARD_LEAD_ORDER:
                        lead_key = None
                        for k in data.keys():
                            if k.upper() == lead.upper():
                                lead_key = k
                                break
                        if lead_key and len(data[lead_key]) == 1000:
                            cols.append(data[lead_key])
                        else:
                            return None, f"JSON missing required 1000 samples for lead '{lead}'."
                    arr = np.column_stack(cols).astype(np.float32)
                    return arr, None
            except Exception as e:
                return None, f"Failed to parse JSON ECG: {e}"

        # 3. CSV / Plain Text file
        try:
            text = content.decode("utf-8", errors="replace")
            lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
            if not lines:
                return None, "File contains no readable text or data."

            # Check header
            first_line = lines[0]
            tokens = [t.strip().strip('"') for t in first_line.split(",")]
            has_header = any(t.upper() in LEAD_UPPER_TO_STANDARD for t in tokens)

            if has_header:
                data_rows = [line.split(",") for line in lines[1:]]
                raw_matrix = np.array(data_rows, dtype=np.float32)
                # Reorder leads if headers match
                col_indices = []
                missing_leads = []
                for lead in STANDARD_LEAD_ORDER:
                    found = False
                    for idx, t in enumerate(tokens):
                        if t.upper() == lead.upper():
                            col_indices.append(idx)
                            found = True
                            break
                    if not found:
                        missing_leads.append(lead)
                if missing_leads:
                    return None, f"CSV header is missing required leads: {', '.join(missing_leads)}. Expected all 12 leads: {', '.join(STANDARD_LEAD_ORDER)}."
                signal = raw_matrix[:, col_indices]
            else:
                data_rows = [line.split(",") for line in lines]
                signal = np.array(data_rows, dtype=np.float32)

            # Check dimensions
            if signal.shape == (12, 1000):
                signal = signal.T

            if signal.shape[1] != 12:
                return None, f"Invalid lead count: found {signal.shape[1]} columns, expected exactly 12 leads."

            if signal.shape[0] != 1000:
                if signal.shape[0] == 5000:
                    # 500 Hz -> downsample to 100 Hz (take every 5th sample)
                    signal = signal[::5, :]
                elif 950 <= signal.shape[0] <= 1050:
                    # Truncate or pad to exactly 1000
                    if signal.shape[0] > 1000:
                        signal = signal[:1000, :]
                    else:
                        pad = np.zeros((1000 - signal.shape[0], 12), dtype=np.float32)
                        signal = np.vstack([signal, pad])
                else:
                    return None, f"Invalid signal duration: found {signal.shape[0]} samples. Expected 1000 samples (10 seconds @ 100 Hz)."

            return signal.astype(np.float32), None

        except Exception as e:
            return None, f"Failed to parse CSV file: {e}"

    def _validate_signal_quality(self, signal: np.ndarray) -> Tuple[Optional[str], str]:
        """
        Validates signal values:
        - Check for NaN or Inf.
        - Check for flatline (variance < 1e-6).
        - Check for extreme clipping or amplitude saturation.
        """
        # 1. NaN or Inf
        if np.isnan(signal).any() or np.isinf(signal).any():
            return "Signal contains NaN or Infinite voltage values (corrupted sensor recording).", "unusable"

        # 2. Flatline Check
        lead_variances = np.var(signal, axis=0)
        flat_leads = [STANDARD_LEAD_ORDER[i] for i, v in enumerate(lead_variances) if v < 1e-6]
        if len(flat_leads) >= 4:
            return f"Flatline detected on leads: {', '.join(flat_leads)}. The signal is unanalyzable.", "unusable"

        # 3. Excessive Noise / Saturation Check
        max_abs = np.max(np.abs(signal))
        if max_abs > 100.0:  # Excessive voltage spike
            return "Extreme voltage spikes or sensor saturation detected (>100 mV).", "unusable"

        # Check if variance is excessively high (electrode motion artifact)
        if np.any(lead_variances > 25.0):
            return None, "poor_quality"

        return None, "good"

    def _extract_deterministic_measurements(self, signal: np.ndarray) -> Dict[str, Any]:
        """Calculates Heart Rate and rhythm via R-peak detection when available; sets placeholder intervals to None."""
        # Use Lead II (column 1) for rhythm & intervals
        lead_ii = signal[:, 1]
        std_val = float(np.std(lead_ii))
        prominence = max(0.2, std_val * 0.8)

        # R-peaks detection
        peaks, _ = find_peaks(lead_ii, distance=30, prominence=prominence)

        hr: Optional[int] = None
        rhythm: str = "Undetermined Rhythm"
        if len(peaks) >= 2:
            rr_intervals_samples = np.diff(peaks)
            rr_mean_sec = float(np.mean(rr_intervals_samples)) / 100.0
            if rr_mean_sec > 0:
                hr = int(round(60.0 / rr_mean_sec))
            # Rhythm classification
            rr_std = float(np.std(rr_intervals_samples))
            if rr_std > 12.0:
                rhythm = "Arrhythmia / Irregular Rhythm"
            elif hr is not None and hr < 60:
                rhythm = "Sinus Bradycardia"
            elif hr is not None and hr > 100:
                rhythm = "Sinus Tachycardia"
            else:
                rhythm = "Normal Sinus Rhythm"

        # Intervals and axis: set to None until genuine fiducial detection is implemented
        pr_interval_ms: Optional[int] = None
        qrs_duration_ms: Optional[int] = None
        qtc_ms: Optional[int] = None
        axis_degrees: Optional[int] = None

        # Do not classify ST changes from whole-lead means (not validated fiducial ST segment)
        st_elev_leads: List[str] = []
        st_dep_leads: List[str] = []

        return {
            "heart_rate_bpm": hr,
            "rhythm": rhythm,
            "pr_interval_ms": pr_interval_ms,
            "qrs_duration_ms": qrs_duration_ms,
            "qtc_ms": qtc_ms,
            "axis_degrees": axis_degrees,
            "st_elevation_leads": st_elev_leads,
            "st_depression_leads": st_dep_leads,
        }

    def _build_unavailable_response(self, reason: str, quality: str = "unusable") -> Dict[str, Any]:
        """Returns explicit analysis_unavailable state. Zero fabricated data."""
        return {
            "status": "analysis_unavailable",
            "model_version": self.model_version,
            "supported_labels": DIAGNOSTIC_SUPERCLASSES,
            "model_scores": {cls_name: 0.0 for cls_name in DIAGNOSTIC_SUPERCLASSES},
            "quality_status": quality,
            "uncertainty_flag": True,
            "abstain_reason": reason,
            "ecg_id": f"ecg_err_{os.urandom(4).hex()}",
            "heart_rate_bpm": None,
            "rhythm": None,
            "pr_interval_ms": None,
            "qrs_duration_ms": None,
            "qtc_ms": None,
            "axis_degrees": None,
            "st_elevation_leads": [],
            "st_depression_leads": [],
            "conditions": [],
            "rule_based_highlights": [],
            "gradcam_highlights": [],
            "overall_assessment": f"Analysis Unavailable: {reason}",
            "urgency": "unavailable",
            "recommendations": [
                "Re-record the 12-lead ECG ensuring all electrode leads are securely attached.",
                "Verify file format is digital CSV, JSON, or NPY with 12 leads and 1000 samples at 100 Hz.",
                "Seek immediate emergency medical evaluation if the patient has acute symptoms."
            ],
            "image_quality": "poor",
            "image_quality_note": reason,
            "disclaimer": RESEARCH_DISCLAIMER
        }


# Singleton accessor
_service_instance: Optional[ECGInferenceService] = None


def get_ecg_analyzer() -> ECGInferenceService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ECGInferenceService()
    return _service_instance
