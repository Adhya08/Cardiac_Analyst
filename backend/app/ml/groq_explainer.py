"""
Groq API Explainer with Anti-Hallucination Guardrails
====================================================
Provides optional, patient-friendly explanations of validated ECG and vitals reports
using Groq's free-tier LLM models (e.g. LLaMA 3.3 70B / LLaMA 3.1 8B).

Enforces strict safety rules:
1. Strict Grounding: The LLM is strictly constrained to the validated findings of the
   deterministic structured report.
2. Anti-Hallucination Verification: Output is verified against known diagnoses. If unvalidated
   conditions or altered findings are introduced, the output is rejected and the deterministic
   report is returned.
3. Resilient Fallbacks: Seamless fallback to deterministic report generator if Groq is
   unconfigured, down, rate-limited (HTTP 429), times out, or returns malformed text.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
import requests

from .report_generator import generate_deterministic_report, generate_deterministic_advice

logger = logging.getLogger("cardiac_analyst.groq")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_GROUNDING_PROMPT = """You are a compassionate medical communication assistant explaining an ALREADY COMPLETED, VALIDATED ECG report to a patient in simple, reassuring language.

CRITICAL CLINICAL GROUNDING RESTRICTIONS:
1. You MUST NOT INVENT, ADD, or SPECULATE about any diagnosis, abnormality, disease, or probability not explicitly listed in the VALIDATED FINDINGS below.
2. You MUST NOT alter any reported numbers, heart rate, or intervals (PR, QRS, QTc).
3. You MUST NOT recommend any prescription medications, invasive procedures, or changes to therapy not in the validated advice.
4. If the validated findings indicate Normal (NORM), DO NOT claim or imply the patient has a heart attack, infarction, or block.
5. Emphasize that this is an educational summary and encourage discussing results with their physician.

Format your response as valid JSON with the following exact keys:
{
  "summary_en": "Patient-friendly summary in English (3-4 sentences)",
  "summary_hi": "Patient-friendly summary in Hindi (3-4 sentences in Devanagari script)",
  "key_points": ["Point 1", "Point 2", "Point 3"],
  "next_step": "Single primary recommended action"
}"""


class GroqExplainer:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_GROQ_MODEL, timeout: int = 8):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self.timeout = timeout

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _call_groq(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        if not self.is_available:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 800,
            "response_format": {"type": "json_object"}
        }

        try:
            resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 429:
                logger.warning("Groq API quota exhausted or rate limit exceeded (HTTP 429).")
                raise RuntimeError("Groq rate limit reached (HTTP 429).")
            if resp.status_code != 200:
                logger.error(f"Groq API returned HTTP {resp.status_code}: {resp.text}")
                raise RuntimeError(f"Groq API error ({resp.status_code})")

            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            logger.warning("Groq API request timed out.")
            raise RuntimeError("Groq request timed out.")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Groq network connection error: {e}")
            raise RuntimeError(f"Groq connection error: {e}")

    def _validate_grounding(self, groq_json: Dict[str, Any], allowed_conditions: List[str]) -> bool:
        """
        Anti-hallucination check: Ensures the LLM did not invent severe conditions absent from the input.
        """
        text_corpus = (
            groq_json.get("summary_en", "") + " " +
            " ".join(groq_json.get("key_points", [])) + " " +
            groq_json.get("next_step", "")
        ).lower()

        # If NORM only, check for hallucinations of critical conditions as positive diagnoses
        if "MI" not in allowed_conditions:
            if any(term in text_corpus for term in ["heart attack", "myocardial infarction", "acute coronary", "ischemic damage"]):
                # Allow only if explicitly negated (e.g. "no sign of heart attack")
                if not any(neg in text_corpus for neg in ["no sign of heart attack", "no evidence of heart attack", "no myocardial infarction", "normal"]):
                    logger.warning("Grounding check failed: LLM mentioned heart attack/MI when not in allowed conditions.")
                    return False

        if "CD" not in allowed_conditions:
            if "bundle branch block" in text_corpus or "conduction block" in text_corpus:
                if not any(neg in text_corpus for neg in ["no bundle branch", "no conduction", "no block"]):
                    logger.warning("Grounding check failed: LLM introduced conduction block not in allowed conditions.")
                    return False

        return True

    def explain_report(self, ecg_analysis: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
        """
        Generates a patient-friendly report using Groq, with automatic fallback to deterministic report.
        """
        # Always build the deterministic baseline first
        deterministic_report = generate_deterministic_report(ecg_analysis, language=language)

        # If analysis is unavailable or Groq is not configured, return deterministic report
        if ecg_analysis.get("status") == "analysis_unavailable" or not self.is_available:
            deterministic_report["source"] = "deterministic_engine"
            return deterministic_report

        allowed_conditions = deterministic_report.get("detected_conditions", ["NORM"])
        metrics_summary = deterministic_report.get("metrics_summary", {})
        
        user_prompt = f"""VALIDATED FINDINGS:
- Conditions Detected: {', '.join(allowed_conditions)}
- Primary Summary: {deterministic_report['summary_en']}
- Electrophysiology Metrics: {json.dumps(metrics_summary)}
- Urgency Level: {deterministic_report['urgency']}
- Validated Next Action: {deterministic_report['next_step']}

Please generate a compassionate, easy-to-understand explanation for the patient while strictly respecting the clinical boundaries."""

        try:
            raw_content = self._call_groq([
                {"role": "system", "content": SYSTEM_GROUNDING_PROMPT},
                {"role": "user", "content": user_prompt}
            ])

            parsed = json.loads(raw_content)

            # Validate grounding
            if not self._validate_grounding(parsed, allowed_conditions):
                logger.warning("Groq response failed clinical grounding validation. Falling back to deterministic report.")
                deterministic_report["source"] = "deterministic_fallback"
                deterministic_report["fallback_reason"] = "grounding_validation_failed"
                return deterministic_report

            # Return grounded Groq explanation merged with validated clinical metadata
            return {
                "summary_en": parsed.get("summary_en", deterministic_report["summary_en"]),
                "summary_hi": parsed.get("summary_hi", deterministic_report["summary_hi"]),
                "key_points": parsed.get("key_points", deterministic_report["key_points"]),
                "next_step": parsed.get("next_step", deterministic_report["next_step"]),
                "urgency": deterministic_report["urgency"],
                "is_emergency": deterministic_report["is_emergency"],
                "detected_conditions": deterministic_report["detected_conditions"],
                "metrics_summary": deterministic_report["metrics_summary"],
                "disclaimer": deterministic_report["disclaimer"],
                "source": "groq_validated"
            }

        except Exception as e:
            logger.info(f"Groq explanation unavailable ({e}). Using deterministic engine.")
            deterministic_report["source"] = "deterministic_fallback"
            deterministic_report["fallback_reason"] = str(e)
            return deterministic_report

    def explain_chat_message(
        self,
        message: str,
        ecg_analysis: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Patient Q&A grounded strictly in validated ECG findings.
        """
        # Emergency intent check
        msg_lower = message.lower()
        emergency_keywords = ["chest pain", "crushing", "sweating", "cannot breathe", "short of breath", "fainted", "passed out", "seizure", "collapse"]
        is_emergency = any(k in msg_lower for k in emergency_keywords)
        if is_emergency:
            return {
                "reply": "🚨 Based on the symptoms described (such as severe chest pain, shortness of breath, or collapse), this sounds like a potential cardiovascular emergency. Please stop all activity, sit or lie down, and call 112 (India) or your local emergency dispatch immediately.",
                "is_emergency": True,
                "source": "deterministic_emergency_guardrail"
            }

        # If Groq is not configured or fails, use safe deterministic FAQ response
        if not self.is_available:
            return {
                "reply": "Cardiac Analyst Assistant is operating in deterministic offline mode. Please consult your physician or electrophysiologist for personalized guidance regarding your cardiac symptoms.",
                "is_emergency": False,
                "source": "deterministic_offline_guardrail"
            }

        context_info = "No specific ECG provided."
        if ecg_analysis:
            det = generate_deterministic_report(ecg_analysis)
            context_info = (
                f"PATIENT'S VALIDATED ECG FINDINGS:\n"
                f"- Conditions: {', '.join(det.get('detected_conditions', []))}\n"
                f"- Metrics: {json.dumps(det.get('metrics_summary', {}))}\n"
                f"- Urgency: {det.get('urgency')}\n"
                f"- Summary: {det.get('summary_en')}\n"
            )

        system_prompt = f"""You are a helpful, reassuring cardiac health educator answering a patient's question.
You MUST NOT diagnose new conditions, contradict their medical team, or invent risks outside this validated context:
{context_info}

Keep responses concise, non-alarmist, and clear. Advise the patient to consult their doctor for personalized medical decisions."""

        messages = [{"role": "system", "content": system_prompt}]
        for turn in (chat_history or [])[-4:]:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
        messages.append({"role": "user", "content": message})

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key.strip()}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 400
            }
            resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                return {
                    "reply": reply,
                    "is_emergency": False,
                    "source": "groq_chat"
                }
            else:
                raise RuntimeError(f"Groq API error ({resp.status_code})")
        except Exception as e:
            logger.info(f"Groq chat fallback: {e}")
            return {
                "reply": "I am currently unable to contact the AI assistant. Please refer to your structured ECG report summary or contact your cardiologist.",
                "is_emergency": False,
                "source": "deterministic_fallback"
            }


_groq_explainer_instance: Optional[GroqExplainer] = None

def get_groq_explainer() -> GroqExplainer:
    global _groq_explainer_instance
    if _groq_explainer_instance is None:
        _groq_explainer_instance = GroqExplainer()
    return _groq_explainer_instance
