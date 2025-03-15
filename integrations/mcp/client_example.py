"""
Example MCP client with Authed authentication.

This example demonstrates how to create an MCP client with Authed authentication.
"""

import asyncio
import logging
import os
import json
from dotenv import load_dotenv

from integrations.mcp import AuthedMCPClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the example MCP client."""
    # Load environment variables
    load_dotenv()
    
    # Get Authed credentials
    registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
    agent_id = os.getenv("AGENT_ID")
    agent_secret = os.getenv("AGENT_SECRET")
    
    # Load keys from environment or files
    private_key = os.getenv("AGENT_PRIVATE_KEY")
    public_key = os.getenv("AGENT_PUBLIC_KEY")
    
    # If keys are not in environment, try to load from files
    if not private_key and os.path.exists("private_key.pem"):
        with open("private_key.pem", "r") as f:
            private_key = f.read()
    
    if not public_key and os.path.exists("public_key.pem"):
        with open("public_key.pem", "r") as f:
            public_key = f.read()
    
    # Check if we have all required credentials
    if not all([agent_id, agent_secret, private_key]):
        logger.error("Missing required Authed credentials")
        logger.info("Please set the following environment variables:")
        logger.info("  AUTHED_REGISTRY_URL - URL of the Authed registry")
        logger.info("  AGENT_ID - ID of the agent")
        logger.info("  AGENT_SECRET - Secret of the agent")
        logger.info("  AGENT_PRIVATE_KEY - Private key of the agent")
        return
    
    # Create MCP client with Authed authentication
    client = AuthedMCPClient(
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    
    # Get server agent ID
    server_agent_id = os.getenv("MCP_SERVER_AGENT_ID")
    if not server_agent_id:
        logger.error("Server agent ID not found. Please set MCP_SERVER_AGENT_ID environment variable.")
        return
    
    # Define server URL
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
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
            resource_id="/hello/MCP"
        )
        logger.info(f"Resource content: {content} ({mime_type})")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 