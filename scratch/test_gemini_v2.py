import os
from google import genai
from dotenv import load_dotenv

load_dotenv("backend/.env")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Listing supported models...")
try:
    for model in client.models.list():
        print(f"Model: {model.name}, DisplayName: {model.display_name}, SupportedMethods: {model.supported_generation_methods}")
except Exception as e:
    print(f"List models failed: {e}")

models_to_test = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-2.0-flash-001"]
for m in models_to_test:
    try:
        print(f"\nTesting {m}...")
        response = client.models.generate_content(
            model=m,
            contents="Hello"
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"{m} failed: {e}")
