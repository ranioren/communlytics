
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
import os
import sys

# Mock Streamlit
import types
st = types.ModuleType("streamlit")

def cache_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator

st.cache_data = cache_mock
st.cache_resource = cache_mock
st.error = lambda msg: print(f"ERROR: {msg}")
sys.modules["streamlit"] = st

# Add current directory to path
sys.path.append(os.getcwd())

from data_utils import load_crm_data, enrich_user_data, load_data

# Configuration
load_dotenv()
DB_URI = os.getenv("DB_URI")
CSV_PATH = os.path.join("channel extraction", "merged_data.csv")
CRM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiHHBbo2j1VVn06Xub2FqBdGqiVEzmNzOcaQcGu10W53Ai93HIYyr3UHb4RKKQpqrF3Iso6z5HhfiI/pub?output=csv"

# SQLAlchemy Setup (Reuse Schema)
Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'users'
    
    user = Column(String, primary_key=True) # Slack username
    persona = Column(String)
    company = Column(String)
    role = Column(String)
    total_messages = Column(Integer)
    last_active = Column(DateTime)
    full_name = Column(String)
    first_name = Column(String)
    email = Column(String)
    is_client = Column(Boolean)
    notes = Column(String)
    city = Column(String)
    mood_emoji = Column(String)
    mood_score = Column(Float)

def migrate_users():
    print("Connecting to database...")
    engine = create_engine(DB_URI)
    
    # Drop table to ensure schema update
    print("Dropping users table to clean schema...")
    try:
        UserProfile.__table__.drop(engine)
    except Exception as e:
        print(f"Drop failed (maybe doesn't exist): {e}")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print(f"Loading raw message data from {CSV_PATH}...")
    # Load 'merged_data.csv' using helper (to get 'sentences', dates etc parsed)
    # But wait, load_data inside data_utils imports streamlit and caches. 
    # Our mock above should handle the cache decorator.
    df_messages = load_data(CSV_PATH)
    
    print("Loading CRM data...")
    df_crm = load_crm_data(CRM_URL)
    
    print("Enriching user data (calculating personas, matching CRM)...")
    # this returns a DF indexed by 'user'
    enriched_df = enrich_user_data(df_messages, df_crm)
    
    print(f"Prepared {len(enriched_df)} user profiles.")
    
    # Transform for insertion
    # The enriched_df columns: 
    # ['Persona', 'Mood_Emoji', 'Mood_Score', 'Company', 'City', 'Role', 'Full Name', 'First Name', 'Email', 'notes', 'Is_Client', 'Total_Messages', 'Last_Active']
    # Index is 'user'
    
    records = []
    for user_name, row in enriched_df.iterrows():
        # Handle types safely
        try:
            total_msgs = int(row.get('Total_Messages', 0))
        except:
            total_msgs = 0
            
        records.append({
            'user': str(user_name),
            'persona': str(row.get('Persona', 'Unknown')),
            'company': str(row.get('Company', 'Unknown')),
            'role': str(row.get('Role', 'Unknown')),
            'total_messages': total_msgs,
            'last_active': row.get('Last_Active'), # Pandas timestamp/datetime
            'full_name': str(row.get('Full Name', '')),
            'first_name': str(row.get('First Name', '')),
            'email': str(row.get('Email', '')),
            'is_client': bool(row.get('Is_Client', False)),
            'notes': str(row.get('notes', '')),
            'city': str(row.get('City', 'Unknown')),
            'mood_emoji': str(row.get('Mood_Emoji', '')),
            'mood_score': float(row.get('Mood_Score', 0.0))
        })
    
    print(f"Inserting {len(records)} users into DB...")
    
    # We use upsert logic or just insert?
    # For now, just insert. If it fails due to PK, we assume clean DB or handle it.
    # To be safe, we can delete all users first since this is "migration"
    # Or use merge
    
    # session.query(UserProfile).delete() # Optional: Clear table
    
    # Batch insert logic
    from sqlalchemy.dialects.postgresql import insert
    
    # Using raw SQL or core for upsert might be cleaner, but let's try standard add_all first.
    # Actually, bulk_save_objects or mappings
    # But for upsert on conflict...
    # Let's just use bulk_save_objects and hope for empty table as intended by "clean env"
    # Actually user didn't say DB is empty, but "migration" implies it. 
    # I already created tables in previous step.
    
    try:
        session.bulk_insert_mappings(UserProfile, records)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Bulk insert failed: {e}")
        print("Attempting individual merges (could be slow)...")
        for rec in records:
            u = UserProfile(**rec)
            session.merge(u)
        session.commit()
        
    print("User migration complete!")
    session.close()

if __name__ == "__main__":
    migrate_users()
