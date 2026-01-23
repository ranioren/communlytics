import os
import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
BASE_URL = "https://slack.com/api"

import streamlit as st

def get_headers():
    return {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json"
    }

@st.cache_data(ttl=3600)
def _fetch_all_users():
    """
    Fetches the list of all users from Slack. Cached for 1 hour.
    """
    url = f"{BASE_URL}/users.list"
    try:
        response = requests.get(url, headers=get_headers())
        if response.status_code != 200:
            return None, f"API Error: {response.text}"
        
        data = response.json()
        if not data.get("ok"):
            return None, f"Slack Error: {data.get('error')}"
            
        return data.get("members", []), None
    except Exception as e:
        return None, str(e)

def find_user_id(query_name="rano"):
    """
    Finds a Slack User ID by matching display name, real name, or name.
    Uses cached user list.
    """
    members, err = _fetch_all_users()
    if err:
        return None, err
        
    query = query_name.lower()
    
    for member in members:
        if member.get("deleted"): continue
        
        # Check various name fields
        real_name = member.get("real_name", "").lower()
        name = member.get("name", "").lower()
        display_name = member.get("profile", {}).get("display_name", "").lower()
        
        if query == name or query == display_name or query in real_name:
            return member["id"], None
            
    return None, f"User '{query_name}' not found."

def update_chat_message(channel_id, ts, text):
    """
    Updates an existing Slack message.
    """
    url = f"{BASE_URL}/chat.update"
    payload = {
        "channel": channel_id,
        "ts": ts,
        "text": text
    }
    try:
        res = requests.post(url, headers=get_headers(), json=payload)
        return res.json().get("ok", False)
    except:
        return False

import time

def send_dm(user_id, text, simulate_typing=False):
    """
    Opens a DM channel and sends a message.
    If simulate_typing is True, sends 'Drafting...' first, then updates.
    """
    # 1. Open Conversation
    open_url = f"{BASE_URL}/conversations.open"
    open_payload = {"users": user_id}
    
    try:
        open_res = requests.post(open_url, headers=get_headers(), json=open_payload)
        open_data = open_res.json()
        
        if not open_data.get("ok"):
            return False, f"Failed to open DM: {open_data.get('error')}"
            
        channel_id = open_data["channel"]["id"]
        
        # 2. Post Message
        post_url = f"{BASE_URL}/chat.postMessage"
        
        if simulate_typing:
            # Send placeholder
            post_payload = {
                "channel": channel_id,
                "text": "✍️ *Drafting response...*" 
            }
            post_res = requests.post(post_url, headers=get_headers(), json=post_payload)
            post_data = post_res.json()
            
            if not post_data.get("ok"):
                 return False, f"Failed to send placeholder: {post_data.get('error')}"
            
            ts = post_data["ts"]
            
            # Simulate delay (human-like)
            time.sleep(0.5)
            
            # Update with actual text
            success = update_chat_message(channel_id, ts, text)
            if success:
                return True, "Message sent (with typing effect)!"
            else:
                return False, "Failed to update placeholder."
        else:
            # Standard Send
            post_payload = {
                "channel": channel_id,
                "text": text
            }
            post_res = requests.post(post_url, headers=get_headers(), json=post_payload)
            post_data = post_res.json()
            
            if post_data.get("ok"):
                return True, "Message sent successfully!"
            else:
                return False, f"Failed to send: {post_data.get('error')}"
            
    except Exception as e:
        return False, str(e)

def send_private_reply(target_handle, original_asker_name, reply_text, simulate_typing=False):
    """
    Wrapper to find 'rano' (or target) and send the formatted message.
    """
    if not SLACK_TOKEN:
        return False, "Missing SLACK_BOT_TOKEN in .env"
        
    user_id, err = find_user_id(target_handle)
    if not user_id:
        return False, err
        
    formatted_message = f"Hi {original_asker_name}, {reply_text}"
    return send_dm(user_id, formatted_message, simulate_typing=simulate_typing)

@st.cache_data(ttl=3600)
def _fetch_all_public_channels():
    """
    Fetches list of public channels. Cached for 1 hour.
    """
    url = f"{BASE_URL}/conversations.list"
    params = {
        "types": "public_channel",
        "exclude_archived": "true",
        "limit": 1000
    }
    
    try:
        response = requests.get(url, headers=get_headers(), params=params)
        data = response.json()
        
        if not data.get("ok"):
            return None, f"Slack Error: {data.get('error')}"
            
        return data.get("channels", []), None
    except Exception as e:
        return None, str(e)

def find_channel_id(channel_name):
    """
    Finds a public channel ID by name (e.g. 'general').
    Uses cached channel list.
    """
    channels, err = _fetch_all_public_channels()
    if err:
        return None, err
        
    query = channel_name.lstrip('#').lower()
    
    for ch in channels:
        if ch["name"].lower() == query:
            return ch["id"], None
            
    return None, f"Channel '#{query}' not found."

def send_channel_reply(channel_name, reply_text):
    """
    Posts a message to a specific public channel.
    """
    if not SLACK_TOKEN:
        return False, "Missing SLACK_BOT_TOKEN in .env"
        
    channel_id, err = find_channel_id(channel_name)
    if not channel_id:
        return False, err
        
    # Post Message (Standard chat.postMessage)
    url = f"{BASE_URL}/chat.postMessage"
    payload = {
        "channel": channel_id,
        "text": reply_text
    }
    
    try:
        res = requests.post(url, headers=get_headers(), json=payload)
        data = res.json()
        
        if data.get("ok"):
            return True, f"Posted to #{channel_name}!"
        else:
            return False, f"Failed to post: {data.get('error')}"
    except Exception as e:
        return False, str(e)
