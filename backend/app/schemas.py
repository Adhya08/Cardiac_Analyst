"""
Pydantic Schemas — Request / Response validation models.
"""
from pydantic import BaseModel, Field, field_validator
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


class UserProfileOut(UserProfileIn):
    id: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    name: str
    probability: float
    severity: str  # "normal" | "possible" | "detected"
    leads_affected: List[str]
    key_finding: str
    explanation_en: str
    explanation_hi: Optional[str] = None


class ECGGradCAMHighlight(BaseModel):
    lead: str
    finding: str
    severity: str


class ECGOut(BaseModel):
    ecg_id: str
    heart_rate_bpm: Optional[int] = None
    rhythm: Optional[str] = None
    pr_interval_ms: Optional[int] = None
    qrs_duration_ms: Optional[int] = None
    qtc_ms: Optional[int] = None
    axis_degrees: Optional[int] = None
    st_elevation_leads: List[str] = []
    st_depression_leads: List[str] = []
    conditions: List[ECGConditionOut]
    gradcam_highlights: List[ECGGradCAMHighlight] = []
    overall_assessment: str
    urgency: str  # "routine" | "see_doctor_today" | "emergency"
    recommendations: List[str]
    image_quality: str  # "good" | "fair" | "poor"
    image_quality_note: Optional[str] = None
    disclaimer: str


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
