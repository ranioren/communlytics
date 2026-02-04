
import os
import sys
print("Start")
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Dotenv loaded")
except ImportError:
    print("Dotenv missing")

try:
    import google.generativeai as genai
    print("GenAI imported")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        print("API Key found")
    else:
        print("API Key MISSING")
    
    genai.configure(api_key=api_key)
    print("GenAI configured")
except Exception as e:
    print(f"GenAI error: {e}")

try:
    from sqlalchemy import create_engine, text
    print("SQLAlchemy imported")
    db_uri = os.getenv("DB_URI")
    print(f"DB URI: {db_uri}")
    engine = create_engine(db_uri)
    with engine.connect() as conn:
        print("DB Connected")
        res = conn.execute(text("SELECT 1")).fetchall()
        print(f"Query Result: {res}")
except Exception as e:
    print(f"DB Error: {e}")

print("Done")
