import pandas as pd
import os
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
    df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
    df['date'] = df['ts'].dt.date
    df['sentences'] = df['sentences'].astype(str)

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
