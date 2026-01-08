import streamlit as st
import os
import base64

# --- Image Helpers ---
def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return None

def display_image(image_filename, alt_text="Image Placeholder", use_container_width=True, centered=False, raw_html=False):
    path = os.path.join("homepage_images", image_filename)
    if raw_html:
        img_b64 = get_image_base64(path)
        if img_b64:
            ext = os.path.splitext(image_filename)[1].replace(".", "")
            if ext == "svg": ext = "svg+xml"
            return f'<img src="data:image/{ext};base64,{img_b64}" alt="{alt_text}" style="max-height: 100%; max-width: 100%; object-fit: contain;">'
        return f'<div class="placeholder-img">{alt_text}</div>'
    
    # Original Streamlit component fallback
    if os.path.exists(path):
        if centered:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(path, use_container_width=use_container_width)
        else:
            st.image(path, use_container_width=use_container_width)
    else:
        st.markdown(f'<div class="placeholder-img">{alt_text}</div>', unsafe_allow_html=True)

# --- Configuration & Setup ---
st.set_page_config(
    page_title="Communilytics | The OS for Developer Communities",
    page_icon="🚀",
    layout="wide",
)

# --- Custom Styling ---
def local_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
html, body, [class*="st-"] {
    font-family: 'Inter', sans-serif;
    background-color: #FFFFFF;
    scroll-behavior: smooth;
}
.main-container {
    max-width: 1000px;
    margin: 0 auto;
    padding-top: 100px;
}
.section-container {
    padding: 100px 0;
    border-bottom: 1px solid #F0F0F0;
}
.section-container:last-child {
    border-bottom: none;
}
h1, h2, h3 { color: #1E1E1E; }
.hero-text {
    font-size: 3.5rem;
    font-weight: 700;
    line-height: 1.1;
    margin-bottom: 1.5rem;
    text-align: center;
}
.hero-subtext {
    font-size: 1.4rem;
    color: #4A4A4A;
    text-align: center;
    margin-bottom: 3rem;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
}
.stButton button, .blue-btn {
    background-color: #007BFF;
    color: white !important;
    border-radius: 8px;
    padding: 0.75rem 2.5rem;
    font-weight: 600;
    border: none;
    transition: all 0.3s ease;
    font-size: 1.1rem;
    text-decoration: none;
    display: inline-block;
}
.stButton button:hover, .blue-btn:hover {
    background-color: #0056b3;
    transform: translateY(-2px);
    color: white !important;
}
.card {
    background-color: #FFFFFF;
    padding: 1.75rem;
    border-radius: 12px;
    border: 1px solid #EAEAEA;
    text-align: center;
    min-height: 150px; /* Reduced min-height slightly for tighter feel */
    display: flex;
    flex-direction: column;
    justify-content: center;
    transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
    box-shadow: 0 4px 6px rgba(0,0,0,0.02);
}
.card:hover {
    box-shadow: 0 20px 40px rgba(0,0,0,0.06);
    border-color: #007BFF;
    transform: translateY(-5px);
}
.card h4 {
    margin-top: 0;
    margin-bottom: 0.5rem;
    font-size: 1.15rem;
    font-weight: 700;
    color: #1E1E1E;
}
.card p {
    margin: 0;
    font-size: 0.92rem;
    color: #666666;
    line-height: 1.5;
}
/* This container ensures all grey boxes start at the exact same vertical position */
.feature-col-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 15px; /* Add breathing room between tiles */
}
.feature-image-wrapper {
    height: 180px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 5px; 
    overflow: hidden;
    padding: 10px;
}
.feature-image-wrapper img {
    max-height: 160px !important;
    width: auto !important;
    object-fit: contain !important;
    transition: transform 0.4s ease;
}
.feature-col-container:hover .feature-image-wrapper img {
    transform: scale(1.05); /* Subtle image zoom on card hover */
}
.terminal-window {
    background-color: #1E1E1E;
    color: #00FF00;
    font-family: 'JetBrains Mono', monospace;
    padding: 2rem;
    border-radius: 12px;
    border-top: 30px solid #333;
    box-shadow: 0 20px 50px rgba(0,0,0,0.4);
    margin-top: 3rem;
    position: relative;
}
.terminal-window::before {
    content: "● ● ●";
    position: absolute;
    top: -22px;
    left: 15px;
    color: #666;
    font-size: 12px;
}
.terminal-text {
    margin: 0;
    font-size: 1rem;
    line-height: 1.8;
}
.status-online {
    color: #00FF00;
    font-weight: bold;
}
blockquote {
    border-left: 8px solid #FF4B4B;
    padding-left: 2rem;
    font-style: italic;
    color: #333;
    margin: 4rem 0;
    font-size: 1.5rem;
    line-height: 1.4;
    padding: 2rem;
    border-radius: 0 16px 16px 0;
}
.logo-cloud {
    text-align: center;
    margin-top: 5rem;
    opacity: 0.8;
}
.fixed-nav {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.98);
    z-index: 999999;
    box-shadow: 0 2px 15px rgba(0,0,0,0.08);
    padding: 10px 0;
    display: flex;
    justify-content: center;
    align-items: center;
    backdrop-filter: blur(5px);
}
.nav-inner {
    max-width: 1000px;
    width: 100%;
    display: flex;
    justify-content: space-around;
    gap: 10px;
}
.nav-item {
    color: #444;
    text-decoration: none;
    font-size: 0.95rem;
    font-weight: 500;
    padding: 8px 16px;
    border-radius: 8px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
}
.nav-item i {
    font-size: 1.1rem;
    color: #FF4B4B;
}
.nav-item:hover {
    background-color: #FEEEEE;
    color: #007BFF;
}
.nav-logo {
    height: 48px;
    width: auto;
    object-fit: contain;
}
:target::before {
    content: "";
    display: block;
    height: 100px;
    margin: -100px 0 0;
}
.back-to-top {
    position: fixed;
    bottom: 30px;
    right: 30px;
    background-color: #FF4B4B;
    color: white;
    padding: 10px 15px;
    border-radius: 50%;
    text-decoration: none;
    box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    z-index: 1001;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 45px;
    height: 45px;
}
header, footer, #MainMenu { visibility: hidden !important; height: 0 !important; }
</style>
""", unsafe_allow_html=True)

local_css()

# --- Navigation Bar with Base64 Logo ---
logo_b64 = get_image_base64(os.path.join("homepage_images", "logo1.jpg"))
logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="nav-logo" alt="Communilytics">' if logo_b64 else "Communilytics"

st.markdown(f"""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
<div class="fixed-nav">
    <div class="nav-inner">
        <a href="#welcome" class="nav-item">{logo_html}</a>
        <a href="#agony" class="nav-item"><i class="bi bi-exclamation-triangle"></i> The Why?</a>
        <a href="#features" class="nav-item"><i class="bi bi-cpu"></i> Features</a>
        <a href="#insights" class="nav-item"><i class="bi bi-chat-quote"></i> Insights</a>
        <a href="#agent" class="nav-item"><i class="bi bi-robot"></i> Your Agent</a>
        <a href="#start" class="nav-item"><i class="bi bi-calendar-check"></i> Get Started</a>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Navigation Bar with Base64 Logo ---
# This banner is placed outside the main-container to be screen-wide
st.markdown('<div style="margin-top: 55px; margin-bottom: -20px; line-height: 0;">', unsafe_allow_html=True)
display_image("community banner.jpg", "Community Banner", use_container_width=True, centered=False)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="main-container" style="padding-top: 0px;">', unsafe_allow_html=True)

# --- Step 1: Welcome (The Hero) ---
st.markdown('<div id="welcome" class="section-container" style="padding-top: 0px; text-align: center; border-bottom: none;">', unsafe_allow_html=True)
st.markdown('<p class="hero-text">The Operating System For Developer Communities.</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtext" style="text-align: center; margin-left: auto; margin-right: auto;">Bridge The Gap Between Slack, Discord, Reddit, And Your Internal Workflows In Jira And Salesforce. Turn Fragmented Conversations Into Actionable Product Insights.</p>', unsafe_allow_html=True)

# Using a centered HTML button for reliable anchor scrolling
st.markdown('<div style="text-align: center; margin-bottom: 3rem;"><a href="#start" class="blue-btn">Learn More</a></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- Step 2: The Agony (The Pain Points) ---
st.markdown('<div id="agony" class="section-container">', unsafe_allow_html=True)
st.markdown("<h2 style='text-align: center; margin-bottom: 3rem;'>Why Community Management Feels Like Chaos.</h2>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    display_image("multi source.jpg", "The Multi-Source Chaos")
    st.markdown("### The Multi-Source Chaos")
    st.write("Your data lives in four different places. You have no single source of truth.")
    
with col2:
    display_image("operational gap.jpg", "The Operational Gap")
    st.markdown("### The Operational Gap")
    st.write("Discord mods say one thing, Engineering in Jira does another. There is no uniformity.")
    
with col3:
    display_image("ghost member.jpg", "The Ghost Member")
    st.markdown("### The Ghost Member")
    st.write("You don't know who your champions are until they’ve already churned.")
st.markdown('</div>', unsafe_allow_html=True)

# --- Step 3: Features (The 3x3 Toolset) ---
st.markdown('<div id="features" class="section-container">', unsafe_allow_html=True)
st.markdown("<h2 style='text-align: center; margin-bottom: 4rem;'>Communlytics feature set is everything community managers need</h2>", unsafe_allow_html=True)

features = [
    ("Community Health", "Real-time engagement velocity index.", "community health.jpg"),
    ("Dynamic Segmentation", "Bulk messaging based on behavior.", "dynamic segmentation.jpg"),
    ("Leaderboards", "Track top 1% contributors.", "leader boards.jpg"),
    ("User Journeys", "Visual timeline from Reddit lurker to customer.", "user journey.jpg"),
    ("Unified Knowledge Base", "AI-synced repository from all threads.", "unified knowledgebase.jpg"),
    ("Retention Model", "Sophisticated churn prediction for public groups.", "retention model.jpg"),
    ("MCP Internal Sync", "Update Salesforce/Jira via Model Context Protocol.", "mcp internal sync.jpg"),
    ("AI Task Prioritization", "Daily 'Next Best Actions' list.", "ai task prioritization.jpg"),
    ("Core Moderation", "Auto-welcomes, alerts, and spam filters included.", "core moderation.jpg"),
]

# 3x3 Grid
for i in range(0, 9, 3):
    cols = st.columns(3)
    for j in range(3):
        if i + j < len(features):
            title, desc, img_name = features[i+j]
            with cols[j]:
                # Using a single markdown block for perfect alignment
                img_html = display_image(img_name, title, raw_html=True)
                st.markdown(f"""
                <div class="feature-col-container">
                    <div class="feature-image-wrapper">
                        {img_html}
                    </div>
                    <div class="card">
                        <h4>{title}</h4>
                        <p>{desc}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    st.write(" ")
st.markdown('</div>', unsafe_allow_html=True)

# --- Step 4: Insights (Social Proof) ---
st.markdown('<div id="insights" class="section-container">', unsafe_allow_html=True)
st.markdown("<h2 style='text-align: center; margin-bottom: 3rem;'>What Community Leaders Say</h2>", unsafe_allow_html=True)

col_text, col_img = st.columns([1, 1.5])

with col_text:
    st.markdown("> \"There was no way to know what the member feels without Communilytics.\"", unsafe_allow_html=True)
    st.markdown("> <p style='text-align: right; font-style: italic; color: #666; margin-top: -1rem;'>— Stephen La Croix, Owner at Study together</p>", unsafe_allow_html=True)
    st.markdown("> \"We were never able to segment our customers on our community until now.\"", unsafe_allow_html=True)
    st.markdown("> <p style='text-align: right; font-style: italic; color: #666; margin-top: -1rem;'>— Shriyash Soni, Founder of Apna Coding</p>", unsafe_allow_html=True)
    st.markdown("> \"It finally standardized our ROI metrics to drive our next business steps.\"", unsafe_allow_html=True)

with col_img:
    display_image("social.jpg", "Social Proof", use_container_width=True, centered=False)
st.markdown('</div>', unsafe_allow_html=True)

# --- Step 5: Your Agent (The Partner) ---
st.markdown('<div id="agent" class="section-container">', unsafe_allow_html=True)
st.markdown("<h2 style='margin-bottom: 1.5rem;'>Your Agent is ready to jump in.</h2>", unsafe_allow_html=True)
st.write("Are you ready to AI your community? Book a demo today and be off and running by next week.")

st.markdown("""
    <div class="terminal-window">
        <p class="terminal-text"><span class="status-online">[STATUS: ONLINE]</span></p>
        <p class="terminal-text">[SYNC COMPLETE: Slack/Jira/Wiki]</p>
        <p class="terminal-text">[REPORT READY: Weekly Jour Fixe]</p>
    </div>
""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- Step 6: Get Started (Final CTA) ---
st.markdown('<div id="start" class="section-container">', unsafe_allow_html=True)
st.markdown("<h2 style='text-align: center; margin-bottom: 3rem;'>Ready to Scale Your Community?</h2>", unsafe_allow_html=True)

col_cta_left, col_cta_right = st.columns(2)
with col_cta_left:
    st.markdown("### Book a Demo")
    import streamlit.components.v1 as components
    components.html(
        """
        <!-- Calendly inline widget begin -->
        <div class="calendly-inline-widget" data-url="https://calendly.com/ran_kysaas/30min" style="min-width:320px;height:700px;"></div>
        <script type="text/javascript" src="https://assets.calendly.com/assets/external/widget.js" async></script>
        <!-- Calendly inline widget end -->
        """,
        height=700,
    )

with col_cta_right:
    st.markdown("### Already a Member?")
    st.markdown("""
        <div style="height: 700px; display: flex; flex-direction: column; justify-content: center; align-items: center; border: 1px solid #EAEAEA; border-radius: 12px; background: #F9F9F9;">
            <p style="font-size: 1.2rem; color: #4A4A4A; margin-bottom: 2rem;">Access your dashboard and insights.</p>
            <a href="http://localhost:8501" target="_blank" class="blue-btn">Go to application</a>
        </div>
    """, unsafe_allow_html=True)

# --- Footer ---
st.markdown("""
    <div style='margin-top: 5rem; padding-top: 3rem; border-top: 1px solid #EEE; text-align: center;'>
        <div style='color: #888; font-size: 1rem; max-width: 800px; margin: 0 auto;'>
            Your community management agent comes ready for every <b>Jour Fixe</b>. 
            It arrives with all issues and next steps prioritized to drive your community forward. 
            It’s not a dashboard; it’s a strategy.
        </div>
        <a href="#welcome" class="back-to-top">↑</a>
    </div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # End of section-container
st.markdown('</div>', unsafe_allow_html=True) # End of main-container
