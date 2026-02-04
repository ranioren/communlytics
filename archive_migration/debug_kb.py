import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URI = os.getenv("DB_URI")
if not DB_URI:
    print("DB_URI not found in environment.")
    exit(1)

try:
    engine = create_engine(DB_URI)
    with engine.connect() as conn:
        # Check if table exists first
        result = conn.execute(text("SELECT to_regclass('public.knowledge_base');")).fetchone()
        if not result[0]:
            print("Table 'knowledge_base' does NOT exist.")
        else:
            count = conn.execute(text("SELECT count(*) FROM knowledge_base")).fetchone()[0]
            print(f"Table 'knowledge_base' exists. Row count: {count}")

except Exception as e:
    print(f"Error connecting to DB: {e}")
