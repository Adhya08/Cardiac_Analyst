"""
Pydantic Schemas — Request / Response validation models.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ─────────────────────────────────────────────
# User Profile
# ─────────────────────────────────────────────

class UserProfileIn(BaseModel):
    name: Optional[str] = "User"
    age: int = Field(default=45, ge=18, le=120)
    sex: str = Field(default="Male", pattern="^(Male|Female|Other)$")
    is_smoker: bool = False
    is_diabetic: bool = False
    has_family_history: bool = False
    height_cm: Optional[float] = Field(None, ge=50, le=250)


class UserRegisterIn(UserProfileIn):
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$", description="Valid email address")
    password: str = Field(..., min_length=8, description="Password minimum 8 characters")
    role: Optional[str] = Field(default="patient", description="Ignored on public registration; always creates patient")


class UserLoginIn(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class UserProfileOut(UserProfileIn):
    id: str
    email: Optional[str] = None
    role: Optional[str] = "patient"
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileOut


# ─────────────────────────────────────────────
# Vitals
# ─────────────────────────────────────────────

class VitalsIn(BaseModel):
    bp_sys: int = Field(..., ge=60, le=250, description="Systolic blood pressure mmHg")
    bp_dia: int = Field(..., ge=40, le=180, description="Diastolic blood pressure mmHg")
    hr: int = Field(..., ge=20, le=250, description="Heart rate bpm")
    weight: float = Field(..., ge=20.0, le=300.0, description="Weight in kg")
    spo2: float = Field(..., ge=40.0, le=100.0, description="Oxygen saturation %")
    glucose: Optional[float] = Field(None, ge=20.0, le=800.0, description="Fasting glucose mg/dL")
    cholesterol: Optional[float] = Field(None, ge=50.0, le=600.0, description="Total cholesterol mg/dL")

    @field_validator("bp_sys")
    @classmethod
    def bp_sys_must_be_sane(cls, v):
        if v < 70 or v > 230:
            raise ValueError("Systolic BP seems extreme — please recheck.")
        return v


class ShapFactorOut(BaseModel):
    feature: str
    value: float
    impact: float
    percent: float
    direction: str  # "positive" | "negative"


class VitalsOut(BaseModel):
    id: str
    risk_score: float
    risk_tier: str  # "Low" | "Borderline" | "Elevated"
    lgbm_probability: float
    framingham_risk: float
    confidence_interval: Dict[str, float]
    shap_top5: List[ShapFactorOut]
    ecg_prompt: bool
    trend_delta: float
    vitals: Dict[str, Any]
    timestamp: datetime


# ─────────────────────────────────────────────
# ECG
# ─────────────────────────────────────────────

class ECGConditionOut(BaseModel):
    code: str = "NORM"  # "NORM" | "MI" | "STTC" | "CD" | "HYP"
    name: str = "Normal ECG"
    model_score: float = 0.0  # Explicitly labeled model score, NOT medical disease probability
    threshold: float = 0.50
    detected: bool = False
    severity: str = "normal"  # "normal" | "possible" | "detected" | "unavailable"
    leads_affected: List[str] = []
    key_finding: str = ""
    explanation_en: str = ""
    explanation_hi: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "model_score" not in data and "probability" in data:
                data["model_score"] = float(data["probability"])
            if "code" not in data:
                name = str(data.get("name", "")).upper()
                if "INFARCT" in name or "ATTACK" in name:
                    data["code"] = "MI"
                elif "ST" in name or "ISCHEM" in name:
                    data["code"] = "STTC"
                elif "CONDUCTION" in name or "BLOCK" in name:
                    data["code"] = "CD"
                elif "HYPERTROPHY" in name:
                    data["code"] = "HYP"
                else:
                    data["code"] = "NORM"
            if "threshold" not in data:
                data["threshold"] = 0.50
            if "detected" not in data:
                score = float(data.get("model_score", 0.0))
                thresh = float(data.get("threshold", 0.50))
                data["detected"] = score >= thresh
            if "severity" not in data:
                data["severity"] = "detected" if data.get("detected") else "normal"
        return data


class ECGGradCAMHighlight(BaseModel):
    lead: str
    finding: str
    severity: str


class ECGOut(BaseModel):
    status: str = Field(default="ok", description="Status of analysis: 'ok', 'uncertain', or 'analysis_unavailable'")
    model_version: str = "ptbxl-resnet1d-v1.0"
    supported_labels: List[str] = ["NORM", "MI", "STTC", "CD", "HYP"]
    model_scores: Dict[str, float] = Field(default_factory=dict, description="Deterministic raw model scores [0-1] per superclass")
    quality_status: str = Field(default="good", description="Signal quality status: 'good', 'poor_quality', or 'unusable'")
    uncertainty_flag: bool = Field(default=False, description="True if prediction confidence is low or near decision boundary")
    abstain_reason: Optional[str] = None

    ecg_id: Optional[str] = None
    persistence_error: Optional[str] = None
    heart_rate_bpm: Optional[int] = None
    rhythm: Optional[str] = None
    pr_interval_ms: Optional[int] = None
    qrs_duration_ms: Optional[int] = None
    qtc_ms: Optional[int] = None
    axis_degrees: Optional[int] = None
    st_elevation_leads: List[str] = []
    st_depression_leads: List[str] = []
    conditions: List[ECGConditionOut] = []
    gradcam_highlights: List[ECGGradCAMHighlight] = []
    overall_assessment: str = "ECG analysis completed."
    urgency: str = "routine"  # "routine" | "see_doctor_today" | "emergency" | "unavailable"
    recommendations: List[str] = []
    image_quality: Optional[str] = "good"
    image_quality_note: Optional[str] = None
    disclaimer: str = "Research and educational prototype only. Not a medical device."


# ─────────────────────────────────────────────
# Emergency / Hospitals
# ─────────────────────────────────────────────

class TriageIn(BaseModel):
    symptoms: List[bool] = Field(..., min_length=8, max_length=8)
    bp_sys: Optional[int] = None
    hr: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    user_id: str = "default_user"


class HospitalOut(BaseModel):
    name: str
    address: Optional[str] = None
    lat: float
    lon: float
    distance_km: float
    rating: Optional[float] = None
    maps_url: str
    open_now: Optional[bool] = None
    contact: Optional[str] = None
    place_id: Optional[str] = None
    total_ratings: Optional[int] = None


class AmbulanceOut(BaseModel):
    service: str
    contact: str
    type: str
    eta_info: Optional[str] = None
    maps_url: Optional[str] = None
    notes: Optional[str] = None


class TriageOut(BaseModel):
    severity: str
    confidence: float
    risk_score: float
    yes_count: int
    stemi_suspicious: bool
    combo_triggered: bool
    vitals_red_flag: bool
    instructions: List[str]
    hospitals: List[HospitalOut]
    ambulances: List[AmbulanceOut]
    triage_id: str
