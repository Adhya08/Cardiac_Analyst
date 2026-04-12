import os
import requests
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.ml.ecg_analyzer import ECGAnalyzer

load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))
api_key = os.getenv('GEMINI_API_KEY')
analyzer = ECGAnalyzer(api_key=api_key)

test_images = [
    {'name': 'Normal ECG', 'url': 'https://raw.githubusercontent.com/Deep-k-Das/ECG-Image-Classification/main/dataset/Normal/1.png'},
    {'name': 'Myocardial Infarction', 'url': 'https://raw.githubusercontent.com/Deep-k-Das/ECG-Image-Classification/main/dataset/Myocardial%20Infarction/1.png'}
]

print('--- ECG Clinical Accuracy Test Suite ---')
for img in test_images:
    print(f"\nRunning AI against: {img['name']}")
    try:
        data = requests.get(img['url']).content
        if len(data) < 1000:
            print('Failed to download image.')
            continue
        res = analyzer.analyze_ecg(data, {'age': 45, 'sex': 'M'}, 'image/png')
        
        fallback = "Analysis incomplete" in str(res)
        print(f'Is AI Fallback? {fallback}')
        if fallback:
            print(f'Reason: {res.get("image_quality_note")}')
        print(f'Top Condition Found: {res["conditions"][0]["name"]} ({res["conditions"][0]["probability"] * 100}%)')
        print(f'Urgency Level: {res["urgency"]}')
        print(f'GradCAM Heatmaps Generated: {len(res.get("gradcam_highlights", []))}')
    except Exception as e:
        print('Error:', e)
