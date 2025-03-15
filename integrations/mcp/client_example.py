"""
Example MCP client with Authed authentication.

This example demonstrates how to create an MCP client with Authed authentication.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from client.sdk import Authed
from integrations.mcp import AuthedMCPClient, grant_mcp_access

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the example MCP client."""
    # Load environment variables
    load_dotenv()
    
    # Load server environment variables
    server_env_file = ".env.mcp_server.example-server"
    if os.path.exists(server_env_file):
        with open(server_env_file, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
    
    # Initialize Authed client
    authed = Authed(
        api_key=os.getenv("AUTHED_API_KEY"),
        api_url=os.getenv("AUTHED_API_URL", "https://api.authed.ai")
    )
    
    # Create MCP client with Authed authentication
    client = AuthedMCPClient(authed)
    
    # Register client as an agent if needed
    client_agent_id = os.getenv("MCP_CLIENT_AGENT_ID")
    if not client_agent_id:
        # Generate key pair
        private_key, public_key = authed.generate_key_pair()
        
        # Register client as an agent
        client_agent = await authed.register_agent(
            name="Example MCP Client",
            description="A simple MCP client with Authed authentication",
            public_key=public_key,
            metadata='{"type": "mcp_client"}'
        )
        
        client_agent_id = client_agent.id
        
        # Save client credentials to .env file for future use
        with open(".env.mcp_client", "w") as f:
            f.write(f"MCP_CLIENT_AGENT_ID={client_agent_id}\n")
            f.write(f"MCP_CLIENT_PRIVATE_KEY={private_key}\n")
            f.write(f"MCP_CLIENT_PUBLIC_KEY={public_key}\n")
        
        logger.info(f"Registered MCP client with Authed: {client_agent_id}")
    
    # Get server agent ID
    server_agent_id = os.getenv("MCP_SERVER_AGENT_ID")
    if not server_agent_id:
        logger.error("Server agent ID not found. Please run the server example first.")
        return
    
    # Grant client access to server if needed
    logger.info(f"Granting client {client_agent_id} access to server {server_agent_id}...")
    granted = await grant_mcp_access(
        authed=authed,
        client_agent_id=client_agent_id,
        server_agent_id=server_agent_id
    )
    
    if granted:
        logger.info("Access granted successfully.")
    else:
        logger.warning("Failed to grant access or access already granted.")
    
    # Define server URL
    server_url = "http://localhost:8000"
    
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