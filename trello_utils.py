import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TRELLO_API_KEY")
TOKEN = os.getenv("TRELLO_TOKEN")
BASE_URL = "https://api.trello.com/1"

def get_auth_params():
    return {
        'key': API_KEY,
        'token': TOKEN
    }

def get_board_id(board_name_preference=["Communlytics", "Personal", "To Do"]):
    """
    Finds a board ID. Tries names in preference order. 
    If none match, returns the first board found.
    """
    url = f"{BASE_URL}/members/me/boards"
    response = requests.get(url, params=get_auth_params())
    
    if response.status_code != 200:
        return None, f"Failed to fetch boards: {response.text}"
        
    boards = response.json()
    if not boards:
        return None, "No boards found."
        
    # Try to find by name
    for name in board_name_preference:
        for board in boards:
            if board['name'].lower() == name.lower() and not board['closed']:
                return board['id'], None
    
    # Fallback to first open board
    for board in boards:
        if not board['closed']:
             return board['id'], None
             
    return None, "No open boards available."

def get_list_id(board_id, list_name="today"):
    """
    Finds a list ID on the given board. 
    If not found, returns the ID of the first list.
    """
    url = f"{BASE_URL}/boards/{board_id}/lists"
    response = requests.get(url, params=get_auth_params())
    
    if response.status_code != 200:
        return None, f"Failed to fetch lists: {response.text}"
        
    lists = response.json()
    if not lists:
        return None, "No lists on this board."
        
    # Try exact match
    for lst in lists:
        if lst['name'].lower() == list_name.lower():
            return lst['id'], None
            
    # Fallback
    return lists[0]['id'], None

def create_card(list_id, name, desc):
    """Creates a card on the specified list."""
    url = f"{BASE_URL}/cards"
    params = get_auth_params()
    params.update({
        'idList': list_id,
        'name': name,
        'desc': desc
    })
    
    response = requests.post(url, params=params)
    if response.status_code == 200:
        return True, response.json()['url']
    else:
        return False, response.text

def add_trello_task(user_name, question_text, note_text):
    """
    Orchestrates the creation of a Trello task.
    """
    if not API_KEY or not TOKEN:
        return False, "Missing Trello Credentials in .env"

    # 1. Get Board
    board_id, err = get_board_id()
    if not board_id:
        return False, f"Board Error: {err}"
        
    # 2. Get List
    list_id, err = get_list_id(board_id, "Today")
    if not list_id:
        return False, f"List Error: {err}"
        
    # 3. Create Card
    title = f"New Task from Communilytics member name - {user_name}"
    description = f"**Unanswered Question:**\n{question_text}\n\n**Notes/Draft:**\n{note_text}"
    
    success, result = create_card(list_id, title, description)
    if success:
        return True, "Card created successfully!"
    else:
        return False, f"API Error: {result}"
