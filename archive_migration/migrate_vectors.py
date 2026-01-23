
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector
import pickle
import os
import sys

# Mock Streamlit
import types
st = types.ModuleType("streamlit")
st.cache_data = lambda func: func
sys.modules["streamlit"] = st

# Configuration
load_dotenv()
DB_URI = os.getenv("DB_URI")
KB_PATH = os.path.join("channel extraction", "knowledge_base.pkl")

Base = declarative_base()

class KnowledgeBaseItem(Base):
    __tablename__ = 'knowledge_base'
    
    id = Column(Integer, primary_key=True)
    question = Column(String)
    answer = Column(String)
    embedding = Column(Vector(768))

def migrate_vectors():
    print("Connecting to database...")
    engine = create_engine(DB_URI)
    
    # Enable Extension
    print("Enabling pgvector extension...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # Create Table
    print("Creating table knowledge_base...")
    # Clean recreate
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print(f"Loading pickle from {KB_PATH}...")
    if not os.path.exists(KB_PATH):
        print("Pickle file not found!")
        return

    with open(KB_PATH, 'rb') as f:
        df = pickle.load(f)
    
    print(f"Loaded {len(df)} records. Inserting into DB...")
    
    # Prepare objects
    items = []
    for _, row in df.iterrows():
        items.append(KnowledgeBaseItem(
            question=row['Question'],
            answer=row['Answer'],
            embedding=row['embedding'] # Expecting list or np array
        ))
        
    # Bulk insert
    try:
        session.bulk_save_objects(items)
        session.commit()
        print(f"Successfully inserted {len(items)} vectors.")
        
        # Create Index (IVFFlat or HNSW)
        # HNSW is better for recall.
        print("Creating HNSW index for fast search...")
        with engine.connect() as conn:
            # Drop index if exists to ensure clean state or if we did drop_all
            # partial index syntax:
            conn.execute(text("CREATE INDEX ON knowledge_base USING hnsw (embedding vector_cosine_ops)"))
            conn.commit()
        print("Index created.")
        
    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate_vectors()
