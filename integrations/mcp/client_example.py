"""
Example MCP client with Authed authentication.

This example demonstrates how to create an MCP client with Authed authentication.
"""

import asyncio
import json
import logging
import os
import pathlib

from adapter import AuthedMCPClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    client = AuthedMCPClient(
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    
    # Define server command and args
    server_command = "python"
    
    # Get the absolute path to the server_example.py file
    server_script = str(pathlib.Path(__file__).parent / "server_example.py")
    server_args = [server_script]
    
    try:
        # List resources
        logger.info("Listing resources...")
        resources = await client.list_resources(server_command, server_args, server_agent_id)
        logger.info(f"Resources: {resources}")
        
        # List tools
        logger.info("Listing tools...")
        tools = await client.list_tools(server_command, server_args, server_agent_id)
        logger.info(f"Tools: {tools}")
        
        # List prompts
        logger.info("Listing prompts...")
        prompts = await client.list_prompts(server_command, server_args, server_agent_id)
        logger.info(f"Prompts: {prompts}")
        
        # Call a tool
        logger.info("Calling echo tool...")
        result = await client.call_tool(
            server_command=server_command,
            server_args=server_args,
            server_agent_id=server_agent_id,
            tool_name="echo",
            arguments={"message": "Hello from MCP client!"}
        )
        logger.info(f"Echo result: {result}")
        
        # Get a prompt
        logger.info("Getting greeting prompt...")
        prompt = await client.get_prompt(
            server_command=server_command,
            server_args=server_args,
            server_agent_id=server_agent_id,
            prompt_name="greeting",
            arguments={"name": "MCP Client"}
        )
        logger.info(f"Greeting prompt: {prompt}")
        
        # Read a resource
        logger.info("Reading hello resource...")
        content, mime_type = await client.read_resource(
            server_command=server_command,
            server_args=server_args,
            server_agent_id=server_agent_id,
            resource_id="hello/MCP"
        )
        logger.info(f"Resource content: {content} ({mime_type})")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.exception(e)  # Print full traceback for debugging

if __name__ == "__main__":
    asyncio.run(main()) 