
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_uri = os.getenv("DB_URI")
try:
    engine = create_engine(db_uri)
    with engine.connect() as conn:
        print("Connected.")
        # Check count
        res = conn.execute(text("SELECT count(*) FROM knowledge_base")).fetchall()
        print(f"Table row count: {res[0][0]}")
        
        # Check one row if exists
        try:
            res_emb = conn.execute(text("SELECT embedding FROM knowledge_base LIMIT 1")).fetchall()
            if res_emb:
                emb_str = res_emb[0][0] # pgvector returns string or list depending on driver? usually string in python if not cast
                print(f"First row retrieved. Embedding type: {type(emb_str)}")
                # approximate length check or parse
                if isinstance(emb_str, str):
                    # [0.1, 0.2, ...]
                    dim = emb_str.count(',') + 1
                    print(f"Approx dimension: {dim}")
            else:
                print("Table is empty.")
        except Exception as e:
            print(f"Could not read embedding: {e}")

except Exception as e:
    print(f"Error: {e}")
