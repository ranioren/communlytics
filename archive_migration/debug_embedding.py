
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print("Attempting to embed...")
try:
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content="Test string",
        task_type="retrieval_query"
    )
    print("Embedding successful!")
    print(f"Dimension: {len(result['embedding'])}")
except Exception as e:
    print(f"Embedding failed: {e}")
