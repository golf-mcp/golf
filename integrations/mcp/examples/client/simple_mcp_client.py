"""
Example MCP Client with Authed Authentication

This example demonstrates how to:
1. Create an MCP client that connects to an Authed-protected server
2. Handle authentication for both SSE (GET) and message (POST) requests
3. Call remote tools exposed by the server
4. Manage the client lifecycle (connect/disconnect)

Usage:
    1. Copy .env.example to .env and fill in your Authed credentials
    2. Make sure TARGET_AGENT_ID is set to the server's agent ID
    3. Run the client: python simple_mcp_client.py
    4. The client will connect to http://localhost:8000/sse by default

Security Notes:
    - Always use HTTPS in production
    - Keep your agent secrets secure
    - Make sure your agent ID is different from the server's
    - Verify the server's agent ID before connecting
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from authed.sdk import Authed
from mcp import ClientSession
from mcp.client.sse import sse_client
from authed_mcp.client import get_auth_headers

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMCPClient:
    def __init__(self):
        """Initialize the MCP client with Authed authentication."""
        # Initialize Authed SDK with credentials from environment
        self.authed = Authed.initialize(
            registry_url=os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev"),
            agent_id=os.getenv("AUTHED_AGENT_ID"),
            agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
            private_key=os.getenv("AUTHED_PRIVATE_KEY"),
            public_key=os.getenv("AUTHED_PUBLIC_KEY")
        )
        
        # Server URL to connect to
        self.server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")
        
        # Get target agent ID - this should be the agent ID of the server we're connecting to
        self.target_agent_id = os.getenv("TARGET_AGENT_ID")
        if not self.target_agent_id:
            logger.warning("TARGET_AGENT_ID not set - authentication may fail")
        
        # Connection state
        self.session = None
        self._streams_context = None
        self._session_context = None
    
    async def connect(self):
        """Connect to the MCP server with authentication.
        
        This method:
        1. Verifies the target agent ID
        2. Generates authentication headers for the SSE connection
        3. Establishes the SSE connection
        4. Initializes the MCP session
        """
        try:
            # Get target agent ID - the ID of the server we're connecting to
            target_agent_id = self.target_agent_id
            self_agent_id = self.authed.agent_id
            
            # Check if target_agent_id is the same as self_agent_id (this won't work)
            if target_agent_id and target_agent_id == self_agent_id:
                logger.warning(f"Target agent ID ({target_agent_id}) is the same as this agent's ID - this will not work with Authed")
                target_agent_id = None
            
            # Get authentication headers using authed-mcp
            headers = await get_auth_headers(
                authed=self.authed,
                url=self.server_url,
                method="GET",
                target_agent_id=target_agent_id,
                fallback=False,  # Don't allow fallback to basic auth
                debug=True  # Enable debug logging
            )
            
            # Create and enter SSE client context
            self._streams_context = sse_client(
                url=self.server_url,
                headers=headers,
                timeout=30.0
            )
            streams = await self._streams_context.__aenter__()
            
            # Create and enter session context
            self._session_context = ClientSession(*streams)
            self.session = await self._session_context.__aenter__()
            
            # Initialize the session
            await self.session.initialize()
            
            # Verify connection by listing available tools
            response = await self.session.list_tools()
            logger.info(f"Connected to server. Available tools: {[t.name for t in response.tools]}")
            
            return self.session
            
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            raise
    
    async def disconnect(self):
        """Disconnect from the MCP server and clean up resources."""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
            if self._streams_context:
                await self._streams_context.__aexit__(None, None, None)
            self.session = None
            logger.info("Disconnected from server")
        except Exception as e:
            logger.error(f"Disconnect failed: {str(e)}")
            raise
    
    async def call_remote_tool(self, tool_name: str, params: dict = None):
        """Call a remote tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            params: Parameters to pass to the tool
            
        Returns:
            The result from the tool
        """
        if not self.session:
            await self.connect()
        
        try:
            logger.info(f"Calling remote tool: {tool_name} with params: {params}")
            result = await self.session.call_tool(tool_name, params)
            logger.info(f"Tool result: {result.content}")
            return result.content
        except Exception as e:
            logger.error(f"Tool call failed: {str(e)}")
            raise

async def main():
    """Example usage of the SimpleMCPClient."""
    client = SimpleMCPClient()
    
    try:
        # Connect to the server
        await client.connect()
        
        # Example: Call the echo tool
        result = await client.call_remote_tool("echo", {"message": "Hello from client!"})
        print(f"Echo result: {result}")
        
        # Example: Call the add_numbers tool
        result = await client.call_remote_tool("add_numbers", {"a": 5, "b": 3})
        print(f"Addition result: {result}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Always disconnect properly
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 