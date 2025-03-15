"""
Script to run the MCP server independently.
"""

import json
import logging
import os
import pathlib
import sys

from adapter import AuthedMCPServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run the MCP server."""
    # Load credentials from JSON file
    creds_path = pathlib.Path(__file__).parent / "credentials.json"
    
    try:
        with open(creds_path, "r") as f:
            creds = json.load(f)
            
        # Use agent_a as the server
        registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
        agent_id = creds["agent_a_id"]
        agent_secret = creds["agent_a_secret"]
        private_key = creds["agent_a_private_key"]
        public_key = creds["agent_a_public_key"]
        
        logger.info(f"Loaded credentials for agent: {agent_id}")
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading credentials: {str(e)}")
        return
    
    # Create MCP server with Authed authentication
    server = AuthedMCPServer(
        name="example-server",
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    
    # Register a resource handler
    @server.resource("hello/{name}")
    async def hello_resource(name: str):
        logger.info(f"Resource request for name: {name}")
        return f"Hello, {name}!", "text/plain"
    
    # Register a tool handler
    @server.tool("echo")
    async def echo_tool(message: str):
        logger.info(f"Tool request with message: {message}")
        return {"message": message}
    
    # Register a prompt handler
    @server.prompt("greeting")
    async def greeting_prompt(name: str = "World"):
        logger.info(f"Prompt request for name: {name}")
        return f"Hello, {name}! Welcome to the MCP server."
    
    # Run the server - don't use asyncio.run() here
    # Let the MCP server handle its own event loop
    logger.info("Starting MCP server...")
    server.mcp.run()  # This will block until the server exits

if __name__ == "__main__":
    main()  # Call main directly, not through asyncio.run()
