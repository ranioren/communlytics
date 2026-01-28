import pandas as pd
import os
import json
from textblob import TextBlob
from datetime import timedelta
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS

# from transformers import pipeline # Lazy loaded
# import torch # Lazy loaded
from sqlalchemy import create_engine, text
import io


# --- Helper Functions ---
# Load from environment variable (security best practice)
DB_URI = os.getenv("DB_URI")

@st.cache_resource
def get_db_engine():
    return create_engine(DB_URI)

@st.cache_data(ttl=300) # shorter cache for DB
def load_data(path, last_modified=None):
    """
    Loads data from PostgreSQL database.
    Falls back to CSV if DB connection fails.
    """
    try:
        engine = get_db_engine()
        query = "SELECT * FROM messages"
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print("DB empty, falling back to CSV...")
            raise Exception("Empty DB")
            
        # Post-processing to match App expectations
        # Rename persisted columns to App's display names
        df = df.rename(columns={
            "sentiment_score": "Sentiment Score",
            "message_type": "Message Type",
            "timestamp": "ts"
        })
        
        # Ensure timestamp is datetime
        df['ts'] = pd.to_datetime(df['ts'])
        df['date'] = df['ts'].dt.date
        
        # Fill NA
        df['user'] = df['user'].fillna("Anonymous")
        
        # Ensure is_unanswered is present (it is in DB)
        # Verify specific columns needed by app
        if 'sentences' not in df.columns and 'content' in df.columns:
             df['sentences'] = df['content']
             
        # Sort
        df = df.sort_values(by=['channel', 'ts'])

        # --- RESTORED LOGIC FOR UNANSWERED QUESTIONS ---
        # OPTIMIZATION: Logic moved to DB. We trust the DB column 'is_unanswered' is now accurate.
        # This removes the O(N^2) loop that was slowing down startup.
        
        return df
        
    except Exception as e:
        print(f"DB Load Failed: {e}. Loading from CSV at {path}")
        # Fallback to original CSV logic
    
    if not os.path.exists(path):
        st.error(f"Data file not found at: {path}")
        return pd.DataFrame()
    
    # Load data
    df = pd.read_csv(path)
    
    # Preprocessing
    if 'timestamp' in df.columns:
        df['ts'] = pd.to_datetime(df['timestamp'], errors='coerce', format='mixed')
    else:
        df['ts'] = pd.to_datetime(df['ts'], errors='coerce', format='mixed')
        
    # Filter rows with invalid timestamps
    df = df.dropna(subset=['ts'])
    df['date'] = df['ts'].dt.date
    
    # Handle user column for Reddit (which might be NaN)
    if 'user' in df.columns:
        df['user'] = df['user'].fillna("Anonymous")
    else:
        df['user'] = "Anonymous"

    if 'sentences' in df.columns:
        df['sentences'] = df['sentences'].astype(str)
    elif 'sentence' in df.columns:
        df['sentences'] = df['sentence'].astype(str)

    # Categorization Logic
    def categorize_message(text):
        words = text.split()
        if len(words) <= 3:
            return "Low Engagement (Short/Emoji)"
        if len(text) > 100 or '?' in text:
            return "High Engagement (Question/Long)"
        return "Medium Engagement (Response)"

    df['Message Type'] = df['sentences'].apply(categorize_message)
    
    # Sentiment Analysis
    def get_sentiment_score(text):
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        if polarity <= -0.6: return 1
        elif polarity <= -0.2: return 2
        elif polarity <= 0.2: return 3
        elif polarity <= 0.6: return 4
        else: return 5

    df['Sentiment Score'] = df['sentences'].apply(get_sentiment_score)
    
    # --- Unanswered Question Logic ---
    # Skip this logic for Reddit data (no user information)
    df['is_question'] = df['sentences'].str.contains(r'\?', regex=True)
    df['is_unanswered'] = False
    
    # Sort by time to ensure order
    df = df.sort_values(by=['channel', 'ts'])
    
    # We will iterate channel by channel, but skip Reddit workspace
    for channel_name, channel_data in df.groupby('channel'):
        # Skip Reddit channels (no user data to match)
        if channel_data['workspace'].iloc[0] == 'reddit':
            continue
            
        # Get potential responses: messages with '@'
        responses = channel_data[channel_data['sentences'].str.contains('@')]
        
        # Get questions
        questions = channel_data[channel_data['is_question']]
        
        for idx, question in questions.iterrows():
            # Look for response in next 24 hours
            time_window_end = question['ts'] + timedelta(days=1)
            
            # Filter responses that are after question AND before window end
            valid_responses = responses[
                (responses['ts'] > question['ts']) & 
                (responses['ts'] <= time_window_end)
            ]
            
            user_name = question['user']
            
            # Skip if user is Anonymous (Reddit data)
            if user_name == "Anonymous":
                continue
            
            # Filter out potentially low-quality or non-questions
            q_text = str(question['sentences'])
            
            # 1. Skip if contains mention (@) - likely a reply or direct address
            if '@' in q_text:
                continue
                
            # 2. Skip if contains URL - likely sharing a link rather than asking
            q_lower = q_text.lower()
            if 'http' in q_lower or 'www' in q_lower:
                continue
            
            # 3. Skip short questions (< 8 words)
            if len(q_text.split()) < 8:
                continue
            
            # Check if any valid response contains the user name
            is_answered = valid_responses['sentences'].str.contains(user_name, case=False).any()
            
            if not is_answered:
                 df.at[idx, 'is_unanswered'] = True

    return df

@st.cache_data
def load_crm_data(csv_url):
    """
    Loads CRM data from a public Google Sheet CSV directly so it works like a static "mock" CRM.
    """
    try:
        # We need to verify SSL certificate (or ignore it if necessary for this specific link, 
        # but using requests usually handles it better or we can pass verify=False)
        # For simplicity with pandas:
        storage_options = {'User-Agent': 'Mozilla/5.0'}
        # Note: If SSL errors persist, we might need requests.get -> io.StringIO -> read_csv
        # trying simple read_csv first.
        crm_df = pd.read_csv(csv_url, storage_options=storage_options)
        
        # Normalize columns if needed (based on debug output: ['First Name', 'Last Name', ...])
        # Let's ensure 'user' or 'full_name' column exists for easy lookup.
        # Assuming we join First + Last
        if 'First Name' in crm_df.columns and 'Last Name' in crm_df.columns:
            crm_df['Full Name'] = crm_df['First Name'].astype(str) + " " + crm_df['Last Name'].astype(str)
            
        return crm_df
    except Exception as e:
        st.error(f"Failed to load CRM data: {e}")
        return pd.DataFrame()

def check_is_client(user_name, crm_df):
    """
    Checks if a user exists in the CRM dataframe.
    Returns: (is_client (bool), match_details (Series or None))
    """
    if crm_df.empty or not user_name:
        return False, None
        
    # Standardize
    user = str(user_name).lower().strip()
    
    # 1. Exact Full Name Match
    # Assuming crm_df has 'Full Name' created in load_crm_data
    if 'Full Name' in crm_df.columns:
        match = crm_df[crm_df['Full Name'].str.lower() == user]
        if not match.empty:
            return True, match.iloc[0]
            
    # 2. First Name Match (Fallback/Heuristic)
    # Split slack user by space -> get first token
    first_name_guess = user.split()[0]
    if 'First Name' in crm_df.columns:
        match = crm_df[crm_df['First Name'].str.lower() == first_name_guess]
        if not match.empty:
            return True, match.iloc[0]
            
    return False, None

@st.cache_resource
def load_keyword_extractor():
    """
    Loads the technical keyword extraction model.
    Cached to avoid reloading on every run.
    """
    try:
        from transformers import pipeline
        # device=0 if cuda is available, else -1 for cpu. 
        # auto-detection is safer but let's stick to cpu/auto for compatibility
        pipe = pipeline("text2text-generation", model="ilsilfverskiold/tech-keywords-extractor")
        return pipe
    except Exception as e:
        st.error(f"Failed to load keyword extraction model: {e}")
        return None

def extract_tech_keywords(text):
    """
    Extracts technical keywords from text using the Hugging Face model.
    Handles text chunking to respect model limits.
    """
    if not text or not text.strip():
        return ""
        
    pipe = load_keyword_extractor()
    if not pipe:
        return text # Fallback to raw text if model fails
        
    # Chunking strategy: rough character chunks to avoid token limits (model max ~512 tokens usually)
    # 2000 chars is roughly 400-500 words, might be safe for T5-based models often used for this.
    # Let's be conservative with 1000 chars.
    chunk_size = 1000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    extracted_keywords = []
    
    # Process max 10 chunks to avoid timeout
    for chunk in chunks[:10]:
        try:
            result = pipe(chunk)
            # Result format for text2text is usually [{'generated_text': '...'}]
            if result and len(result) > 0:
                 extracted_keywords.append(result[0]['generated_text'])
        except Exception as e:
            continue
            
    return " ".join(extracted_keywords)

def generate_wordcloud(text):
    """
    Generates a word cloud image from the provided text.
    Uses AI model to filter for technical keywords first.
    """
    if not text or len(text.strip()) == 0:
        return None

    # Step 1: Extract only technical keywords
    # This might take time, so it's good that it's inside the spinner in app.py
    tech_text = extract_tech_keywords(text)
    
    # If extraction returned empty (rare), fallback to original
    final_text = tech_text if tech_text.strip() else text

    # Custom color function for dark blue shades
    def blue_color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        # HSL: Hue=240 (Blue), Saturation=100%, Lightness=random between 20-50%
        return "hsl(240, 100%, {}%)".format(np.random.randint(20, 50))

    try:
        wc = WordCloud(
            background_color="rgba(0,0,0,0)", # Transparent
            mode="RGBA",
            max_words=50,
            width=800,
            height=400,
            color_func=blue_color_func,
            font_path=None 
        ).generate(final_text)
        
        return wc.to_array()
    except Exception as e:
        st.error(f"Error generating word cloud: {e}")
        return None

def get_cached_wordcloud_from_db():
    """
    Retrieves the pre-calculated wordcloud image from the Postgres 'app_cache' table.
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT value FROM app_cache WHERE key = 'global_wordcloud'"))
            row = result.fetchone()
            
            if row and row[0]:
                import matplotlib.pyplot as plt
                import matplotlib.image as mpimg
                # Bytes to Image
                image = mpimg.imread(io.BytesIO(row[0]), format='png')
                return image
    except Exception as e:
        print(f"Failed to fetch cached wordcloud: {e}")
    return None

def save_wordcloud_to_db(image_bytes):
    """
    Saves the wordcloud bytes to the Postgres 'app_cache' table.
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            # Upsert
            conn.execute(text("""
                INSERT INTO app_cache (key, value, updated_at)
                VALUES ('global_wordcloud', :val, NOW())
                ON CONFLICT (key) 
                DO UPDATE SET value = :val, updated_at = NOW()
            """), {"val": image_bytes})
            conn.commit()
            return True
    except Exception as e:
        print(f"Failed to save wordcloud cache: {e}")
        return False


def get_user_persona(metrics_df, messages_series):
    total_msgs = len(messages_series)
    
    # Rule 1: Passive Reader
    if total_msgs < 5:
        return "Passive Reader/Lurker", 1.0, "Extremely low message count."

    # Calculate features
    avg_len = messages_series.str.len().mean()
    question_ratio = metrics_df['is_question'].mean()
    low_engagement_ratio = (metrics_df['Message Type'] == 'Low Engagement (Short/Emoji)').mean()
    
    # Keywords
    text_corpus = " ".join(messages_series.str.lower())
    advocate_keywords = ['feature', 'roadmap', 'bug', 'release', 'update', 'suggestion', 'plz', 'please', 'add']
    learner_keywords = ['how', 'why', 'help', 'error', 'question', 'fail', 'issue', 'problem']
    
    # Scoring (Heuristics)
    scores = {}
    
    # Feature Advocate: Mentions product terms
    scores['Feature Advocate'] = sum(text_corpus.count(w) for w in advocate_keywords) / total_msgs * 20
    
    # Active Learner: Asks questions, uses help words
    scores['Active Learner'] = (question_ratio * 10) + (sum(text_corpus.count(w) for w in learner_keywords) / total_msgs * 10)
    
    # Expert Contributor: Long messages, few questions
    # Penalize if question ratio is high
    expert_base = (avg_len / 50) * 5 # 5 points for every 50 chars average
    scores['Expert Contributor'] = expert_base * (1.0 - question_ratio)
    
    # Social Connector: Short messages, emojis (Low engagement type includes emojis), positive sentiment (implied check)
    # We'll use low_engagement_ratio as proxy for "chatty/social"
    scores['Social Connector'] = low_engagement_ratio * 15
    
    # Determine Winner
    best_persona = max(scores, key=scores.get)
    max_score = scores[best_persona]
    total_score = sum(scores.values())
    
    confidence = max_score / total_score if total_score > 0 else 0.0
    # Cap confidence at 0.95 unless it's Passive Reader
    confidence = min(confidence, 0.95)
    
    descriptions = {
        "Expert Contributor": "Initiates complex discussions, detailed solutions.",
        "Active Learner": "Frequently asks questions, uses community as resource.",
        "Feature Advocate": "Discusses roadmap, suggests features, critical of updates.",
        "Social Connector": "Socializes, welcomes members, uses emojis.",
        "Passive Reader/Lurker": "Low participation."
    }
    
    return best_persona, confidence, descriptions[best_persona]

def calculate_all_user_personas(df):
    """
    Calculates persona for all users in the dataframe.
    Returns a dictionary: {User: Persona}
    """
    user_personas = {}
    
    # helper to avoid repeated slicing
    # We need metrics per user. 
    # Group by user and apply the logic?
    # get_user_persona needs: metrics_df (filtered for user) and messages_series
    
    # Optimizing: Calculate global metrics first if possible, but our function takes filtered DF.
    # Let's just loop for now, it should be fast enough for < 1000 users.
    
    for user, user_df in df.groupby('user'):
        persona, _, _ = get_user_persona(user_df, user_df['sentences'])
        user_personas[user] = persona
        
    return user_personas

def transform_reddit_to_csv(jsonl_path, csv_path):
    """
    Transforms Reddit JSONL data to CSV format with specific column mapping.
    Maps: 'sub' -> 'channel', 'title' -> 'sentence', 'selftext' -> 'comments', 'created_utc' -> 'created_utc'
    Adds: 'workspace' = 'reddit'
    """
    data = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    
    df = pd.DataFrame(data)
    
    # Column Mapping
    rename_map = {
        "sub": "channel",
        "title": "sentence",
        "selftext": "comments",
        "created_utc": "created_utc"
    }
    df = df.rename(columns=rename_map)
    
    # Add static workspace
    df['workspace'] = 'reddit'
    
    # Keep only relevant columns
    cols_to_keep = ["workspace", "channel", "sentence", "comments", "created_utc"]
    available_cols = [c for c in cols_to_keep if c in df.columns]
    
    df_out = df[available_cols]
    df_out.to_csv(csv_path, index=False)
    return df_out

def merge_slack_reddit(slack_csv_path, reddit_csv_path, output_csv_path):
    """
    Merges Slack and Reddit CSVs into a single standardized CSV.
    Standardizes:
    - timestamp: From Slack 'ts' and Reddit 'created_utc'
    - sentences: From Slack 'sentences' and Reddit 'sentence'
    - Includes 'user' (Slack) and 'comments' (Reddit) separately.
    """
    # Load Slack
    df_slack = pd.read_csv(slack_csv_path)
    # Slack ts is often ISO string in this dataset, but we will handle both
    df_slack['timestamp'] = pd.to_datetime(df_slack['ts'], errors='coerce')
    
    # Load Reddit
    df_reddit = pd.read_csv(reddit_csv_path)
    # Reddit created_utc is unix timestamp
    df_reddit['timestamp'] = pd.to_datetime(df_reddit['created_utc'], unit='s', errors='coerce')
    # Rename sentence to sentences to match Slack
    df_reddit = df_reddit.rename(columns={"sentence": "sentences"})
    
    # Define shared columns
    shared_cols = ["timestamp", "workspace", "channel", "sentences", "user", "comments"]
    
    # Ensure all columns exist in both (add missing as NaN)
    for col in shared_cols:
        if col not in df_slack.columns:
            df_slack[col] = pd.NA
        if col not in df_reddit.columns:
            df_reddit[col] = pd.NA
            
    # Concatenate
    df_merged = pd.concat([df_slack[shared_cols], df_reddit[shared_cols]], ignore_index=True)
    
    # Sort by timestamp
    df_merged = df_merged.sort_values(by="timestamp")
    
    # Save
    df_merged.to_csv(output_csv_path, index=False)
    return df_merged

def update_csv_timestamps(csv_path):
    """
    Updates the timestamps in the CSV file by shifting old years to recent ones.
    Creates a backup before modifying.
    Updates: 2017->2025, 2018->2024, 2019->2025, 2022->2025.
    """
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    # Create backup
    backup_path = csv_path.replace(".csv", "_backup.csv")
    print(f"Creating backup at {backup_path}...")
    
    try:
        df = pd.read_csv(csv_path)
        df.to_csv(backup_path, index=False)
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return

    # Function to update year
    def update_year(timestamp_str):
        try:
            # Parse the timestamp handling potential mixed formats or already parsed objects
            dt = pd.to_datetime(timestamp_str)
            
            # Define year updates
            year_updates = {
                2017: 2025,
                2018: 2024,
                2019: 2025,
                2022: 2025
            }
            
            # Update year based on original year
            original_year = dt.year
            if original_year in year_updates:
                dt = dt.replace(year=year_updates[original_year])
            
            return str(dt)
        except:
            return timestamp_str

    print("Updating years in timestamp column...")
    if 'timestamp' in df.columns:
        df['timestamp'] = df['timestamp'].apply(update_year)
        
        # Save updated data
        print(f"Saving updated data to {csv_path}...")
        df.to_csv(csv_path, index=False)
        print("Update complete.")
    else:
        print("Column 'timestamp' not found in CSV.")

def process_stackoverflow_export(questions_path, answers_path, output_path=None):
    """
    Processes StackOverflow export files (Questions.csv, Answers.csv).
    Filters for positive scores, merges Q&A, and formats text.
    Returns the processed DataFrame. If output_path is provided, saves to CSV.
    """
    if not os.path.exists(questions_path) or not os.path.exists(answers_path):
        print("Input files not found.")
        return pd.DataFrame()

    try:
        # Load Questions
        dfQuestions = pd.read_csv(questions_path,
                                encoding="ISO-8859-1",
                                usecols=['Id','Score','Title', 'CreationDate'])
        
        # Load Answers
        dfAnswers = pd.read_csv(answers_path,
                                encoding="ISO-8859-1",
                                usecols=['ParentId','Score','Body']) # parent id links to the questions table

        # Filter
        dfQuestions = dfQuestions[dfQuestions['Score'] > 0]
        dfAnswers = dfAnswers[dfAnswers['Score'] > 0]\
            .sort_values('Score',ascending=False)\
            .drop_duplicates(subset=['ParentId'])

        # Merge
        qaDf = dfQuestions.merge(dfAnswers, left_on='Id', right_on='ParentId')\
            .rename(columns={'Title':'Question','Body':'Answer'})[['Question','Answer','Score_x', 'CreationDate']]

        # Format Text
        qaDf['text'] = 'Question:\n' + qaDf['Question'] + '\n\nAnswer:\n' + qaDf['Answer']
        
        if output_path:
            qaDf.to_csv(output_path, index=False)
            print(f"Saved {len(qaDf)} rows to {output_path}")
            
        return qaDf
    except Exception as e:
        print(f"Error processing StackOverflow data: {e}")
        return pd.DataFrame()

    return user_stats

@st.cache_data(ttl=300)
def load_users_from_db():
    try:
        engine = get_db_engine()
        query = "SELECT * FROM users"
        df = pd.read_sql(query, engine)
        if not df.empty:
            df = df.set_index('user')
            # Map columns back if needed or ensure app uses lower_snake_case?
            # App uses Title Case like 'Full Name', 'Company'.
            # DB has 'full_name', 'company'.
            # We need to rename.
            rename_map = {
                'full_name': 'Full Name',
                'first_name': 'First Name',
                'email': 'Email',
                'persona': 'Persona',
                'company': 'Company',
                'role': 'Role',
                'city': 'City',
                'is_client': 'Is_Client',
                'total_messages': 'Total_Messages',
                'last_active': 'Last_Active',
                'mood_emoji': 'Mood_Emoji',
                'mood_score': 'Mood_Score'
            }
            df = df.rename(columns=rename_map)
            return df
    except Exception as e:
        print(f"Error loading users from DB: {e}")
    return pd.DataFrame()

@st.cache_data
def enrich_user_data(messages_df, crm_df):
    """
    Consolidates user metrics. Tries DB first, then falls back to calculation.
    """
    # Try DB
    db_users = load_users_from_db()
    if not db_users.empty:
        # Check if we cover the users in messages_df? 
        # Ideally we return DB users, but maybe we want to join with current message counts if real-time is needed?
        # User asked to use the DB dataset. Let's return it.
        # But we must ensure the index matches what app expects (user name).
        return db_users

    # Fallback to original calculation
    if messages_df.empty:
        return pd.DataFrame()

    # 1. Base Aggregation (Total Messages, Last Active)
    user_stats = messages_df.groupby('user').agg(
        Total_Messages=('sentences', 'count'),
        Last_Active=('date', 'max'),
        Avg_Sentiment=('Sentiment Score', 'mean')
    )
    
    # 2. Calculate Personas (Batch)
    personas_dict = calculate_all_user_personas(messages_df)
    user_stats['Persona'] = user_stats.index.map(personas_dict).fillna('Unknown')
    
    # 3. Calculate Mood (Batch)
    def get_mood_emoji(score):
        if score > 0.2: return "🟢 Positive"
        elif score < -0.1: return "🔴 Negative"
        else: return "⚪ Neutral"
        
    user_stats['Mood_Emoji'] = user_stats['Avg_Sentiment'].apply(get_mood_emoji)
    user_stats['Mood_Score'] = user_stats['Avg_Sentiment'] # Keep raw score if needed
    
    # 4. Integrate CRM Data
    # Ensure crm_df is ready for lookup
    if not crm_df.empty:
        # Create a lookup series for each field we want
        # We need to match 'user' (Slack Name) to CRM 'First Name' or 'Full Name'
        
        # Pre-process CRM for easier lookup
        crm_lookup = crm_df.copy()
        # Create normalized columns for matching
        crm_lookup['match_full'] = crm_lookup['Full Name'].str.lower().str.strip()
        crm_lookup['match_first'] = crm_lookup['First Name'].str.lower().str.strip()
        
        # We will create dictionary lookups for performance
        # Priority: Full Name Match -> First Name Match
        
        # Dictionaries
        companies = []
        cities = []
        roles = []
        # New fields
        full_names = []
        first_names = []
        emails = []
        notes_list = []
        
        is_client_list = []
        
        # user_stats has unique users.
        users_list = user_stats.index.tolist()
        
        for u in users_list:
            u_clean = str(u).lower().strip()
            
            # Try Full Match
            match = crm_lookup[crm_lookup['match_full'] == u_clean]
            
            # Try First Name Match (if u is single word or we just match first part)
            if match.empty:
                u_first = u_clean.split()[0]
                match = crm_lookup[crm_lookup['match_first'] == u_first]
            
            if not match.empty:
                # Take first match
                r = match.iloc[0]
                companies.append(r.get('Company', 'Unknown'))
                
                # City logic
                loc = []
                if pd.notna(r.get('City')): loc.append(r['City'])
                if pd.notna(r.get('State')): loc.append(r['State'])
                cities.append(", ".join(loc) if loc else "Unknown")
                
                roles.append(r.get('Role', 'Unknown'))
                
                # New Fields
                full_names.append(r.get('Full Name', 'Unknown'))
                first_names.append(r.get('First Name', 'Unknown'))
                emails.append(r.get('Email', 'Unknown'))
                notes_list.append(r.get('notes', ''))
                
                # Is Client Logic
                status_val = str(r.get('Status', '')).lower()
                is_client = 'customer' in status_val or 'client' in status_val
                is_client_list.append(is_client)
                
            else:
                companies.append("Unknown")
                cities.append("Unknown")
                roles.append("Unknown")
                # New Fields
                full_names.append("Unknown")
                first_names.append("Unknown")
                emails.append("Unknown")
                notes_list.append("")
                
                is_client_list.append(False)
        
        user_stats['Company'] = companies
        user_stats['City'] = cities
        user_stats['Role'] = roles
        user_stats['Full Name'] = full_names
        user_stats['First Name'] = first_names
        user_stats['Email'] = emails
        user_stats['notes'] = notes_list
        user_stats['Is_Client'] = is_client_list
        
    else:
        user_stats['Company'] = "Unknown"
        user_stats['City'] = "Unknown"
        user_stats['Role'] = "Unknown"
        user_stats['Full Name'] = "Unknown"
        user_stats['First Name'] = "Unknown"
        user_stats['Email'] = "Unknown"
        user_stats['notes'] = ""
        user_stats['Is_Client'] = False
        
    return user_stats
