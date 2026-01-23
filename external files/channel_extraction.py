import os
import json
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- Configuration ---
# Your Bot User OAuth Token (xoxb-...)
# It's best practice to load this from an environment variable.
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")

# The name of the channel you want to extract data from
# Example: "general", "my-private-channel"
TARGET_CHANNEL_NAME = "test" # <<<--- CHANGE THIS TO YOUR CHANNEL NAME

# Output directory for the data
OUTPUT_DIR = "slack_data_export"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Initialize Slack Client ---
if not SLACK_BOT_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN environment variable not set.")
client = WebClient(token=SLACK_BOT_TOKEN)

# --- Helper Functions ---

def get_channel_id(channel_name):
    """Fetches the ID of a channel by its name."""
    try:
        # Fetch all conversations (channels, private channels, DMs)
        # types: public_channel, private_channel, im, mpim
        response = client.conversations_list(types="public_channel,private_channel", limit=1000)
        channels = response["channels"]
        for channel in channels:
            if channel["name"] == channel_name:
                print(f"Found channel '{channel_name}' with ID: {channel['id']}")
                return channel["id"]
        print(f"Channel '{channel_name}' not found.")
        return None
    except SlackApiError as e:
        print(f"Error fetching channel list: {e.response['error']}")
        return None

def get_user_info(user_id):
    """Fetches user information and caches it."""
    if user_id not in user_cache:
        try:
            response = client.users_info(user=user_id)
            user_cache[user_id] = response["user"]
            print(f"Fetched info for user: {user_cache[user_id]['real_name']}")
        except SlackApiError as e:
            print(f"Error fetching user info for {user_id}: {e.response['error']}")
            user_cache[user_id] = {"id": user_id, "real_name": "Unknown User", "is_bot": False} # Placeholder
    return user_cache[user_id]

def get_channel_history(channel_id):
    """Fetches all messages from a channel, handling pagination."""
    all_messages = []
    has_more = True
    cursor = None
    
    print(f"\nFetching message history for channel ID: {channel_id}...")

    while has_more:
        try:
            response = client.conversations_history(
                channel=channel_id,
                limit=1000, # Max messages per page
                cursor=cursor
            )
            messages = response["messages"]
            all_messages.extend(messages)
            has_more = response["has_more"]
            if has_more:
                cursor = response["response_metadata"]["next_cursor"]
                print(f"  Fetched {len(messages)} messages, total: {len(all_messages)}. Getting next page...")
                time.sleep(1) # Be kind to the API and avoid rate limits
            else:
                print(f"  Fetched all {len(all_messages)} messages.")

        except SlackApiError as e:
            if e.response["error"] == "not_in_channel":
                print(f"Error: Bot is not in channel ID '{channel_id}'. Please invite the bot to the channel.")
            else:
                print(f"Error fetching channel history: {e.response['error']}")
            break
    return all_messages

def get_channel_files(channel_id):
    """Fetches metadata for all files in a channel."""
    all_files = []
    has_more = True
    page = 1
    
    print(f"\nFetching files for channel ID: {channel_id}...")

    while has_more:
        try:
            response = client.files_list(
                channel=channel_id,
                page=page,
                count=1000 # Max files per page
            )
            files = response["files"]
            all_files.extend(files)
            has_more = response["paging"]["pages"] > response["paging"]["page"]
            if has_more:
                page += 1
                print(f"  Fetched {len(files)} files, total: {len(all_files)}. Getting next page...")
                time.sleep(1) # Be kind to the API
            else:
                print(f"  Fetched all {len(all_files)} files.")

        except SlackApiError as e:
            print(f"Error fetching files for channel: {e.response['error']}")
            break
    return all_files

# --- Main Execution ---
if __name__ == "__main__":
    user_cache = {} # Cache for user information

    print(f"Starting data extraction for channel: {TARGET_CHANNEL_NAME}")

    # 1. Get Channel ID
    channel_id = get_channel_id(TARGET_CHANNEL_NAME)
    if not channel_id:
        print("Exiting. Could not find target channel or bot not in it.")
        exit()

    # 2. Get Channel Info
    try:
        channel_info_response = client.conversations_info(channel=channel_id)
        channel_info = channel_info_response["channel"]
        print("\n--- Channel Details ---")
        print(f"Name: {channel_info.get('name')}")
        print(f"ID: {channel_info.get('id')}")
        print(f"Topic: {channel_info.get('topic', {}).get('value')}")
        print(f"Purpose: {channel_info.get('purpose', {}).get('value')}")
        print(f"Is Private: {channel_info.get('is_private')}")
        print(f"Members Count: {channel_info.get('num_members')}")

        with open(os.path.join(OUTPUT_DIR, f"{TARGET_CHANNEL_NAME}_channel_info.json"), "w", encoding="utf-8") as f:
            json.dump(channel_info, f, indent=4)
        print(f"Saved channel info to {OUTPUT_DIR}/{TARGET_CHANNEL_NAME}_channel_info.json")

    except SlackApiError as e:
        print(f"Error fetching channel info: {e.response['error']}")
        # This error might also mean the bot isn't in the channel.
        print("Please ensure your bot is invited to the channel.")
        exit()

    # 3. Get Message History
    messages = get_channel_history(channel_id)

    # Enhance messages with user info and process files attached to messages
    processed_messages = []
    all_files_in_messages = []
    if messages:
        for msg in messages:
            # Replace user ID with real name
            if "user" in msg:
                user_info = get_user_info(msg["user"])
                msg["user_info"] = {
                    "id": user_info.get("id"),
                    "name": user_info.get("real_name"),
                    "is_bot": user_info.get("is_bot")
                }
                # Remove original user ID for clarity if you prefer
                # del msg["user"]
            
            # Extract file info linked to messages
            if "files" in msg:
                for file_data in msg["files"]:
                    all_files_in_messages.append(file_data)
            processed_messages.append(msg)

        with open(os.path.join(OUTPUT_DIR, f"{TARGET_CHANNEL_NAME}_messages.json"), "w", encoding="utf-8") as f:
            json.dump(processed_messages, f, indent=4)
        print(f"Saved {len(processed_messages)} messages to {OUTPUT_DIR}/{TARGET_CHANNEL_NAME}_messages.json")
    else:
        print("No messages found or accessible.")

    # 4. Get All Files (from files.list API)
    # Note: files.list is separate from files attached to messages in history
    # files.list gives you all files uploaded/shared in the channel, even if not linked to a message directly
    all_channel_files = get_channel_files(channel_id)
    if all_channel_files:
        with open(os.path.join(OUTPUT_DIR, f"{TARGET_CHANNEL_NAME}_files_list.json"), "w", encoding="utf-8") as f:
            json.dump(all_channel_files, f, indent=4)
        print(f"Saved {len(all_channel_files)} file metadata to {OUTPUT_DIR}/{TARGET_CHANNEL_NAME}_files_list.json")
    else:
        print("No files found or accessible via files.list.")

    print("\nData extraction complete!")