import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from app.ml.ecg_analyzer import ECGAnalyzer
import json

# Force UTF-8 output so Hindi characters print correctly on Windows
sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables from .env
load_dotenv()

def main():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: GEMINI_API_KEY not set.")
        return

    print("Initializing ECG Analyzer...")
    analyzer = ECGAnalyzer(api_key=gemini_key)

    # Use a sample ECG from the repo (path relative to this script)
    sample_path = Path(__file__).parent.parent / "demo_ecgs" / "normal_ecg_sample.png"
    if not os.path.exists(sample_path):
        print(f"Error: Could not find sample ECG at {sample_path}")
        return

    print(f"Reading sample ECG from {sample_path}...")
    with open(sample_path, "rb") as f:
        image_bytes = f.read()

    # Patient context
    patient_context = {
        "age": 45,
        "sex": "Male",
        "conditions": "None",
        "bp_sys": 120,
        "hr": 75
    }

    print("Analyzing ECG...")
    result = analyzer.analyze_ecg(
        image_bytes=image_bytes,
        patient_context=patient_context,
        content_type="image/png"
    )

    print("\n--- Analysis Result ---")
    print(f"Urgency: {result.get('urgency')}")
    print(f"Overall Assessment: {result.get('overall_assessment')}")
    
    print("\n--- Conditions Translated ---")
    for cond in result.get("conditions", [])[:3]:
        name = cond.get("name")
        prob = cond.get("probability")
        en_text = cond.get("explanation_en")
        hi_text = cond.get("explanation_hi")
        
        print(f"[{name}] (Prob: {prob})")
        print(f"  EN: {en_text}")
        print(f"  HI: {hi_text}")
        print("-" * 30)

if __name__ == "__main__":
    main()
