import streamlit as st
import pandas as pd
import plotly.express as px
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
from data_utils import load_data, get_user_persona, calculate_all_user_personas
from trello_utils import add_trello_task
from slack_utils import send_private_reply, send_channel_reply

# --- Configuration & Setup ---
st.set_page_config(page_title="Slack Engagement Dashboard", layout="wide")
DATA_PATH = os.path.join("channel extraction", "merged_data.csv")

# --- Main App ---
def main():
    
    # Navigation Callback
    def go_to_user(user_name):
        st.session_state['selected_dashboard'] = "User Analysis"
        st.session_state['selected_user_analysis'] = user_name

    st.title("Slack Engagement Analysis")
    
    # Initialize Session State
    if 'selected_user_analysis' not in st.session_state:
        st.session_state['selected_user_analysis'] = None
    if 'selected_dashboard' not in st.session_state:
        st.session_state['selected_dashboard'] = "Overall Summary"
    if 'resolved_tasks' not in st.session_state:
        st.session_state['resolved_tasks'] = set()

    with st.spinner("Loading and processing data..."):
        df = load_data(DATA_PATH)
    
    if df.empty:
        st.warning("No data loaded.")
        return

    # Sidebar Navigation
    st.sidebar.title("Navigation")
    dashboard_mode = st.sidebar.radio(
        "Select Dashboard", 
        ["Overall Summary", "User Analysis", "Tasks", "Bulk Messaging"],
        key="selected_dashboard"
    )

    st.sidebar.divider()
    st.sidebar.subheader("Global Filters")
    
    # Workspace Filter
    all_workspaces = sorted(df['workspace'].unique())
    selected_workspaces = st.sidebar.multiselect(
        "Slack Workspaces or Reddit", 
        all_workspaces, 
        default=all_workspaces
    )

    if not selected_workspaces:
        st.warning("Please select at least one workspace.")
        return

    # Filter DF by selected workspaces for all subsequent logic
    df_ws = df[df['workspace'].isin(selected_workspaces)]

    # --- Dashboard 1: Overall Summary ---
    if dashboard_mode == "Overall Summary":
        st.header("Overall Channel Activity")
        
        all_channels = sorted(df_ws['channel'].unique())
        selected_channels = st.sidebar.multiselect("Filter by Channel", all_channels, default=all_channels)
        
        # Date Filter
        min_date = df_ws['date'].min()
        max_date = df_ws['date'].max()
        
        # Default to last 30 days, constrained by data range
        default_end = max_date
        default_start = max(min_date, max_date - timedelta(days=30))
        
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=max_date
        )
        
        if not selected_channels:
            st.warning("Please select at least one channel.")
            return

        # Validate date range selection
        if len(date_range) != 2:
            st.warning("Please select a start and end date.")
            return
            
        start_date, end_date = date_range

        filtered_df = df_ws[
            (df_ws['channel'].isin(selected_channels)) & 
            (df_ws['date'] >= start_date) & 
            (df_ws['date'] <= end_date)
        ]
        
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

        st.subheader("Top 10 Slack Contributors (pythondev)")
        
        if not filtered_df.empty:
            # Filter specifically for pythondev to show Slack contributors
            slack_only_df = filtered_df[filtered_df['workspace'] == 'pythondev']
            
            # 1. Identify Top 10 Users by Message Count
            top_users = slack_only_df['user'].value_counts().head(10).index.tolist()
            
            if not top_users:
                st.info("No Slack contributors found in this date range. Try expanding the Date Range in the sidebar to include 2017.")
            
            table_data = []
            emojis = {1: "😠", 2: "🙁", 3: "😐", 4: "🙂", 5: "😃"}

            # 2. Iterate and Calculate Stats
            
            # Header Row
            h1, h2, h3, h4, h5, h6 = st.columns([2, 1, 2, 1, 2, 1.5])
            h1.markdown("**User**")
            h2.markdown("**Msgs**")
            h3.markdown("**Top Channels**")
            h4.markdown("**Mood**")
            h5.markdown("**Persona**")
            h6.markdown("**Action**")
            st.divider()

            for user in top_users:
                user_data = filtered_df[filtered_df['user'] == user]
                
                # Top Channels
                top_channels = user_data['channel'].value_counts().head(3).index.tolist()
                channels_str = ", ".join(top_channels)
                
                # Sentiment
                avg_sentiment = user_data['Sentiment Score'].mean()
                sentiment_level = int(round(avg_sentiment))
                sentiment_emoji = emojis.get(sentiment_level, "😐")
                
                # Persona
                persona, _, _ = get_user_persona(user_data, user_data['sentences'])
                
                # Render Row
                c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 2, 1, 2, 1.5])
                
                c1.write(user)  
                c2.write(f"{len(user_data)}")
                c3.caption(channels_str)
                c4.write(sentiment_emoji)
                c5.caption(persona)
                
                # Button for Details
                c6.button("More Details", key=f"btn_{user}", on_click=go_to_user, args=(user,))
            
        else:
            st.info("No data available for the selected range.")

    # --- Dashboard 2: User Analysis ---
    elif dashboard_mode == "User Analysis":
        st.header("Individual User Analysis")
        
        all_users = sorted(df['user'].unique())
        
        # Determine index for selectbox
        try:
            default_ix = all_users.index(st.session_state.get('selected_user_analysis')) if st.session_state.get('selected_user_analysis') in all_users else 0
        except:
            default_ix = 0
            
        selected_user = st.sidebar.selectbox("Select User", all_users, index=default_ix, key="user_selector")
        
        # Sync selection back to state if changed manually
        if selected_user != st.session_state.get('selected_user_analysis'):
             st.session_state['selected_user_analysis'] = selected_user
        
        user_channels = df_ws[df_ws['user'] == selected_user]['channel'].unique()
        selected_channels_user = st.sidebar.multiselect("Filter by Channel", user_channels, default=user_channels)
        
        if not selected_channels_user:
             st.warning("Please select at least one channel.")
             return

        user_df = df_ws[(df_ws['user'] == selected_user) & (df_ws['channel'].isin(selected_channels_user))]
        
        col1, col2 = st.columns(2)
        col1.metric("Total Messages", len(user_df))
        most_active_channel = user_df['channel'].mode()[0] if not user_df.empty else "N/A"
        col2.metric("Most Active Channel", most_active_channel)
        
        st.subheader("User Persona & Sentiment")
        
        if not user_df.empty:
            # 1. Sentiment Analysis
            avg_sentiment = user_df['Sentiment Score'].mean()
            sentiment_level = int(round(avg_sentiment))
            emojis = {1: "😠", 2: "🙁", 3: "😐", 4: "🙂", 5: "😃"}
            
            # 2. Persona Classification Logic
            persona, confidence, description = get_user_persona(user_df, user_df['sentences'])

            # Display Sentiment and Persona side-by-side
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.markdown("**Avg Sentiment**")
                st.markdown(f"**{avg_sentiment:.2f}** / 5.0")
                emoji_html = f"<span style='font-size: 40px;'>{emojis[sentiment_level]}</span>"
                st.markdown(emoji_html, unsafe_allow_html=True)
            
            with c2:
                st.markdown("**Behavioral Persona**")
                st.info(f"**{persona}**\n\nConfidence: **{confidence:.0%}**\n\n*{description}*")

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
        all_channels = sorted(df_ws['channel'].unique())
        selected_channels_tasks = st.sidebar.multiselect("Filter by Channel", all_channels, default=all_channels)
        
        if not selected_channels_tasks:
            st.warning("Please select at least one channel.")
            return
            
        filtered_tasks = df_ws[
            (df_ws['channel'].isin(selected_channels_tasks)) & 
            (df_ws['is_unanswered'])
        ]
        
        st.metric("Total Unanswered Questions", len(filtered_tasks))
        
        if not filtered_tasks.empty:
            # Sort by time
            filtered_tasks = filtered_tasks.sort_values('ts', ascending=False)
            
            # Filter out resolved tasks (using original index)
            visible_tasks = [i for i in filtered_tasks.index if i not in st.session_state['resolved_tasks']]
            
            if not visible_tasks:
                 st.success("No unanswered questions found in selected channels! (All resolved)")
            else:
                # Limit to 50 recent tasks for performance
                for index in visible_tasks[:50]:
                    row = df.loc[index] # Access by label (original index)
                    user_msg = row['sentences']
                    ts = row['ts']
                    user = row['user']
                    
                    # Truncate for title
                    preview = (user_msg[:75] + '..') if len(user_msg) > 75 else user_msg
                    
                    with st.expander(f"**{user}** in **#{row['channel']}**: {preview}"):
                        st.write(f"**Full Question** (asked at {ts}):")
                        st.info(user_msg)
                        
                        # Work Area
                        respond_text = st.text_area("Draft Response / Notes:", key=f"resp_{index}")
                        
                        # Action Buttons
                        col_a, col_b, col_c, col_d, col_e = st.columns(5)
                        
                        if col_a.button("✉️ Private Reply", key=f"priv_{index}"):
                            with st.spinner("Sending private message..."):
                                success, msg = send_private_reply("rano", user, respond_text)
                                if success:
                                    st.toast(msg, icon="✅")
                                else:
                                    st.error(msg)
                            
                        if col_b.button("📢 Channel Reply", key=f"chan_{index}"):
                            with st.spinner("Posting to #test..."):
                                success, msg = send_channel_reply("#test", respond_text)
                                if success:
                                    st.toast(msg, icon="✅")
                                else:
                                    st.error(msg)
                            
                        if col_c.button("📋 Trello Task", key=f"trello_{index}"):
                            with st.spinner("Creating Trello card..."):
                                success, msg = add_trello_task(user, user_msg, respond_text)
                                if success:
                                    st.toast(msg, icon="✅")
                                else:
                                    st.error(msg)
                            
                        if col_d.button("☁️ Salesforce Log", key=f"sf_{index}"):
                             st.toast("Feature Coming Soon!", icon="🚧")
    
                        
                        if col_e.button("✅ Resolve", key=f"res_{index}"):
                             st.session_state['resolved_tasks'].add(index)
                             st.toast("Task marked as resolved!", icon="🎉")
                             st.rerun()
                
                if len(visible_tasks) > 50:
                    st.warning(f"Showing top 50 of {len(visible_tasks)} tasks. Resolve tasks to see more.")
                        
        else:
            st.success("No unanswered questions found in selected channels!")

    # --- Dashboard 4: Bulk Messaging ---
    elif dashboard_mode == "Bulk Messaging":
        st.header("Bulk Messaging by Persona")
        
        # 1. Persona Descriptions
        st.subheader("Target Audience Definitions")
        
        persona_data = {
            "Persona": ["Expert Contributor", "Active Learner", "Passive Reader/Lurker", "Feature Advocate", "Social Connector"],
            "Description": [
                "Initiates complex, technical discussions; provides detailed solutions; rarely asks questions.",
                "Asks frequent, specific technical questions; high engagement in core concepts.",
                "Extremely low message count; views many channels but rarely participates.",
                "Primarily discusses roadmap, suggests features, critical/praising of updates.",
                "Focuses on non-technical channels; uses emojis heavily; welcomes new members."
            ]
        }
        st.table(pd.DataFrame(persona_data))
        
        st.markdown("---")
        st.subheader("Compose Message")
        
        # 2. Message Composition
        message_text = st.text_area("Enter your message content here:", height=150)
        
        # 3. Target Selection
        # Calculate personas for all users to populate counts (optional but nice)
        with st.spinner("Analyzing user base (filtered by workspace)..."):
            all_user_personas = calculate_all_user_personas(df_ws)
            
        # Create a DF for easy filtering
        persona_df = pd.DataFrame(list(all_user_personas.items()), columns=['User', 'Persona'])
        persona_counts = persona_df['Persona'].value_counts()
        
        # Append counts to labels for the multiselect
        persona_options = sorted(persona_df['Persona'].unique())
        persona_options_with_counts = [f"{p} ({persona_counts.get(p, 0)} users)" for p in persona_options]
        
        # Mapping back to raw persona name for logic
        option_map = {f"{p} ({persona_counts.get(p, 0)} users)": p for p in persona_options}
        
        selected_options = st.multiselect("Select Target Personas:", persona_options_with_counts)
        
        # 4. Impact Preview
        if selected_options:
            selected_personas = [option_map[opt] for opt in selected_options]
            target_users = persona_df[persona_df['Persona'].isin(selected_personas)]['User'].tolist()
            user_count = len(target_users)
            
            st.info(f"Targeting **{user_count}** users across {len(selected_personas)} persona groups.")
            with st.expander("View Target User List"):
                st.write(", ".join(target_users))
        else:
            st.warning("Select at least one persona group to see the target audience.")

        # 5. Actions
        col_btn1, col_btn2 = st.columns([1, 4])
        
        with col_btn1:
            if st.button("Send Message", type="primary"):
                if not message_text:
                    st.error("Please enter a message first.")
                elif not selected_options:
                    st.error("Please select a target audience.")
                else:
                    st.success(f"Message sent to {user_count} users! (Simulation)")
        
        with col_btn2:
            st.button("Create New User Classification", help="Define a new persona rule (Coming Soon)")

if __name__ == "__main__":
    main()
