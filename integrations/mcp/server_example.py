"""
Example MCP server with Authed authentication.

This example demonstrates how to create an MCP server with Authed authentication.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from adapter import AuthedMCPServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the example MCP server."""
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
    if not all([agent_id, agent_secret, private_key, public_key]):
        logger.error("Missing required Authed credentials")
        logger.info("Please set the following environment variables:")
        logger.info("  AUTHED_REGISTRY_URL - URL of the Authed registry")
        logger.info("  AGENT_ID - ID of the agent")
        logger.info("  AGENT_SECRET - Secret of the agent")
        logger.info("  AGENT_PRIVATE_KEY - Private key of the agent")
        logger.info("  AGENT_PUBLIC_KEY - Public key of the agent")
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
    
    # Run the server
    logger.info("Starting MCP server...")
    await server.run()

if __name__ == "__main__":
    asyncio.run(main()) 