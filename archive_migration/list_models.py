
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print("Listing available models...")


with open("models_out.txt", "w", encoding="utf-8") as f:
    try:
        for m in genai.list_models():
            if 'embedContent' in m.supported_generation_methods:
                f.write(f"Name: {m.name}\n")
                f.write(f"Supported Methods: {m.supported_generation_methods}\n")
                f.write("-" * 20 + "\n")
        print("Models written to models_out.txt")
    except Exception as e:
        f.write(f"Error listing models: {e}")
