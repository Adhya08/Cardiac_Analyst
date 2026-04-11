import os
from google import genai
from dotenv import load_dotenv

load_dotenv("backend/.env")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

try:
    print("Testing gemini-2.5-flash...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello"
    )
    print(f"Response: {response.text}")
except Exception as e:
    print(f"gemini-2.5-flash failed: {e}")
