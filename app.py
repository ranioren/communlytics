import streamlit as st
import pandas as pd
import plotly.express as px
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
from data_utils import load_data, get_user_persona, calculate_all_user_personas, generate_wordcloud, load_crm_data, check_is_client, enrich_user_data, get_cached_wordcloud_from_db, load_users_from_db

def get_enriched_data_safe(df):
    """
    Attempts to load enriched user data from DB first (Fast).
    Falls back to fetching CRM and calculating if DB is empty (Slow).
    """
    # 1. Try DB
    db_users = load_users_from_db()
    if not db_users.empty:
        return db_users
        
    # 2. Fallback
    sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiHHBbo2j1VVn06Xub2FqBdGqiVEzmNzOcaQcGu10W53Ai93HIYyr3UHb4RKKQpqrF3Iso6z5HhfiI/pub?output=csv"
    crm_df = load_crm_data(sheet_url)
    return enrich_user_data(df, crm_df)

from ai_utils import get_top_suggestions, generate_ai_response, generate_crm_response
from trello_utils import add_trello_task
from slack_utils import send_private_reply, send_channel_reply
from streamlit_option_menu import option_menu
# import hubspot_utils (Removed)
from data_utils import load_crm_data

# --- Configuration & Setup ---
st.set_page_config(page_title="Slack Engagement Dashboard", layout="wide")
DATA_PATH = os.path.join("channel extraction", "merged_data.csv")

# --- Main App ---
def main():
    # Fix for Bug: "st.session_state.selected_dashboard cannot be modified after widget is instantiated"
    # We handle programmatic navigation by setting a pending flag, then applying it at the start of the NEXT run.
    if 'pending_nav' in st.session_state and st.session_state['pending_nav']:
        target_nav = st.session_state.pop('pending_nav')
        print(f"DEBUG: Applying pending nav: {target_nav}")
        st.session_state['selected_dashboard'] = target_nav
    
    print(f"DEBUG: Start of Main. selected_dashboard={st.session_state.get('selected_dashboard')}")

    # Profiling Hook
    if "profile" in st.query_params and st.query_params["profile"] == "true":
         try:
             from pyinstrument import Profiler
             profiler = Profiler()
             profiler.start()
         except ImportError:
             profiler = None
    else:
         profiler = None

    
    # Navigation Callback
    def go_to_user(user_name):
        st.session_state['selected_dashboard'] = "User Analysis"
        st.session_state['selected_user_analysis'] = user_name

    # --- reusable component ---
    def render_task_card(index, row):
        """
        Renders a single task card with AI, Trello, and CRM integration.
        """
        user_msg = row['sentences']
        ts = row['ts']
        user = row['user']
        channel = row['channel']
        
        # Truncate for title
        preview = (user_msg[:75] + '..') if len(user_msg) > 75 else user_msg
        
        # Lazy load key
        kb_lookup_key = f"kb_lookup_{index}"
        if kb_lookup_key not in st.session_state:
            st.session_state[kb_lookup_key] = False

        # Keep expanded if we are interacting with it (KB lookup active)
        is_expanded = st.session_state[kb_lookup_key]

        with st.expander(f"**{user}** in **#{channel}**: {preview}", expanded=is_expanded):
            st.write(f"**Full Question** (asked at {ts}):")
            st.info(user_msg)
            
            if not st.session_state[kb_lookup_key]:
                    if st.button("🔍 Find Similar Questions", key=f"btn_kb_{index}"):
                        st.session_state[kb_lookup_key] = True
                        st.rerun()
            
            if st.session_state[kb_lookup_key]:
                st.markdown("##### 📚 Knowledgebase Suggestions")
                with st.spinner("Finding similar questions..."):
                    suggestions = get_top_suggestions(user_msg)
                
                if not suggestions:
                    st.write("No similar questions found in knowledge base.")
                else:
                    st.write("Select relevant suggestions to include in AI drafting:")
                    selected_indices = []
                    for i, s in enumerate(suggestions):
                        if st.checkbox(f"**{s['similarity']:.1%} Match**: {s['question'][:100]}...", key=f"kb_{index}_{i}"):
                            selected_indices.append(i)
                        with st.container():
                            st.caption(f"**Answer**: {s['answer'][:200]}...")
                    
                    if st.button("✨ Generate Draft with Gemini", key=f"gen_{index}"):
                        if not selected_indices:
                            st.warning("Please select at least one suggestion.")
                        else:
                            chosen = [suggestions[i] for i in selected_indices]
                            # Get current draft if user already typed something
                            current_draft_content = st.session_state.get(f"resp_{index}", "")
                            with st.spinner("Gemini is drafting a response..."):
                                draft = generate_ai_response(user_msg, chosen, existing_draft=current_draft_content)
                                st.session_state['ai_drafts'][index] = draft
                                # Directly update the text area's session state key
                                st.session_state[f"resp_{index}"] = draft
                                st.rerun()

            # Work Area
            # Use session state to handle the text area value
            if f"resp_{index}" not in st.session_state:
                 st.session_state[f"resp_{index}"] = st.session_state['ai_drafts'].get(index, "")
            
            respond_text = st.text_area("Draft Response / Notes:", key=f"resp_{index}")
            
            # Sync back to our persistent draft storage
            st.session_state['ai_drafts'][index] = respond_text
            
            # Action Buttons
            col_a, col_b, col_c, col_d, col_e = st.columns(5)
            
            if col_a.button("✉️ Private Reply", key=f"priv_{index}"):
                with st.spinner("Sending private message..."):
                    success, msg = send_private_reply("rano", user, respond_text, simulate_typing=True)
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
                
            if col_d.button("💬 Interact with CRM", key=f"sf_{index}"):
                 if f"show_crm_{index}" not in st.session_state:
                     st.session_state[f"show_crm_{index}"] = True
                 else:
                     st.session_state[f"show_crm_{index}"] = not st.session_state[f"show_crm_{index}"]
            
            # CRM Lookup Area
            if st.session_state.get(f"show_crm_{index}", False):
                 st.markdown("---")
                 
                 with st.spinner("Fetching CRM data..."):
                      # Load Data
                      sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiHHBbo2j1VVn06Xub2FqBdGqiVEzmNzOcaQcGu10W53Ai93HIYyr3UHb4RKKQpqrF3Iso6z5HhfiI/pub?output=csv"
                      crm_df = load_crm_data(sheet_url)
                      
                      if crm_df.empty:
                          st.error("Could not load CRM data.")
                      else:
                          # Simple filter: Check if any part of the name matches
                          match = None
                          
                          # 1. Try exact Full Name match
                          exact_matches = crm_df[crm_df['Full Name'].str.lower() == user.lower()]
                          if not exact_matches.empty:
                              match = exact_matches.iloc[0]
                          
                          # 2. Try First Name match if no exact match
                          if match is None:
                              # Split slack user by space
                              first_name_guess = user.split()[0]
                              partial_matches = crm_df[crm_df['First Name'].str.lower() == first_name_guess.lower()]
                              if not partial_matches.empty:
                                  match = partial_matches.iloc[0]
                          
                          if match is not None:
                              c1, c2 = st.columns(2)
                              
                              # Left Column: Details
                              with c1:
                                  st.caption("🔎 **Mock CRM Data**")
                                  st.success(f"**Found: {match['Full Name']}**")
                                  
                                  # Where is he from
                                  loc_str = "Unknown"
                                  if 'City' in match and pd.notna(match['City']):
                                       loc_str = match['City']
                                  if 'State' in match and pd.notna(match['State']):
                                       loc_str += f", {match['State']}"
                                  st.markdown(f"🌍 **From:** {loc_str}")
                                  
                                  # Where does he work
                                  company = match['Company'] if 'Company' in match and pd.notna(match['Company']) else "Unknown"
                                  st.markdown(f"🏢 **Work:** {company}")
                                  
                                  # Other details
                                  if 'Role' in match and pd.notna(match['Role']): 
                                      st.markdown(f"💼 **Role:** {match['Role']}")
                                  if 'Email' in match and pd.notna(match['Email']): 
                                      st.markdown(f"📧 **Email:** {match['Email']}")
                                  if 'notes' in match and pd.notna(match['notes']): 
                                      st.info(f"📝 **Notes:** {match['notes']}")
                                  
                              # Right Column: Chat
                              with c2:
                                  st.caption("Chat with Account manager - via CRM")
                                  
                                  # Chat History Key
                                  crm_chat_key = f"crm_chat_{index}_{match['First Name']}"
                                  if crm_chat_key not in st.session_state:
                                      st.session_state[crm_chat_key] = []
                                      
                                  # Display History
                                  chat_container = st.container(height=200)
                                   
                                  # Dark Green Robot Icon
                                  GREEN_BOT_ICON = "https://img.icons8.com/ios-filled/50/006400/bot.png"
                                   
                                  with chat_container:
                                      for msg in st.session_state[crm_chat_key]:
                                          avatar = GREEN_BOT_ICON if msg["role"] == "assistant" else None
                                          with st.chat_message(msg["role"], avatar=avatar):
                                              st.write(msg["content"])
                                               
                                  # Input
                                  if users_query := st.chat_input(f"Ask about {match['First Name']}...", key=f"crm_in_{index}"):
                                       # Add user message
                                       st.session_state[crm_chat_key].append({"role": "user", "content": users_query})
                                       with chat_container:
                                           with st.chat_message("user"):
                                               st.write(users_query)
                                               
                                           with st.chat_message("assistant", avatar=GREEN_BOT_ICON):
                                               with st.spinner("Analyzing CRM data..."):
                                                   # Prepare context
                                                   context_str = str(match.to_dict())
                                                   ans = generate_crm_response(users_query, context_str)
                                                   st.write(ans)
                                                   st.session_state[crm_chat_key].append({"role": "assistant", "content": ans})
                                                   
                          else:
                              st.caption("🔎 **Mock CRM Data**")
                              st.warning(f"User '{user}' not found in CRM Sheet.")
                              st.caption(f"Checked against {len(crm_df)} records.")
            
            if col_e.button("✅ Resolve", key=f"res_{index}"):
                 st.session_state['resolved_tasks'].add(index)
                 st.toast("Task marked as resolved!", icon="🎉")
                 st.rerun()


    st.title("Community Engagement Analysis")
    
    # Initialize Session State
    if 'selected_user_analysis' not in st.session_state:
        st.session_state['selected_user_analysis'] = None
    if 'selected_dashboard' not in st.session_state:
        # Check query params for deep linking
        qp = st.query_params
        if "dashboard" in qp:
            target = qp["dashboard"]
            # Validate target is a valid option
            if target in ["Community Health", "User Analysis", "Tasks", "Bulk Messaging"]:
                 st.session_state['selected_dashboard'] = target
            else:
                 st.session_state['selected_dashboard'] = "Community Health"
        else:
            st.session_state['selected_dashboard'] = "Community Health"
    if 'resolved_tasks' not in st.session_state:
        st.session_state['resolved_tasks'] = set()
    if 'ai_drafts' not in st.session_state:
        st.session_state['ai_drafts'] = {}

    with st.spinner("Loading and processing data..."):
        try:
             # Pass mtime to force cache invalidation when file changes
             mtime = os.path.getmtime(DATA_PATH)
             df = load_data(DATA_PATH, last_modified=mtime)
        except OSError:
             # Fallback if file not found (though check is inside load_data too)
             df = load_data(DATA_PATH)
    
    if df.empty:
        st.warning("No data loaded.")
        return



    # Sidebar Navigation
    st.sidebar.image(os.path.join("homepage_images", "logo2.png"), use_container_width=True)
    # Define menu options
    menu_options = ["Community Health", "User Analysis", "Tasks", "Bulk Messaging", "My TO-DO List"]
    menu_icons = ["activity", "person-lines-fill", "list-task", "envelope", "check2-square"]
    
    # Determine default index based on session state
    try:
        current_selection = st.session_state.get('selected_dashboard', "Community Health")
        default_ix = menu_options.index(current_selection)
    except ValueError:
        default_ix = 0

    with st.sidebar:
        selected = option_menu(
            "Main Menu",
            menu_options,
            icons=menu_icons,
            menu_icon="cast",
            default_index=default_ix,
            key='selected_dashboard'
        )
    
    # Update local variable for consistency (though it's in state now)
    dashboard_mode = st.session_state['selected_dashboard']

    # --- Settings Removed (HubSpot Auth) ---



    st.sidebar.divider()
    
    # Profiler Output
    if profiler is not None:
         profiler.stop()
         st.sidebar.success("Profiling Complete")
         if st.sidebar.button("See Profile"):
             st.components.v1.html(profiler.output_html(), height=800, scrolling=True)
    
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
    
    # Global Date Filter
    min_date = df_ws['date'].min()
    max_date = df_ws['date'].max()
    
    # Default to last 180 days to ensure we catch Reddit data (which might be older than Slack updates)
    default_end = max_date
    default_start = max(min_date, max_date - timedelta(days=180))
    
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(default_start, default_end),
        min_value=min_date,
        max_value=max_date
    )

    # Validate date range selection
    if len(date_range) != 2:
        st.warning("Please select a start and end date.")
        return
        
    start_date, end_date = date_range

    # --- Dashboard 1: Community Health ---
    if dashboard_mode == "Community Health":
        st.header("Overall Community Activity")
        
        all_channels = sorted(df_ws['channel'].unique())
        selected_channels = st.sidebar.multiselect("Filter by Channel", all_channels, default=all_channels)
        
        if not selected_channels:
            st.warning("Please select at least one channel.")
            return

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
        
        col_dist1, col_dist2 = st.columns(2)
        
        with col_dist1:
            type_counts = filtered_df['Message Type'].value_counts().reset_index()
            type_counts.columns = ['Message Type', 'Count']
            fig_bar = px.bar(type_counts, x='Message Type', y='Count', color='Message Type', title="Total Messages by Type")
            st.plotly_chart(fig_bar, use_container_width=True)
            
             
        with col_dist2:
            # Calculate Monthly Unique Members
            # Ensure date is in datetime format for manipulation, though it might be date object
            # efficient way to extract month-year from date object
            if not filtered_df.empty:
                # Create a copy to avoid SettingWithCopyWarning on the original filtered_df view
                df_monthly = filtered_df.copy()
                # Convert to string YYYY-MM for robust grouping
                df_monthly['month_year'] = pd.to_datetime(df_monthly['date']).dt.to_period('M').astype(str)
                
                monthly_unique = df_monthly.groupby('month_year')['user'].nunique().reset_index()
                monthly_unique.columns = ['Month', 'Unique Members']
                
                fig_monthly = px.line(
                    monthly_unique, 
                    x='Month', 
                    y='Unique Members', 
                    title="Monthly Unique Members Writing a Message",
                    color_discrete_sequence=['#00008B'], # Dark Blue color
                    markers=True,
                    text='Unique Members'
                )
                fig_monthly.update_traces(textposition="top center")
                st.plotly_chart(fig_monthly, use_container_width=True)
            else:
                st.info("No data for monthly analysis")
        
        st.subheader("Activity & Trends")
        col_trend1, col_trend2 = st.columns(2)
        
        with col_trend1:
            st.markdown("#### Daily Message Volume")
            daily_activity = filtered_df.groupby(['date', 'Message Type']).size().reset_index(name='Count')
            fig_line = px.area(daily_activity, x='date', y='Count', color='Message Type', title="")
            fig_line.update_layout(legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="center",
                x=0.5
            ))
            st.plotly_chart(fig_line, use_container_width=True)
            
        with col_trend2:
             st.markdown("#### Trending Technical Words (All Time)")
             
             with st.spinner("Loading word cloud..."):
                 # Use cached version from DB
                 wc_image = get_cached_wordcloud_from_db()
            
                 if wc_image is not None:
                     st.image(wc_image, use_container_width=True)
                 else:
                     st.info("No cached word cloud found. Run 'cron_analytics.py' to generate.")


        st.subheader("Community Contributors Table")
        
        # --- Lazy Load User Data for Table ---
        # This is where we pay the cost, but only after charts are shown. (DB Optimized)
        with st.spinner("Loading contributor profiles..."):
            enriched_users_df = get_enriched_data_safe(df)
        
        if not filtered_df.empty:
            # Aggregate stats for the SELECTED PERIOD
            period_stats = filtered_df.groupby('user').agg({
                'sentences': 'count',
                'channel': lambda x: list(x.value_counts().head(2).index)
            })

            # Join with Enriched Data (Global Context)
            # We use 'inner' join to only show users active in this period, 
            # or 'left' on period_stats to match
            display_df = period_stats.join(enriched_users_df, how='left')
            display_df = display_df.reset_index()

            # Format Columns
            display_df = display_df.rename(columns={'user': 'User', 'sentences': 'Messages'})
            
            # Helper to format list
            def fmt_channels(x): 
                if isinstance(x, list): return ", ".join(x)
                return str(x)
                
            display_df['Top Channels'] = display_df['channel'].apply(fmt_channels)
            display_df['Is Client?'] = display_df['Is_Client'].apply(lambda x: "✅ Yes" if x is True else "No")
            
            # Sentiment Emoji Logic (1-5 Scale)
            sentiment_emojis = {1: "😠", 2: "🙁", 3: "😐", 4: "🙂", 5: "😃"}
            def get_sentiment_emoji(score):
                try:
                    return sentiment_emojis.get(int(round(score)), "😐")
                except:
                    return "😐"
            
            display_df['Sentiment'] = display_df['Mood_Score'].apply(get_sentiment_emoji)
            display_df['Avg Sentiment'] = display_df['Mood_Score'].round(2)

            # Select Final Columns
            cols = ["User", "Messages", "Top Channels", "Avg Sentiment", "Sentiment", "Persona", "Is Client?"]
            # Fill NaNs for safety
            display_df = display_df[cols].fillna("Unknown")
                 
            # --- Filters ---
            f1, f2 = st.columns(2)
            with f1:
                all_personas = sorted(display_df['Persona'].unique())
                sel_personas = st.multiselect("Filter by Persona", all_personas)
                
            with f2:
                all_sentiments = sorted(display_df['Sentiment'].unique())
                sel_sentiments = st.multiselect("Filter by Sentiment", all_sentiments)
                
            # Apply Filters
            if sel_personas:
                display_df = display_df[display_df['Persona'].isin(sel_personas)]
            if sel_sentiments:
                display_df = display_df[display_df['Sentiment'].isin(sel_sentiments)]
                
            st.caption(f"Showing {len(display_df)} users. Click a row to view details.")
            
            # Use on_select to capture selection
            selection = st.dataframe(
                display_df,
                column_config={
                    "Avg Sentiment": st.column_config.NumberColumn(
                        "Score",
                        help="1 (Negative) to 5 (Positive)",
                        format="%.2f"
                    ),
                    "Sentiment": st.column_config.Column(
                        "Sentiment",
                        help="Sentiment Emojis"
                    ),
                    "Is Client?": st.column_config.TextColumn(
                        "Is Client?",
                        help="Matched in CRM Sheet"
                    )
                },
                hide_index=True,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            if selection.selection.rows:
                selected_index = selection.selection.rows[0]
                clicked_user = display_df.iloc[selected_index]['User']
                
                # Logic: Redirect if this is a NEW selection or we are not already on the page
                # To prevent loop, we only redirect if the target user is different or we are not on the dashboard
                # But since we are IN 'Community Health' block (dashboard_mode == "Community Health"),
                # any request to go to "User Analysis" is valid.
                
                # Check if we should switch (to avoid infinite reruns if we were to stay on this page, 
                # but we are switching pages so it's safer).
                # We update the state and rerun.
                
                if st.session_state.get('selected_user_analysis') != clicked_user:
                    # Queue navigation for next run
                    st.session_state['pending_nav'] = "User Analysis"
                    st.session_state['selected_user_analysis'] = clicked_user
                    # Widget 'user_selector' is not rendered yet in this mode, so this is safe:
                    st.session_state['user_selector'] = clicked_user
                    st.rerun()
                elif st.session_state.get('selected_dashboard') != "User Analysis":
                    # Queue navigation
                    print(f"DEBUG: Triggering navigation to User Analysis for user: {clicked_user}")
                    st.session_state['pending_nav'] = "User Analysis"
                    st.session_state['user_selector'] = clicked_user
                    st.rerun()
            
        else:
            st.info("No data available for the selected range.")

    # --- Dashboard 2: User Analysis ---
    elif dashboard_mode == "User Analysis":
        # --- Lazy Load User Data ---
        with st.spinner("Loading user profiles..."):
             enriched_users_df = get_enriched_data_safe(df)
             
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
                fig_line_user.update_layout(legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5
                ))
                st.plotly_chart(fig_line_user, use_container_width=True)
            else:
                st.info("No data available for timeline.")

        # User Activity Timeline
        st.subheader("User Activity Timeline")
        st.markdown("Activity timeline from the beginning (all time).")
        
        if not user_df.empty:
            # Ensure sorting
            timeline_path_df = user_df.sort_values("ts")
            
            # --- Filter Timeline Events ---
            def get_timeline_category(row):
                if row['is_question']: return "Question"
                if row['Sentiment Score'] <= 2: return "Negative"
                if row['Sentiment Score'] >= 4: return "Positive"
                return "Neutral"

            # Create a temporary column for filtering (safe on copy)
            timeline_path_df = timeline_path_df.copy()
            timeline_path_df['Timeline_Category'] = timeline_path_df.apply(get_timeline_category, axis=1)

            all_cats = ["Question", "Negative", "Positive", "Neutral"]
            # Default to showing all
            selected_cats = st.multiselect("Filter Timeline Events", all_cats, default=all_cats, key="timeline_filter")
            
            # Apply Filter
            timeline_path_df = timeline_path_df[timeline_path_df['Timeline_Category'].isin(selected_cats)]

            # Prepare items for Vis.js Timeline
            # Items need: id, content, start, (end), group (optional), title (hover), className/style
            items = []
            for idx, row in timeline_path_df.iterrows():
                # Vis.js format
                # User asked for "flag" style -> 'box' often looks like a label with stem.
                
                # Logic for Color-Coded Flags
                # Yellow: Question
                # Red: Bad (Sentiment <= 2)
                # Green: Good (Sentiment >= 4) or Response (implied by @ or high score)
                # Gray: Neutral
                
                style_str = ""
                content_html = row['channel']
                
                if row['is_question']:
                    # Gold/Yellow
                    style_str = "background-color: #FFD700; color: black; border-color: #DAA520;" 
                    content_html = f"❓ {row['channel']}"
                elif row['Sentiment Score'] <= 2:
                    # Red
                    style_str = "background-color: #FF4B4B; color: white; border-color: #8B0000;"
                    content_html = f"😠 {row['channel']}"
                elif row['Sentiment Score'] >= 4:
                    # Green
                    style_str = "background-color: #28a745; color: white; border-color: #006400;"
                    content_html = f"😃 {row['channel']}"
                else:
                    # Light Gray (Neutral)
                    style_str = "background-color: #E0E0E0; color: black; border-color: #A9A9A9;"
                    content_html = f"{row['channel']}"

                items.append({
                    "id": idx,
                    "content": content_html, 
                    "start": str(row['ts']),   
                    "type": "box",             
                    "title": row['sentences'][:200],
                    "style": style_str
                })

            # Vis.js Options
            timeline_options = {
                "height": "400px",
                "showMajorLabels": True, # User requested this specifically
                "showMinorLabels": True,
                "zoomMin": 1000 * 60 * 60 * 24, # Limit zoom to 1 day
                "type": "box",
                "orientation": "top"
            }
            
            try:
                # Correct import based on debug_import.py output
                from streamlit_timeline import st_timeline
                
                # Render Timeline
                selected_item = st_timeline(items, options=timeline_options, height="400px")
                
                # Handle Selection
                # st_timeline returns the selected item (dict) or None, not just ID
                if selected_item:
                    try:
                        # Depending on version, it might return the full item dict or just ID.
                        # Usually returns the item dict if 'items' were passed.
                        # Let's assume it returns the item dict and check 'id'.
                        
                        item_id = selected_item.get('id')
                         
                        if item_id is not None:
                            selected_row = df.loc[int(item_id)]
                            
                            sel_msg = selected_row['sentences']
                            sel_ts = selected_row['ts']
                            sel_channel = selected_row['channel']
                            
                            st.info(f"**Selected Activity** ({sel_ts}):\n\n> {sel_msg}\n\n*in #{sel_channel}*")
                        
                    except Exception as e:
                        # Fallback if structure is different
                        # st.write(f"Debug Selection: {selected_item}") 
                        pass
                        
            except ImportError:
                 st.error("Please install 'streamlit-vis-timeline' (which provides streamlit_timeline) to view this chart.")
            except Exception as e:
                 st.error(f"Error loading timeline: {e}")
                
        else:
            st.info("No activity data to show.")

        # Unanswered Questions List for User
        st.subheader("Unanswered Questions (Tasks)")
        st.markdown(f"List of questions asked by **{selected_user}** that did not receive a mention-response within 24 hours.")
        
        unanswered_user = user_df[user_df['is_unanswered']]
        
        if not unanswered_user.empty:
             # Sort by timestamp
             unanswered_user = unanswered_user.sort_values('ts', ascending=False)
             
             # Filter resolved
             visible_user_tasks = [i for i in unanswered_user.index if i not in st.session_state['resolved_tasks']]
             
             if not visible_user_tasks:
                 st.success("All questions resolved for this user.")
             else:
                 # Render cards
                 for index in visible_user_tasks:
                     row = df.loc[index]
                     # Use 'ua' prefix to avoid key collisions if needed, but index is unique so it's fine.
                     # Actually index is unique across DF, so keys like f"gen_{index}" will match the Task dashboard.
                     # This means state is shared! That's actually a feature (draft in one place, see it in another).
                     render_task_card(index, row)
        else:
            st.success("Great! No unanswered questions found for this user.")

    # --- Dashboard 3: Tasks ---
    elif dashboard_mode == "Tasks":
        st.header("Actionable Tasks (Unanswered Questions)")
        
        # --- Lazy Load User Data ---
        # Need CRM data for task card interactions (though arguably could be even lazier inside card)
        with st.spinner("Loading user profiles..."):
            enriched_users_df = get_enriched_data_safe(df)
       
        st.header("Unanswered Questions (Tasks Management)")
        st.info("This dashboard lists all questions that have not received a direct response (mentioning the asker) within 48 hours.")
       
        # Filter: Channel
        all_channels = sorted(df_ws['channel'].unique())
        selected_channels_tasks = st.sidebar.multiselect("Filter by Channel", all_channels, default=all_channels)
       
        if not selected_channels_tasks:
            st.warning("Please select at least one channel.")
            return
           
        filtered_tasks = df_ws[
            (df_ws['channel'].isin(selected_channels_tasks)) & 
            (df_ws['is_unanswered']) &
            (df_ws['date'] >= start_date) & 
            (df_ws['date'] <= end_date)
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
                # --- Pagination Logic ---
                items_per_page = 50
                if 'tasks_page_number' not in st.session_state:
                    st.session_state['tasks_page_number'] = 0
                    
                total_pages = (len(visible_tasks) - 1) // items_per_page + 1
                curr_page = st.session_state['tasks_page_number']
                
                # Ensure valid page
                if curr_page >= total_pages: curr_page = total_pages - 1
                if curr_page < 0: curr_page = 0
                st.session_state['tasks_page_number'] = curr_page
                
                start_idx = curr_page * items_per_page
                end_idx = start_idx + items_per_page
                
                # Display Controls Top (optional, or just bottom)
                st.caption(f"Showing page {curr_page + 1} of {total_pages} ({len(visible_tasks)} tasks total)")
                
                current_page_tasks = visible_tasks[start_idx:end_idx]
                
                for index in current_page_tasks:
                    row = df.loc[index] # Access by label (original index)
                    render_task_card(index, row)
                
                # --- Pagination Controls Bottom ---
                st.markdown("---")
                col_prev, col_page, col_next = st.columns([1, 2, 1])
                
                with col_prev:
                    if st.button("Previous Page", disabled=(curr_page == 0)):
                        st.session_state['tasks_page_number'] -= 1
                        st.rerun()
                        
                with col_page:
                    st.markdown(f"**Page {curr_page + 1} / {total_pages}**", unsafe_allow_html=True)
                    
                with col_next:
                    if st.button("Next Page", disabled=(curr_page >= total_pages - 1)):
                        st.session_state['tasks_page_number'] += 1
                        st.rerun()
                        
        else:
            st.success("No unanswered questions found in selected channels!")

    # --- Dashboard 4: Bulk Messaging ---
    elif dashboard_mode == "Bulk Messaging":
        st.header("Bulk Messaging Campaign")
        
        # --- Lazy Load User Data ---
        with st.spinner("Loading user profiles..."):
             enriched_users_df = get_enriched_data_safe(df)
        
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
        # 3. Target Selection
        # Use existing 'enriched_users_df' which is cached and ready
        if 'enriched_users_df' not in locals() or enriched_users_df.empty:
             st.error("User data not loaded.")
        else:
             # Filter enriched DF by workspace if needed (it contains all users)
             # df_ws['user'] is the filtered list of users
             valid_users = set(df_ws['user'].unique())
             target_df = enriched_users_df[enriched_users_df.index.isin(valid_users)]
             
             persona_counts = target_df['Persona'].value_counts()
             
             # Create persona_df for downstream logic
             # We want a DF with columns ['User', 'Persona']
             persona_df = target_df[['Persona']].copy()
             persona_df = persona_df.reset_index() 
             # The index name in DB load might be 'user' or None
             # Check columns
             if 'user' in persona_df.columns:
                 persona_df = persona_df.rename(columns={'user': 'User'})
             elif 'User' not in persona_df.columns:
                 # Fallback if index has no name
                 persona_df['User'] = target_df.index


        
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

    # --- Dashboard 5: My TO-DO List (Moved from Sidebar) ---
    elif dashboard_mode == "My TO-DO List":
        st.header("My TO-DO List & Daily Briefing")
        st.info("Trigger your daily community briefing delivered directly to your Slack.")
        
        from ai_utils import generate_community_health_suggestion
        import time
        
        if st.button("🚀 Generate & Send Daily Briefing", type="primary"):
            with st.spinner("Analyzing community and sending daily briefing..."):
            
                # --- Message 1: Community Health ---
                # Calculate simple metrics (Last 7 days vs Previous 7 days)
                now = df['date'].max()
                last_7 = df[df['date'] > (now - timedelta(days=7))]
                prev_7 = df[(df['date'] <= (now - timedelta(days=7))) & (df['date'] > (now - timedelta(days=14)))]
                
                msg_count_now = len(last_7)
                msg_count_prev = len(prev_7)
                
                delta = msg_count_now - msg_count_prev
                trend = "INCREASE" if delta >= 0 else "REDUCTION"
                
                top_types = last_7['Message Type'].value_counts().head(3).to_dict()
                
                status_text = (
                    f"Comparison (Last 7 Days vs Previous):\n"
                    f"- Total Messages: {msg_count_now} (Trend: {trend} of {abs(delta)})\n"
                    f"- Active Users: {last_7['user'].nunique()} (vs {prev_7['user'].nunique()})\n"
                    f"- Top Message Types: {top_types}"
                )
                
                # Use a simpler placeholder if API key not valid/set to avoid hard crash
                try:
                    ai_recommendation = generate_community_health_suggestion(status_text)
                except:
                    ai_recommendation = "AI suggestions unavailable."
                
                msg1 = (
                    f"*Community Health Update*\n"
                    f"{status_text}\n\n"
                    f"*AI Recommendation:*\n{ai_recommendation}\n\n"
                    f"Dashboard: http://localhost:8501/?dashboard=Community%20Health"
                )
                
                s1, e1 = send_private_reply("rano", "Ran", msg1, simulate_typing=True)
                if not s1: st.error(f"Msg 1 failed: {e1}")
                time.sleep(1.5)
                
                # --- Message 2: Unanswered Tasks ---
                unanswered_count = len(df[df['is_unanswered']])
                msg2 = (
                    f"*Task Alert*\n"
                    f"You have *{unanswered_count}* unanswered questions pending.\n"
                    f"Go to Tasks dashboard to answer multiple queries by your users.\n"
                    f"View Tasks: http://localhost:8501/?dashboard=Tasks"
                )
                s2, e2 = send_private_reply("rano", "Ran", msg2, simulate_typing=True)
                if not s2: st.error(f"Msg 2 failed: {e2}")
                time.sleep(1.5)
                
                # --- Message 3: Retention (Mock) ---
                msg3 = (
                    f"Retention Risk Alert\n"
                    f"Our model flagged **3 key members** at risk of churn this week.\n"
                    f"This feature is coming soon to your dashboard.\n"
                    f"Stay tuned: http://localhost:8501"
                )
                s3, e3 = send_private_reply("rano", "Ran", msg3, simulate_typing=True)
                if not s3: st.error(f"Msg 3 failed: {e3}")
                time.sleep(1.5)
                
                # --- Message 4: General ---
                msg4 = (
                    f"Anything else would you like to do this week?\n"
                    f"http://localhost:8501"
                )
                s4, e4 = send_private_reply("rano", "Ran", msg4, simulate_typing=True)
                if not s4: st.error(f"Msg 4 failed: {e4}")
                
                st.success("✅ To-Do List Sent to Slack!")

if __name__ == "__main__":
    main()
    
    # End Profiling
    # Note: Streamlit execution model means this runs at end of script run.
    # We might need to handle the profiler object being in local scope of main if we want to print here.
    # Better to handle inside main if possible, but st.stop() might prevent reach.
    # Alternative: check st.session_state or just doing it inside main at the end (return).
    # But main() has returns inside.
    
    # Actually, simpler to just put it at the very end of main() before returns or use a try/finally block in main.
    # But since main is big, let's just leave it simple for now. 
    # If the user wants to see the profile, they need to ensure the script finishes.
    # Streamlit reruns might clear it.
    
    # Correct approach for Streamlit Profiling:
    # We started it in main. We should stop it and display before main returns.
    # Let's adjust chunk 1 to handle the printing inside main/sidebar or via a callback?
    # No, simplest is to just wrap the call:
    
    # (No change to this block needed if we handle it in main, but let's leave it as is)

