import os
import urllib.parse
import requests
import asyncio
import nest_asyncio
import streamlit as st
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
# Patch loop for streamlit
nest_asyncio.apply()

# Constants
# Use the EU1 domain if that's what was in your install link, 
# otherwise standard is mcp.hubspot.com. 
# based on your link: https://mcp-eu1.hubspot.com/oauth/authorize/...
MCP_SERVER_URL = "https://mcp-eu1.hubspot.com/sse" 
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
REDIRECT_URI = "http://localhost:6274/oauth/callback/debug" # Must match app config

def get_auth_url():
    """Generates the HubSpot OAuth Authorization URL."""
    client_id = os.getenv("HUBSPOT_CLIENT_ID")
    if not client_id:
        return None
    
    # Scopes might need adjustment based on what tools you need, 
    # but initially we just hit the auth endpoint.
    # The install link you provided had:
    # client_id=...&redirect_uri=...
    base = "https://mcp-eu1.hubspot.com/oauth/authorize/user"
    encoded_redirect = urllib.parse.quote(REDIRECT_URI, safe='')
    return f"{base}?client_id={client_id}&redirect_uri={encoded_redirect}"

def exchange_code_for_token(auth_code):
    """Exchanges the temporary auth code for an access token."""
    client_id = os.getenv("HUBSPOT_CLIENT_ID")
    client_secret = os.getenv("HUBSPOT_CLIENT_SECRET")
    
    if not all([client_id, client_secret, auth_code]):
        return None, "Missing credentials or code."

    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code
    }
    
    try:
        response = requests.post(TOKEN_URL, data=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("access_token"), None
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP Error: {e.response.text}"
    except Exception as e:
        return None, str(e)

# --- MCP Client Logic ---

class HubSpotMCPClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        """
        Connects to the HubSpot MCP SSE endpoint.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "text/event-stream"
        }
        
        # We use the sse_client helper from mcp
        # Note: We need to keep this connection alive.
        # This structure might be tricky in Streamlit reruns.
        # We'll see if we can do stateless 'connect-run-disconnect' for now
        # or if we need a persistent session.
        pass

    async def list_tools(self):
        """Lists available tools from the HubSpot MCP Server."""
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            async with sse_client(MCP_SERVER_URL, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return result.tools
        except Exception as e:
            st.error(f"MCP Connection Error: {e}")
            return []

    async def call_tool(self, tool_name, arguments=None):
        """Calls a specific tool."""
        if arguments is None:
            arguments = {}
            
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
             async with sse_client(MCP_SERVER_URL, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result
        except Exception as e:
            return f"Error calling tool: {e}"

# Synchronous wrappers for Streamlit
def sync_list_tools(token):
    client = HubSpotMCPClient(token)
    return asyncio.run(client.list_tools())

def sync_call_tool(token, tool_name, args):
    client = HubSpotMCPClient(token)
    return asyncio.run(client.call_tool(tool_name, args))
