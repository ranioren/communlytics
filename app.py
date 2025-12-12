import streamlit as st
import pandas as pd
import plotly.express as px
import os
from textblob import TextBlob
from datetime import timedelta

# --- Configuration & Setup ---
st.set_page_config(page_title="Slack Engagement Dashboard", layout="wide")
DATA_PATH = os.path.join("channel extraction", "slack_spencer_hf.csv")

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
    # 1. Identify Questions
    # We treat "High Engagement (Question/Long)" as potential questions, 
    # but let's be more specific: must have '?' for this task logic to be precise?
    # User prompt said: "if a question was asked...". Let's stick to our "High Engagement" category 
    # OR strictly contain '?' to avoid noise. Let's use '?' for stricter "Question" detection for tasks.
    df['is_question'] = df['sentences'].str.contains(r'\?', regex=True)
    
    # 2. Identify Tasks (Unanswered Questions)
    # This might be slow on large dataframes, so we'll try to be efficient.
    # We need to look ahead.
    
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
            
            # Check if any response mentions the user
            # User format in CSV seems to be 'Melvin'. 
            # Mentions in messages: "<@Ben>" or just "@Ben"? 
            # Looking at CSV sample: "<@Beula> zappa ...". So it seems to be `<@User>`.
            # But the 'user' column has "Melvin".
            # We should check for both `@Melvin` and `<@Melvin>` just to be sure, or just the name.
            user_name = question['user']
            
            # Check if any valid response contains the user name
            is_answered = valid_responses['sentences'].str.contains(user_name, case=False).any()
            
            if not is_answered:
                 df.at[idx, 'is_unanswered'] = True

    return df

# --- Main App ---
def main():
    st.title("Slack Engagement Analysis")
    
    with st.spinner("Loading and processing data..."):
        df = load_data(DATA_PATH)
    
    if df.empty:
        st.warning("No data loaded.")
        return

    # Sidebar Navigation
    dashboard_mode = st.sidebar.radio("Select Dashboard", ["Overall Summary", "User Analysis", "Tasks"])

    # --- Dashboard 1: Overall Summary ---
    if dashboard_mode == "Overall Summary":
        st.header("Overall Channel Activity")
        
        all_channels = sorted(df['channel'].unique())
        selected_channels = st.sidebar.multiselect("Filter by Channel", all_channels, default=all_channels)
        
        if not selected_channels:
            st.warning("Please select at least one channel.")
            return

        filtered_df = df[df['channel'].isin(selected_channels)]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Messages", len(filtered_df))
        col2.metric("Active Users", filtered_df['user'].nunique())
        col3.metric("Date Range", f"{filtered_df['date'].min()} to {filtered_df['date'].max()}")

        st.subheader("Engagement Distribution")
        type_counts = filtered_df['Message Type'].value_counts().reset_index()
        type_counts.columns = ['Message Type', 'Count']
        fig_bar = px.bar(type_counts, x='Message Type', y='Count', color='Message Type', title="Total Messages by Type")
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.subheader("Daily Activity Trend")
        daily_activity = filtered_df.groupby(['date', 'Message Type']).size().reset_index(name='Count')
        fig_line = px.area(daily_activity, x='date', y='Count', color='Message Type', title="Daily Message Volume by Type")
        st.plotly_chart(fig_line, use_container_width=True)

    # --- Dashboard 2: User Analysis ---
    elif dashboard_mode == "User Analysis":
        st.header("Individual User Analysis")
        
        all_users = sorted(df['user'].unique())
        selected_user = st.sidebar.selectbox("Select User", all_users)
        
        user_channels = df[df['user'] == selected_user]['channel'].unique()
        selected_channels_user = st.sidebar.multiselect("Filter by Channel", user_channels, default=user_channels)
        
        if not selected_channels_user:
             st.warning("Please select at least one channel.")
             return

        user_df = df[(df['user'] == selected_user) & (df['channel'].isin(selected_channels_user))]
        
        col1, col2 = st.columns(2)
        col1.metric("Total Messages", len(user_df))
        most_active_channel = user_df['channel'].mode()[0] if not user_df.empty else "N/A"
        col2.metric("Most Active Channel", most_active_channel)
        
        st.subheader("User Sentiment")
        if not user_df.empty:
            avg_sentiment = user_df['Sentiment Score'].mean()
            sentiment_level = int(round(avg_sentiment))
            emojis = {1: "😠", 2: "🙁", 3: "😐", 4: "🙂", 5: "😃"}
            st.write(f"Average Sentiment Score: **{avg_sentiment:.2f}** / 5.0")
            cols = st.columns(5)
            for i in range(1, 6):
                with cols[i-1]:
                    if i == sentiment_level:
                         st.markdown(f"<h1 style='text-align: center;'>{emojis[i]}</h1>", unsafe_allow_html=True)
                         st.markdown(f"<p style='text-align: center; font-weight: bold;'>Level {i}</p>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<h3 style='text-align: center; opacity: 0.3;'>{emojis[i]}</h3>", unsafe_allow_html=True)

        st.subheader(f"Engagement Breakdown: {selected_user}")
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            type_counts_user = user_df['Message Type'].value_counts().reset_index()
            type_counts_user.columns = ['Message Type', 'Count']
            fig_pie = px.pie(type_counts_user, names='Message Type', values='Count', title="Message Type Distribution")
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_chart2:
            daily_activity_user = user_df.groupby(['date', 'Message Type']).size().reset_index(name='Count')
            if not daily_activity_user.empty:
                fig_line_user = px.bar(daily_activity_user, x='date', y='Count', color='Message Type', title="Daily Activity")
                st.plotly_chart(fig_line_user, use_container_width=True)
            else:
                st.info("No data available for timeline.")

        # Unanswered Questions List for User
        st.subheader("Unanswered Questions (Tasks)")
        st.markdown(f"List of questions asked by **{selected_user}** that did not receive a mention-response within 24 hours.")
        
        unanswered_user = user_df[user_df['is_unanswered']]
        
        if not unanswered_user.empty:
             # Display readable table
             display_cols = ['ts', 'channel', 'sentences']
             st.dataframe(unanswered_user[display_cols].sort_values('ts', ascending=False), use_container_width=True)
        else:
            st.success("Great! No unanswered questions found for this user.")

    # --- Dashboard 3: Tasks ---
    elif dashboard_mode == "Tasks":
        st.header("Unanswered Questions (Tasks Management)")
        st.info("This dashboard lists all questions that have not received a direct response (mentioning the asker) within 24 hours.")
        
        # Filter: Channel
        all_channels = sorted(df['channel'].unique())
        selected_channels_tasks = st.sidebar.multiselect("Filter by Channel", all_channels, default=all_channels)
        
        if not selected_channels_tasks:
            st.warning("Please select at least one channel.")
            return
            
        filtered_tasks = df[
            (df['channel'].isin(selected_channels_tasks)) & 
            (df['is_unanswered'])
        ]
        
        st.metric("Total Unanswered Questions", len(filtered_tasks))
        
        if not filtered_tasks.empty:
            # Display readable table
            display_cols = ['ts', 'channel', 'user', 'sentences']
            st.dataframe(filtered_tasks[display_cols].sort_values('ts', ascending=False), use_container_width=True)
        else:
            st.success("No unanswered questions found in selected channels!")

if __name__ == "__main__":
    main()
