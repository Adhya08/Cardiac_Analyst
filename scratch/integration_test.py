import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_suite():
    print("--- TC1: Update Profile ---")
    profile_data = {
        "age": 55,
        "sex": "Male",
        "is_smoker": True,
        "is_diabetic": False,
        "has_family_history": True,
        "height_cm": 175
    }
    r1 = requests.put(f"{BASE_URL}/user/profile", params={"user_id": "test_user"}, json=profile_data)
    print(f"Status: {r1.status_code}")
    print(r1.json())

    print("\n--- TC2: Log Vitals (Sanity Check) ---")
    vitals_data = {
        "bp_sys": 175,
        "bp_dia": 105,
        "hr": 110,
        "weight": 95,
        "spo2": 92,
        "glucose": 220,
        "cholesterol": 280
    }
    r2 = requests.post(f"{BASE_URL}/vitals", params={"user_id": "test_user"}, json=vitals_data)
    print(f"Status: {r2.status_code}")
    res2 = r2.json()
    if r2.status_code == 200:
        print(f"Risk Score: {res2.get('risk_score')}%")
        print(f"Risk Tier: {res2.get('risk_tier')}")
        if res2.get('clinical_audit'):
            print(f"Audit Result: {'Flagged' if res2['clinical_audit']['is_model_wrong'] else 'Passed'}")
            print(f"Expected Risk: {res2['clinical_audit']['expected_risk']}")
            if res2['clinical_audit']['fixes']:
                print(f"Suggested Fixes: {res2['clinical_audit']['fixes'][:2]}")
    else:
        print(res2)

    print("\n--- TC3: ECG History Check ---")
    r3 = requests.get(f"{BASE_URL}/ecg/history", params={"user_id": "test_user"})
    print(f"Status: {r3.status_code}")
    print(f"Sessions: {r3.json().get('total', 0)}")

    print("\n--- TC4: Emergency Triage (High Risk) ---")
    triage_data = {
        "symptoms": [True, True, True, False, False, False, False, False], # 8 symptoms
        "lat": 28.6139,
        "lon": 77.2090,
        "user_id": "test_user"
    }
    r4 = requests.post(f"{BASE_URL}/emergency/triage", json=triage_data)
    print(f"Status: {r4.status_code}")
    res4 = r4.json()
    if r4.status_code == 200:
        print(f"Severity: {res4.get('severity')}")
        print(f"Risk Score: {res4.get('risk_score')}")
        print(f"Hospitals Found: {len(res4.get('hospitals', []))}")
    else:
        print(res4)

    print("\n--- TC5: Vitals History (Trend) ---")
    r5 = requests.get(f"{BASE_URL}/vitals/history", params={"user_id": "test_user"})
    print(f"Status: {r5.status_code}")
    res5 = r5.json()
    print(f"Total Logs: {res5.get('count', 0)}")
    print(f"Trend: {res5.get('trend')}")

if __name__ == "__main__":
    test_suite()
