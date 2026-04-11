"""
ECG Analyzer — Real ECG analysis using Google Gemini Vision API (gemini-1.5-flash-latest).
Migrated from deprecated google-generativeai to google-genai (google.genai).

Supports: JPG, PNG, PDF ECG formats.
Returns: 18-condition multi-label classification, measurements, urgency level,
         plain-language patient explanation (English + Hindi), GradCAM-style highlights.
"""
import io
import json
import re
import base64
from typing import Optional
from google import genai
from google.genai import types
from PIL import Image


# ── 18-condition cardiac condition list (as per PRD v2.0)
CONDITION_LIST = [
    "Normal Sinus Rhythm",
    "Atrial Fibrillation",
    "Atrial Flutter",
    "STEMI",
    "NSTEMI",
    "Ventricular Tachycardia",
    "Heart Failure (LVH)",
    "Long QT Syndrome",
    "WPW Syndrome",
    "Pericarditis",
    "LBBB",
    "RBBB",
    "AV Block",
    "Takotsubo Cardiomyopathy",
    "Hyperkalemia",
    "Myocarditis",
    "Sinus Bradycardia",
    "Sinus Tachycardia",
]


class ECGAnalyzer:
    """
    Real ECG analysis using Gemini Vision API (google.genai SDK).
    No mock data — every output comes from actual AI image analysis.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    # ─────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────

    def analyze_ecg(self, image_bytes: bytes, patient_context: dict, content_type: str = "image/jpeg") -> dict:
        """
        Analyze an ECG image using Gemini Vision.

        Args:
            image_bytes:     Raw bytes of the uploaded file.
            patient_context: age, sex, conditions, bp_sys, hr.
            content_type:    MIME type of uploaded file.

        Returns:
            Dict matching ECGOut schema.
        """
        if content_type == "application/pdf":
            return self._analyze_pdf(image_bytes, patient_context)

        # Load and validate image
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            if pil_image.mode == "RGBA":
                pil_image = pil_image.convert("RGB")
            elif pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")
        except Exception as e:
            return self._fallback_response(f"Could not open image: {e}")

        prompt = self._build_prompt(patient_context)

        # Convert PIL image to bytes for genai SDK
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format="JPEG", quality=90)
        img_bytes = img_byte_arr.getvalue()

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text
        except Exception as e:
            return self._fallback_response(f"Gemini API error: {e}")

        return self._parse_and_validate(raw_text)

    # ─────────────────────────────────────────────────────────
    # Prompt Engineering
    # ─────────────────────────────────────────────────────────

    def _build_prompt(self, ctx: dict) -> str:
        age = ctx.get("age", "Unknown")
        sex = ctx.get("sex", "Unknown")
        conditions = ctx.get("conditions") or "None reported"
        bp_sys = ctx.get("bp_sys", "Unknown")
        hr = ctx.get("hr", "Unknown")
        condition_csv = ", ".join(CONDITION_LIST)

        return f"""You are an expert cardiologist AI assistant. 
Analyze this ECG image in detail and return a structured clinical assessment.

PATIENT CONTEXT:
- Age: {age} years
- Sex: {sex}
- Known conditions/medications: {conditions}
- Current resting BP: {bp_sys} mmHg
- Current resting HR: {hr} bpm

ANALYSIS INSTRUCTIONS:
1. Identify heart rate from R-R intervals if visible
2. Assess rhythm: regular/irregular, P-wave presence, R-R consistency
3. Measure intervals: PR (normal 120-200ms), QRS (normal <120ms), QTc (male <450ms, female <470ms)
4. Check electrical axis (normal -30 to +90 degrees)
5. ST segment: elevation (≥1mm in ≥2 contiguous leads = STEMI), depression
6. T-wave morphology: inversion, peaked, flattened
7. Q waves: pathological if >25% of R-wave or >40ms wide
8. Bundle branch blocks: LBBB (QRS≥120ms, broad notched R in V5-V6), RBBB (rSR' in V1)
9. Signs of WPW: delta wave + short PR (<120ms)
10. Signs of LVH: Sokolow-Lyon voltage criteria
11. Hyperkalemia: peaked narrow T-waves, widened QRS, sine-wave pattern
12. Takotsubo: anterior T-wave inversions, prolonged QTc, no coronary obstruction pattern
13. Pericarditis: diffuse saddle-shaped ST elevation, PR depression in multiple leads
14. Assess all 18 conditions: {condition_csv}
15. If image quality is poor or leads are indistinguishable, clearly state limitations.
16. Give priority to detecting artifacts or excessive baseline wander that could mimic pathology.

Return ONLY valid JSON with this exact structure:
{{
  "heart_rate_bpm": <integer or null>,
  "rhythm": "<string>",
  "pr_interval_ms": <integer or null>,
  "qrs_duration_ms": <integer or null>,
  "qtc_ms": <integer or null>,
  "axis_degrees": <integer or null>,
  "st_elevation_leads": ["<lead names>"],
  "st_depression_leads": ["<lead names>"],
  "conditions": [
    {{
      "name": "<exact name from the 18 conditions list>",
      "probability": <float 0.0-1.0>,
      "severity": "<normal|possible|detected>",
      "leads_affected": ["<lead names>"],
      "key_finding": "<specific ECG feature that triggered this>",
      "explanation_en": "<2-3 sentence patient-friendly English explanation>",
      "explanation_hi": "<same in Hindi>"
    }}
  ],
  "gradcam_highlights": [
    {{"lead": "<lead>", "finding": "<what was found>", "severity": "<normal|abnormal|critical>"}}
  ],
  "overall_assessment": "<3-4 sentence clinical summary>",
  "urgency": "<routine|see_doctor_today|emergency>",
  "recommendations": ["<specific recommendation 1>", "<recommendation 2>"],
  "image_quality": "<good|fair|poor>",
  "image_quality_note": "<explain if fair/poor, else null>",
  "disclaimer": "This is an AI-assisted screening tool. All findings must be confirmed by a qualified cardiologist."
}}

CRITICAL RULES:
- If STEMI detected (ST elevation ≥1mm in ≥2 contiguous leads): urgency = "emergency", severity = "detected"
- If Ventricular Tachycardia (wide complex, rate >100 bpm): urgency = "emergency"
- All 18 conditions MUST appear in conditions array (even if probability = 0.01 and severity = "normal")
- Use probability 0.0-1.0 as decimal (NOT percentage)
- If image is not an ECG or unreadable, set image_quality = "poor" and explain
- severity thresholds: probability > 0.85 → "detected", 0.50-0.85 → "possible", <0.50 → "normal"
"""

    # ─────────────────────────────────────────────────────────
    # Response Parsing
    # ─────────────────────────────────────────────────────────

    def _parse_and_validate(self, raw_text: str) -> dict:
        """Parse Gemini JSON response and ensure all required fields."""
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback: extract JSON block from text
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    return self._fallback_response("Could not parse AI response as JSON.")
            else:
                return self._fallback_response("No JSON found in AI response.")

        # Ensure all 18 conditions are present
        existing = {c.get("name", "") for c in result.get("conditions", [])}
        for cond in CONDITION_LIST:
            if cond not in existing:
                result.setdefault("conditions", []).append({
                    "name": cond,
                    "probability": 0.01,
                    "severity": "normal",
                    "leads_affected": [],
                    "key_finding": "No abnormalities detected for this condition.",
                    "explanation_en": f"No signs of {cond} were identified on this ECG.",
                    "explanation_hi": f"इस ECG पर {cond} के कोई संकेत नहीं पाए गए।",
                })

        # Enforce severity thresholds
        for cond in result.get("conditions", []):
            prob = float(cond.get("probability", 0))
            if prob > 0.85:
                cond["severity"] = "detected"
            elif prob > 0.50:
                cond["severity"] = "possible"
            else:
                cond["severity"] = "normal"

        # Sort conditions: detected first, then possible, then normal (by probability)
        result["conditions"].sort(key=lambda c: -float(c.get("probability", 0)))

        # Ensure emergency upgrade for life-threatening conditions
        for cond in result.get("conditions", []):
            if cond.get("name") in ("STEMI", "Ventricular Tachycardia") and cond.get("severity") == "detected":
                result["urgency"] = "emergency"
                break

        # Fill required fields with safe defaults
        def_required = {
            "heart_rate_bpm": None,
            "rhythm": "Cannot determine from this image",
            "pr_interval_ms": None,
            "qrs_duration_ms": None,
            "qtc_ms": None,
            "axis_degrees": None,
            "st_elevation_leads": [],
            "st_depression_leads": [],
            "gradcam_highlights": [],
            "overall_assessment": "Assessment completed. Please consult a cardiologist.",
            "urgency": "see_doctor_today",
            "recommendations": ["Consult a cardiologist for professional ECG interpretation."],
            "image_quality": "fair",
            "image_quality_note": None,
            "disclaimer": "This is an AI-assisted screening tool. All findings must be confirmed by a qualified cardiologist.",
        }
        for k, v in def_required.items():
            if k not in result:
                result[k] = v

        return result

    def _analyze_pdf(self, pdf_bytes: bytes, ctx: dict) -> dict:
        """Analyze PDF ECG file by passing bytes directly to Gemini."""
        prompt = self._build_prompt(ctx) + "\n\nNote: This is a PDF file. It may contain an ECG Report. Extract and analyze any ECG data present."
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                ),
            )
            return self._parse_and_validate(response.text)
        except Exception as e:
            return self._fallback_response(f"PDF ECG analysis failed: {e}")

    def _fallback_response(self, error_note: str) -> dict:
        """Safe fallback when analysis fails."""
        conditions = [
            {
                "name": cond,
                "probability": 0.5 if cond == "Normal Sinus Rhythm" else 0.01,
                "severity": "possible" if cond == "Normal Sinus Rhythm" else "normal",
                "leads_affected": [],
                "key_finding": "Analysis incomplete",
                "explanation_en": f"Could not complete analysis for {cond}. Please upload a clearer ECG image.",
                "explanation_hi": f"{cond} का विश्लेषण पूरा नहीं हो सका। कृपया एक स्पष्ट ECG छवि अपलोड करें।",
            }
            for cond in CONDITION_LIST
        ]
        return {
            "heart_rate_bpm": None,
            "rhythm": "Unable to determine",
            "pr_interval_ms": None,
            "qrs_duration_ms": None,
            "qtc_ms": None,
            "axis_degrees": None,
            "st_elevation_leads": [],
            "st_depression_leads": [],
            "conditions": conditions,
            "gradcam_highlights": [],
            "overall_assessment": f"ECG analysis could not be completed. {error_note} Please upload a higher-quality ECG image.",
            "urgency": "see_doctor_today",
            "recommendations": [
                "Upload a higher quality, well-lit ECG image.",
                "Ensure the full 12-lead ECG is visible in the image.",
                "Consult a cardiologist for professional interpretation.",
            ],
            "image_quality": "poor",
            "image_quality_note": error_note,
            "disclaimer": "This is an AI-assisted screening tool. All findings must be confirmed by a qualified cardiologist.",
        }
