"""
Example MCP client with Authed authentication.

This example demonstrates how to create an MCP client with Authed authentication.
"""

import asyncio
import json
import logging
import os
import pathlib
import sys

from adapter import AuthedMCPClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set Authed SDK logger to DEBUG
logging.getLogger('client.sdk').setLevel(logging.DEBUG)
logging.getLogger('client.sdk.auth').setLevel(logging.DEBUG)

async def main():
    """Run the example MCP client."""
    # Load credentials from JSON file
    creds_path = pathlib.Path(__file__).parent / "credentials.json"
    
    try:
        with open(creds_path, "r") as f:
            creds = json.load(f)
            
        # Use agent_b as the client
        registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
        agent_id = creds["agent_b_id"]
        agent_secret = creds["agent_b_secret"]
        private_key = creds["agent_b_private_key"]
        public_key = creds["agent_b_public_key"]
        
        # Use agent_a as the server
        server_agent_id = creds["agent_a_id"]
        
        logger.info(f"Loaded credentials for client agent: {agent_id}")
        logger.info(f"Using server agent: {server_agent_id}")
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading credentials: {str(e)}")
        return
    
    # Create MCP client with Authed authentication
    logger.info("Creating AuthedMCPClient...")
    client = AuthedMCPClient(
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    logger.info("AuthedMCPClient created successfully")
    
    # Define server URL
    server_url = "http://localhost:8000/sse"
    logger.info(f"Using server URL: {server_url}")
    
    try:
        # List resources
        logger.info("Listing resources...")
        resources = await client.list_resources(server_url, server_agent_id)
        logger.info(f"Resources: {resources}")
        
        # List tools
        logger.info("Listing tools...")
        tools = await client.list_tools(server_url, server_agent_id)
        logger.info(f"Tools: {tools}")
        
        # List prompts
        logger.info("Listing prompts...")
        prompts = await client.list_prompts(server_url, server_agent_id)
        logger.info(f"Prompts: {prompts}")
        
        # Call a tool
        logger.info("Calling echo tool...")
        result = await client.call_tool(
            server_url=server_url,
            server_agent_id=server_agent_id,
            tool_name="echo",
            arguments={"message": "Hello from MCP client!"}
        )
        logger.info(f"Echo result: {result}")
        
        # Get a prompt
        logger.info("Getting greeting prompt...")
        prompt = await client.get_prompt(
            server_url=server_url,
            server_agent_id=server_agent_id,
            prompt_name="greeting",
            arguments={"name": "MCP Client"}
        )
        logger.info(f"Greeting prompt: {prompt}")
        
        # Read a resource
        logger.info("Reading hello resource...")
        content, mime_type = await client.read_resource(
            server_url=server_url,
            server_agent_id=server_agent_id,
            resource_id="hello/MCP"
        )
        logger.info(f"Resource content: {content} ({mime_type})")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.exception(e)  # Print full traceback for debugging
    finally:
        # Clean up resources
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 