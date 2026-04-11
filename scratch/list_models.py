import os
from google import genai
from dotenv import load_dotenv

load_dotenv("backend/.env")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Listing supported models...")
try:
    models = list(client.models.list())
    for m in models:
        print(f"Name: {m.name}")
except Exception as e:
    print(f"List models failed: {e}")
