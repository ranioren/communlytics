
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
import sys

# Add current directory to path to allow importing data_utils if needed
sys.path.append(os.getcwd())

# Configuration
# Configuration
load_dotenv()
DB_URI = os.getenv("DB_URI")
CSV_PATH = os.path.join("channel extraction", "merged_data.csv")

# SQLAlchemy Setup
Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    workspace = Column(String)
    channel = Column(String)
    sentences = Column(String) # Content
    user = Column(String) # User name
    comments = Column(String)
    # Calculated fields to persist
    sentiment_score = Column(Float)
    message_type = Column(String)
    is_question = Column(Boolean)
    is_unanswered = Column(Boolean)

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

def migrate_messages():
    print("Connecting to database...")
    engine = create_engine(DB_URI)
    
    # Create tables
    print("Creating tables if they define exist...")
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Load CSV
    print(f"Loading data from {CSV_PATH}...")
    if not os.path.exists(CSV_PATH):
        print("CSV file not found!")
        return
        
    df = pd.read_csv(CSV_PATH)
    
    # Preprocessing to match table schema
    print("Preprocessing data...")
    if 'ts' in df.columns:
        df['timestamp'] = pd.to_datetime(df['ts'], errors='coerce', format='mixed')
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', format='mixed')
        
    df = df.dropna(subset=['timestamp'])
    
    # Fill NA
    df = df.fillna({
        'workspace': 'unknown',
        'channel': 'unknown',
        'sentences': '',
        'user': 'Anonymous',
        'comments': ''
    })
    
    # Re-use logic from data_utils for sentiment/type if possible or just recalculate simply here?
    # Ideally we should use the exact logic.
    # Let's import the logic OR just replicate simple versions to ensure standalone stability
    # Replicating simpler versions for migration script stability
    
    from textblob import TextBlob
    def get_sentiment_score(text):
        blob = TextBlob(str(text))
        polarity = blob.sentiment.polarity
        if polarity <= -0.6: return 1
        elif polarity <= -0.2: return 2
        elif polarity <= 0.2: return 3
        elif polarity <= 0.6: return 4
        else: return 5

    def categorize_message(text):
        text = str(text)
        words = text.split()
        if len(words) <= 3: return "Low Engagement (Short/Emoji)"
        if len(text) > 100 or '?' in text: return "High Engagement (Question/Long)"
        return "Medium Engagement (Response)"

    print("Calculating extra fields...")
    df['sentiment_score'] = df['sentences'].apply(get_sentiment_score)
    df['message_type'] = df['sentences'].apply(categorize_message)
    df['is_question'] = df['sentences'].astype(str).str.contains(r'\?', regex=True)
    df['is_unanswered'] = False # Default, app logic calculates this dynamically usually, or we can compute it.
    # We will leave is_unanswered as False for now, or compute it? The app computes it dynamically `load_data`
    # Creating a persisted field for it is good optimization.
    
    # Bulk Insert
    print("Inserting messages into database...")
    # Convert DF to list of dicts
    records = df[[
        'timestamp', 'workspace', 'channel', 'sentences', 'user', 'comments', 
        'sentiment_score', 'message_type', 'is_question', 'is_unanswered'
    ]].to_dict(orient='records')
    
    # Batch insert
    # using session.bulk_insert_mappings is faster
    session.bulk_insert_mappings(Message, records)
    session.commit()
    print(f"Successfully inserted {len(records)} messages.")
    session.close()

if __name__ == "__main__":
    try:
        migrate_messages()
    except Exception as e:
        print(f"Migration failed: {e}")
