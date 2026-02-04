
import os
import pickle
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from ai_utils import build_knowledge_base

load_dotenv()

# Configuration
DB_URI = os.getenv("DB_URI")
PKL_PATH = os.path.join("channel extraction", "knowledge_base.pkl")
CSV_PATH = os.path.join("channel extraction", "stof10k.csv")

def upload_to_postgres():
    print(f"Connecting to DB: {DB_URI}")
    try:
        engine = create_engine(DB_URI)
        
        # 1. Load Pickle
        print(f"Loading pickle from {PKL_PATH}...")
        with open(PKL_PATH, 'rb') as f:
            df = pickle.load(f)
            
        print(f"Loaded {len(df)} records.")
        
        with engine.connect() as conn:
            # 2. Add Vector Extension (if not exists)
            print("Ensuring vector extension...")
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            
            # 3. Create Table (if not exists)
            # Embedding-001 has 768 dimensions
            print("Creating table 'knowledge_base' if needed...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id SERIAL PRIMARY KEY,
                    question TEXT,
                    answer TEXT,
                    embedding vector(768)
                );
            """))
            
            # 4. Truncate Table (Clear old data)
            print("Clearing old data...")
            conn.execute(text("TRUNCATE TABLE knowledge_base;"))
            conn.commit()
            
            # 5. Insert Data
            print("Inserting new vectors...")
            data_to_insert = []
            for _, row in df.iterrows():
                # specific format for pgvector
                emb_list = row['embedding']
                # Ensure it is a list
                if hasattr(emb_list, 'tolist'):
                    emb_list = emb_list.tolist()
                
                data_to_insert.append({
                    "question": row['Question'],
                    "answer": row['Answer'],
                    "embedding": str(emb_list) # PGVector expects string representation list like '[0.1, ...]'
                })
            
            # Bulk Insert
            # Bulk Insert in Batches
            batch_size = 100
            total_inserted = 0
            
            for i in range(0, len(data_to_insert), batch_size):
                batch = data_to_insert[i : i + batch_size]
                conn.execute(text("""
                    INSERT INTO knowledge_base (question, answer, embedding)
                    VALUES (:question, :answer, :embedding)
                """), batch)
                total_inserted += len(batch)
                print(f"Inserted {total_inserted}/{len(data_to_insert)} rows...")
            
            conn.commit()
            print("Upload complete!")
            
    except Exception as e:
        print(f"Error during upload: {e}")

if __name__ == "__main__":
    print("--- Step 1: Rebuilding Knowledge Base Vectors (Gemini) ---")
    # This calls the function in ai_utils which uses models/embedding-001
    # try:
    #     build_knowledge_base(input_csv_path=CSV_PATH, output_pkl_path=PKL_PATH)
    # except Exception as e:
    #     print(f"Build failed: {e}")
    #     exit(1)
        
    print("\n--- Step 2: Uploading to Postgres ---")
    upload_to_postgres()
