import os
import requests
import json

# Local paths for generated samples
SAMPLES = [
    {
        "name": "Normal_Sinus_Rhythm.png",
        "path": r"C:\Users\adhya\.gemini\antigravity\brain\113a7d1e-bff4-45a7-bdd4-743258e95c39\normal_ecg_sample_1775915908113.png",
        "context": {"age": 45, "sex": "Male", "conditions": "Reference Baseline (PhysioNet inspired)"}
    },
    {
        "name": "Atrial_Fibrillation.png",
        "path": r"C:\Users\adhya\.gemini\antigravity\brain\113a7d1e-bff4-45a7-bdd4-743258e95c39\afib_ecg_sample_1775916102465.png",
        "context": {"age": 72, "sex": "Female", "conditions": "New onset palpitations (PTB-XL style)"}
    },
    {
        "name": "Acute_Anterior_STEMI.png",
        "path": r"C:\Users\adhya\.gemini\antigravity\brain\113a7d1e-bff4-45a7-bdd4-743258e95c39\stemi_ecg_sample_1775916138636.png",
        "context": {"age": 58, "sex": "Male", "conditions": "Severe retrospectal pain (Emergency Case)"}
    },
    {
        "name": "LBBB.png",
        "path": r"C:\Users\adhya\.gemini\antigravity\brain\113a7d1e-bff4-45a7-bdd4-743258e95c39\lbbb_ecg_sample_1775916414579.png",
        "context": {"age": 68, "sex": "Male", "conditions": "Chronic cardiomyopathy"}
    },
    {
        "name": "Ventricular_Tachycardia.png",
        "path": r"C:\Users\adhya\.gemini\antigravity\brain\113a7d1e-bff4-45a7-bdd4-743258e95c39\vt_ecg_sample_1775916572822.png",
        "context": {"age": 62, "sex": "Male", "conditions": "Recurrent syncope (High Urgency)"}
    }
]

API_URL = "http://localhost:8000/api/v1/ecg/upload"

def upload_samples():
    print("--- STARTING LOCAL SAMPLE UPLOAD ---")
    
    for sample in SAMPLES:
        print(f"Processing: {sample['name']}...")
        
        path = sample['path']
        if not os.path.exists(path):
            print(f"  ❌ FILE NOT FOUND: {path}")
            continue
            
        # Upload to API
        try:
            with open(path, 'rb') as f:
                content = f.read()
                
            form_data = {
                "user_id": "default_user",
                "age": sample['context']['age'],
                "sex": sample['context']['sex'],
                "conditions": sample['context']['conditions']
            }
            
            files = {
                'file': (sample['name'], content, 'image/png')
            }
            
            print(f"  Uploading {sample['name']} to Gemini 2.5 Flash...")
            resp = requests.post(API_URL, data=form_data, files=files, timeout=60)
            
            if resp.status_code == 200:
                print(f"  ✅ SUCCESS: {sample['name']}")
                data = resp.json()
                print(f"     Diagnosis: {data.get('top_condition')} ({data.get('top_condition_prob', 0)*100:.1f}%)")
                print(f"     Urgency:   {data.get('urgency')}")
            else:
                print(f"  ❌ FAILED ({resp.status_code}): {resp.text}")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")

    print("\n--- SAMPLE UPLOAD COMPLETE ---")

    print("\n--- SAMPLE UPLOAD COMPLETE ---")

if __name__ == "__main__":
    upload_samples()
