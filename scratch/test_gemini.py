import os
from google import genai
from dotenv import load_dotenv

load_dotenv("backend/.env")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

try:
    print("Testing gemini-1.5-flash...")
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Hello, say '1.5-flash is working'"
    )
    print(f"Response: {response.text}")
except Exception as e:
    print(f"gemini-1.5-flash failed: {e}")

try:
    print("\nTesting gemini-2.0-flash...")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hello, say '2.0-flash is working'"
    )
    print(f"Response: {response.text}")
except Exception as e:
    print(f"gemini-2.0-flash failed: {e}")

try:
    print("\nTesting gemini-2.0-flash-exp...")
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents="Hello, say '2.0-flash-exp is working'"
    )
    print(f"Response: {response.text}")
except Exception as e:
    print(f"gemini-2.0-flash-exp failed: {e}")
