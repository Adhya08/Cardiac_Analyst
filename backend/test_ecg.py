import os
import requests
import json
from dotenv import load_dotenv

# Add app to path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.ecg_analyzer import ECGAnalyzer

def test():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("NO API KEY!")
        return

    analyzer = ECGAnalyzer(api_key=api_key)

    # Download a sample normal ECG image
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/ECG_Normal.jpg/800px-ECG_Normal.jpg"

    try:
        from PIL import Image, ImageDraw
        import io
        
        print("Generating synthetic test image...")
        img = Image.new('RGB', (800, 400), color = (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.line([(0,200), (100,200), (120, 150), (140, 300), (160, 50), (180, 250), (200, 200), (800, 200)], fill=(0,0,0), width=3)
        d.text((10,10), "TEST ECG", fill=(0,0,0))
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="JPEG")
        img_data = img_byte_arr.getvalue()
        
        print("Analyzing with Gemini Vision...")
        res = analyzer.analyze_ecg(img_data, {"age": 45, "sex": "Male"}, "image/jpeg")
        
        print("\n--- RESULTS ---")
        if res.get("image_quality") == "poor" and "Could not parse" in res.get("image_quality_note", "") or "incomplete" in str(res):
            print("FAILED: Using fallback data.")
            print("Fallback Reason:", res.get("image_quality_note"))
        else:
            print("SUCCESS! Real Gemini analysis executed.")
            print(f"Top Condition: {res['conditions'][0]['name']} (Probability: {res['conditions'][0]['probability']})")
            print(f"Urgency: {res['urgency']}")
            print(f"GradCAM Highlights: {len(res.get('gradcam_highlights', []))} found.")
            print(f"Total Conditions Scored: {len(res['conditions'])}")
            print(f"\nOverall Assessment: {res['overall_assessment']}")

    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    test()
