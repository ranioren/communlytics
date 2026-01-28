
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URI = os.getenv("DB_URI")

def migrate():
    if not DB_URI:
        print("Error: DB_URI not found in environment variables.")
        return

    print(f"Connecting to database...")
    engine = create_engine(DB_URI)

    with engine.connect() as conn:
        print("Creating app_cache table if not exists...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_cache (
                key TEXT PRIMARY KEY,
                value BYTEA,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()
        print("Migration complete. 'app_cache' table created.")

if __name__ == "__main__":
    migrate()
