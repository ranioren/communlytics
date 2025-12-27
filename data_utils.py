import pandas as pd
import os
import json
from textblob import TextBlob
from datetime import timedelta
import streamlit as st

# --- Helper Functions ---
@st.cache_data
def load_data(path):
    if not os.path.exists(path):
        st.error(f"Data file not found at: {path}")
        return pd.DataFrame()
    
    # Load data
    df = pd.read_csv(path)
    
    # Preprocessing
    if 'timestamp' in df.columns:
        df['ts'] = pd.to_datetime(df['timestamp'], errors='coerce')
    else:
        df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
        
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
    df['is_question'] = df['sentences'].str.contains(r'\?', regex=True)
    df['is_unanswered'] = False
    
    # Sort by time to ensure order
    df = df.sort_values(by=['channel', 'ts'])
    
    # We will iterate channel by channel
    for channel_name, channel_data in df.groupby('channel'):
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
            
            # Check if any valid response contains the user name
            is_answered = valid_responses['sentences'].str.contains(user_name, case=False).any()
            
            if not is_answered:
                 df.at[idx, 'is_unanswered'] = True

    return df

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
