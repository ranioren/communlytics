
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_uri = os.getenv("DB_URI")

try:
    engine = create_engine(db_uri)
    with engine.connect() as conn:
        print(f"Connected to: {engine.url.database}")
        
        # List tables in public schema
        sql = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        result = conn.execute(sql).fetchall()
        
        print("\nTables found:")
        for row in result:
            t_name = row[0]
            try:
                count = conn.execute(text(f"SELECT count(*) FROM {t_name}")).scalar()
                print(f"- {t_name}: {count} rows")
            except Exception as e:
                print(f"- {t_name}: Error ({e})")

except Exception as e:
    print(f"Error: {e}")
