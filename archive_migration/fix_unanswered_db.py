
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import timedelta
import os

import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
DB_URI = os.getenv("DB_URI")

def fix_unanswered_questions():
    print("Connecting to DB...")
    engine = create_engine(DB_URI)
    
    print("Loading data...")
    query = "SELECT * FROM messages"
    df = pd.read_sql(query, engine)
    
    if df.empty:
        print("No data found.")
        return

    print(f"Loaded {len(df)} rows. Processing...")
    
    # Check Columns
    # The DB probably has 'timestamp' instead of 'ts' if it was migrated raw
    if 'timestamp' in df.columns:
        df['ts'] = pd.to_datetime(df['timestamp'])
    elif 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts'])
    else:
        print(f"Error: Timestamp column not found. Columns: {df.columns}")
        return

    # User
    df['user'] = df['user'].fillna("Anonymous")
    
    # Sentences
    if 'sentences' not in df.columns and 'content' in df.columns:
         df['sentences'] = df['content']
         
    df['is_question'] = df['sentences'].astype(str).str.contains(r'\?', regex=True)
    
    # We want to identify IDs that ARE unanswered.
    # Initialize all as False first (reset) - we will update DB explicitly.
    unanswered_ids = []
    
    # Logic from data_utils.py
    for channel_name, channel_data in df.groupby('channel'):
        if channel_data['workspace'].iloc[0] == 'reddit':
            continue
            
        responses = channel_data[channel_data['sentences'].astype(str).str.contains('@')]
        questions = channel_data[channel_data['is_question']]
        
        for idx, question in questions.iterrows():
            time_window_end = question['ts'] + timedelta(days=2)
            valid_responses = responses[
                (responses['ts'] > question['ts']) & 
                (responses['ts'] <= time_window_end)
            ]
            
            user_name = question['user']
            if user_name == "Anonymous": continue
            
            q_text = str(question['sentences'])
            if '@' in q_text: continue
            q_lower = q_text.lower()
            if 'http' in q_lower or 'www' in q_lower: continue
            if len(q_text.split()) < 8: continue
            
            is_answered = valid_responses['sentences'].astype(str).str.contains(user_name, case=False).any()
            
            if not is_answered:
                # Store the ID (assuming 'id' column exists, usually SERIAL PK)
                # If dataframe index is not the PK, we need to check columns.
                # In read_sql without index_col, usually 'id' is a column if it exists.
                if 'id' in question:
                    unanswered_ids.append(int(question['id']))
    
    print(f"Found {len(unanswered_ids)} unanswered questions.")
    
    if not unanswered_ids:
        print("No updates needed.")
        return

    print("Updating database...")
    with engine.connect() as conn:
        # Batch update is safer
        # 1. Reset all to False
        conn.execute(text("UPDATE messages SET is_unanswered = FALSE"))
        
        # 2. Set True for specific IDs
        # Chunking for safety
        chunk_size = 1000
        for i in range(0, len(unanswered_ids), chunk_size):
            chunk = unanswered_ids[i:i+chunk_size]
            if not chunk: continue
            
            # Format list for SQL IN clause
            ids_tuple = tuple(chunk)
            sql = text(f"UPDATE messages SET is_unanswered = TRUE WHERE id IN :ids")
            conn.execute(sql, {"ids": ids_tuple})
            print(f"Updated chunk {i}-{i+len(chunk)}")
            
        conn.commit()
    
    print("Database updated successfully.")

if __name__ == "__main__":
    fix_unanswered_questions()
