"""
Sarvam AI Assistant — Secondary LLM for text tasks.
Uses Sarvam's OpenAI-compatible chat API (sarvam-m model).

Capabilities:
  1. patient_chat()        — Conversational Q&A about ECG results / cardiac health
  2. summarize_report()    — Plain-language summary of an ECG analysis report
  3. generate_advice()     — Personalised lifestyle/follow-up advice from vitals

Base URL : https://api.sarvam.ai/v1
Auth     : api-subscription-key header (passed as api_key to OpenAI client)
Model    : sarvam-m  (hybrid reasoning, multilingual EN + HI)
"""
import os
from typing import Optional
from openai import OpenAI


# ── System persona for all cardiac chat sessions
CARDIAC_SYSTEM_PROMPT = """You are CardiacCare AI, a compassionate and knowledgeable cardiac health assistant.
You help patients understand their ECG results, heart health metrics, and what steps to take next.

RULES:
- Always respond in the same language the user writes in (English or Hindi or a mix).
- Use simple, non-technical language that patients can understand.
- Never diagnose or prescribe medication. Always recommend consulting a cardiologist.
- If the user describes an emergency (chest pain, shortness of breath, collapse), immediately tell them to call emergency services (112 in India).
- Be warm, reassuring, and empathetic. Patients may be anxious.
- Keep responses concise — 3-5 sentences unless more detail is explicitly requested.
- When referencing ECG findings, explain what they mean in daily life terms."""

# ── Sarvam-specific cardiac domain knowledge injected as context
CARDIAC_KNOWLEDGE_SNIPPET = """
Common ECG terms simplified:
- Heart rate: How fast your heart beats (normal: 60-100 bpm)
- Rhythm: The pattern of your heartbeats (should be regular)
- QTc interval: Electrical timing in your heart (prolonged QTc can increase arrhythmia risk)
- STEMI: A serious type of heart attack — always an emergency
- Atrial Fibrillation (AFib): Irregular heartbeat that increases stroke risk
- Bundle Branch Block (BBB): Electrical conduction delay — often manageable but needs monitoring
- LVH: Heart muscle thickening, often from high blood pressure
"""


class SarvamAssistant:
    """
    Sarvam AI powered assistant for cardiac patient text interactions.
    Uses the OpenAI-compatible Sarvam API endpoint.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("SARVAM_API_KEY must be set.")
        self.client = OpenAI(
            base_url="https://api.sarvam.ai/v1",
            api_key=api_key,
        )
        self.model = "sarvam-m"  # Hybrid reasoning, multilingual

    # ─────────────────────────────────────────────────────────
    # 1. Patient Chat — conversational Q&A
    # ─────────────────────────────────────────────────────────

    def patient_chat(
        self,
        user_message: str,
        ecg_context: Optional[dict] = None,
        chat_history: Optional[list] = None,
    ) -> dict:
        """
        Respond to a patient's question about their ECG or cardiac health.

        Args:
            user_message:  The patient's question/message.
            ecg_context:   Optional ECG analysis dict to inject as context.
            chat_history:  Optional list of prior messages [{"role": ..., "content": ...}].

        Returns:
            {"reply": str, "is_emergency": bool}
        """
        messages = [
            {"role": "system", "content": CARDIAC_SYSTEM_PROMPT + CARDIAC_KNOWLEDGE_SNIPPET},
        ]

        # Inject ECG context as a system note if available
        if ecg_context:
            ecg_summary = self._build_ecg_context_message(ecg_context)
            messages.append({
                "role": "system",
                "content": f"[Patient's latest ECG results for context]\n{ecg_summary}",
            })

        # Add conversation history (last 10 turns max to stay within context)
        if chat_history:
            messages.extend(chat_history[-10:])

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=512,
                temperature=0.4,
            )
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            reply = (
                "I'm sorry, I'm having trouble connecting right now. "
                f"Please consult your cardiologist directly. (Error: {e})"
            )

        # Simple emergency keyword detection
        emergency_keywords = [
            "chest pain", "heart attack", "can't breathe", "unconscious",
            "collapse", "saans nahi", "seene mein dard", "behosh",
        ]
        is_emergency = any(kw in user_message.lower() for kw in emergency_keywords)

        return {
            "reply": reply,
            "is_emergency": is_emergency,
        }

    # ─────────────────────────────────────────────────────────
    # 2. Report Summary — plain-language ECG report summary
    # ─────────────────────────────────────────────────────────

    def summarize_report(self, ecg_analysis: dict, language: str = "en") -> dict:
        """
        Generate a plain-language patient summary of an ECG analysis report.

        Args:
            ecg_analysis: The full ECG analysis dict from Gemini.
            language:     "en" for English, "hi" for Hindi, "en-hi" for bilingual.

        Returns:
            {"summary_en": str, "summary_hi": str, "key_points": list[str], "next_step": str}
        """
        ecg_text = self._build_ecg_context_message(ecg_analysis)

        lang_instruction = {
            "en": "Respond ONLY in English.",
            "hi": "Respond ONLY in Hindi (Devanagari script).",
            "en-hi": "Respond in both English and Hindi. First write the English version, then the Hindi version.",
        }.get(language, "Respond ONLY in English.")

        prompt = f"""You are summarizing an ECG report for a patient (not a doctor).
{lang_instruction}

Here is the ECG report data:
{ecg_text}

Please provide:
1. A warm, reassuring 3-4 sentence plain-language summary of what the ECG found.
2. 3-4 bullet-point key takeaways the patient should remember.
3. The single most important next step for this patient.

Format your response as:
SUMMARY: <summary text>
KEY POINTS:
- <point 1>
- <point 2>
- <point 3>
NEXT STEP: <most important action>"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CARDIAC_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=700,
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
        except Exception as e:
            raw = f"Could not generate summary. Error: {e}"
            return {
                "summary_en": raw,
                "summary_hi": "",
                "key_points": [],
                "next_step": "Please consult your cardiologist.",
                "raw": raw,
            }

        return self._parse_summary_response(raw, language)

    # ─────────────────────────────────────────────────────────
    # 3. Lifestyle Advice — personalised advice from vitals
    # ─────────────────────────────────────────────────────────

    def generate_advice(
        self,
        vitals: dict,
        risk_tier: str,
        ecg_urgency: Optional[str] = None,
    ) -> dict:
        """
        Generate personalised lifestyle and follow-up advice.

        Args:
            vitals:      Dict with bp_sys, bp_dia, hr, spo2, glucose, cholesterol, weight.
            risk_tier:   "Low" | "Borderline" | "Elevated"
            ecg_urgency: "routine" | "see_doctor_today" | "emergency" | None

        Returns:
            {"advice": str, "do_list": list[str], "avoid_list": list[str], "follow_up": str}
        """
        vitals_text = "\n".join(f"- {k}: {v}" for k, v in vitals.items() if v is not None)

        urgency_note = ""
        if ecg_urgency == "emergency":
            urgency_note = (
                "⚠️ CRITICAL: This patient's ECG showed emergency-level findings. "
                "Emphasise immediate hospital visit."
            )
        elif ecg_urgency == "see_doctor_today":
            urgency_note = "This patient should see a cardiologist today or very soon."

        prompt = f"""Based on the following patient vitals and risk level, provide clear, actionable lifestyle advice.
{urgency_note}

Patient Vitals:
{vitals_text}
Overall Cardiac Risk: {risk_tier}

Please provide:
1. A brief 2-sentence personalised health message for this patient.
2. A "Do" list of 3-4 things they should start doing.
3. An "Avoid" list of 3-4 things they should stop or reduce.
4. A clear follow-up recommendation (when to see a doctor, what tests to ask for).

Format:
ADVICE: <personal message>
DO:
- <item>
AVOID:
- <item>
FOLLOW_UP: <recommendation>"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CARDIAC_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.4,
            )
            raw = response.choices[0].message.content.strip()
        except Exception as e:
            raw = f"Could not generate advice. Error: {e}"
            return {
                "advice": raw,
                "do_list": [],
                "avoid_list": [],
                "follow_up": "Consult your cardiologist.",
            }

        return self._parse_advice_response(raw)

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    def _build_ecg_context_message(self, ecg: dict) -> str:
        """Convert ECG analysis dict to a concise text block for prompt injection."""
        detected = [
            c["name"]
            for c in ecg.get("conditions", [])
            if c.get("severity") in ("detected", "possible")
        ]
        lines = [
            f"Heart Rate: {ecg.get('heart_rate_bpm', 'Unknown')} bpm",
            f"Rhythm: {ecg.get('rhythm', 'Unknown')}",
            f"QTc: {ecg.get('qtc_ms', 'Unknown')} ms",
            f"PR Interval: {ecg.get('pr_interval_ms', 'Unknown')} ms",
            f"QRS Duration: {ecg.get('qrs_duration_ms', 'Unknown')} ms",
            f"ST Elevation Leads: {', '.join(ecg.get('st_elevation_leads', [])) or 'None'}",
            f"ST Depression Leads: {', '.join(ecg.get('st_depression_leads', [])) or 'None'}",
            f"Urgency: {ecg.get('urgency', 'Unknown')}",
            f"Image Quality: {ecg.get('image_quality', 'Unknown')}",
            f"Overall Assessment: {ecg.get('overall_assessment', '')}",
            f"Detected/Possible Conditions: {', '.join(detected) if detected else 'None significant'}",
        ]
        return "\n".join(lines)

    def _parse_summary_response(self, raw: str, language: str) -> dict:
        """Parse structured summary response from Sarvam."""
        import re

        summary_match = re.search(
            r"SUMMARY:\s*(.+?)(?=KEY POINTS:|$)", raw, re.DOTALL | re.IGNORECASE
        )
        points_match = re.search(
            r"KEY POINTS:\s*(.+?)(?=NEXT STEP:|$)", raw, re.DOTALL | re.IGNORECASE
        )
        next_match = re.search(r"NEXT STEP:\s*(.+?)$", raw, re.DOTALL | re.IGNORECASE)

        summary_text = summary_match.group(1).strip() if summary_match else raw[:300]
        points_raw = points_match.group(1).strip() if points_match else ""
        next_step = (
            next_match.group(1).strip() if next_match else "Consult your cardiologist."
        )

        # Extract bullet points
        key_points = [
            line.lstrip("-•* ").strip()
            for line in points_raw.splitlines()
            if line.strip().startswith(("-", "•", "*"))
            or (line.strip() and len(line.strip()) > 5)
        ]
        key_points = [p for p in key_points if p][:4]

        # Split EN / HI for bilingual responses
        summary_en = summary_text
        summary_hi = ""
        if language == "en-hi" and ("।" in raw or "हिन्दी" in raw):
            parts = raw.split("\n\n", 2)
            if len(parts) >= 2:
                summary_en = parts[0].replace("SUMMARY:", "").strip()
                summary_hi = parts[1].strip()

        return {
            "summary_en": summary_en,
            "summary_hi": summary_hi,
            "key_points": key_points,
            "next_step": next_step,
            "raw": raw,
        }

    def _parse_advice_response(self, raw: str) -> dict:
        """Parse structured advice response from Sarvam."""
        import re

        advice_match = re.search(
            r"ADVICE:\s*(.+?)(?=DO:|$)", raw, re.DOTALL | re.IGNORECASE
        )
        do_match = re.search(r"DO:\s*(.+?)(?=AVOID:|$)", raw, re.DOTALL | re.IGNORECASE)
        avoid_match = re.search(
            r"AVOID:\s*(.+?)(?=FOLLOW_UP:|$)", raw, re.DOTALL | re.IGNORECASE
        )
        follow_match = re.search(r"FOLLOW_UP:\s*(.+?)$", raw, re.DOTALL | re.IGNORECASE)

        def extract_bullets(text: str) -> list:
            return [
                line.lstrip("-•* ").strip()
                for line in text.splitlines()
                if line.strip()
                and (line.strip()[0] in "-•*" or len(line.strip()) > 5)
            ]

        return {
            "advice": advice_match.group(1).strip() if advice_match else raw[:200],
            "do_list": extract_bullets(do_match.group(1)) if do_match else [],
            "avoid_list": extract_bullets(avoid_match.group(1)) if avoid_match else [],
            "follow_up": (
                follow_match.group(1).strip() if follow_match else "Consult your cardiologist."
            ),
        }


# ── Module-level singleton accessor
_sarvam_assistant: Optional[SarvamAssistant] = None


def get_sarvam_assistant() -> SarvamAssistant:
    """Return or create the module-level SarvamAssistant singleton."""
    global _sarvam_assistant
    if _sarvam_assistant is None:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError("SARVAM_API_KEY environment variable is not set.")
        _sarvam_assistant = SarvamAssistant(api_key=api_key)
    return _sarvam_assistant
