"""
Deprecated Sarvam Assistant Adapter
====================================
This module is maintained solely for backward compatibility.
All report generation and patient explanations are now routed to:
- Deterministic Structured Generator: app.ml.report_generator
- Grounded Groq Explainer (Free Tier): app.ml.groq_explainer
"""

from typing import Optional, Dict, Any, List
from .report_generator import generate_deterministic_report, generate_deterministic_advice
from .groq_explainer import get_groq_explainer


class SarvamAssistantAdapter:
    """Compatibility adapter delegating to deterministic generator and Groq."""

    def __init__(self, api_key: Optional[str] = None):
        self.groq = get_groq_explainer()

    def patient_chat(
        self,
        user_message: str,
        ecg_context: Optional[dict] = None,
        chat_history: Optional[List[dict]] = None
    ) -> dict:
        return self.groq.explain_chat_message(
            message=user_message,
            ecg_analysis=ecg_context,
            chat_history=chat_history
        )

    def summarize_report(self, ecg_analysis: dict, language: str = "en") -> dict:
        if self.groq.is_available:
            return self.groq.explain_report(ecg_analysis, language=language)
        return generate_deterministic_report(ecg_analysis, language=language)

    def generate_advice(
        self,
        vitals: dict,
        risk_tier: str,
        ecg_urgency: Optional[str] = None
    ) -> dict:
        return generate_deterministic_advice(vitals, risk_tier=risk_tier, ecg_urgency=ecg_urgency)


_adapter_instance: Optional[SarvamAssistantAdapter] = None

def get_sarvam_assistant() -> SarvamAssistantAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = SarvamAssistantAdapter()
    return _adapter_instance
