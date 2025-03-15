"""
Example MCP server with Authed authentication.

This example demonstrates how to create an MCP server with Authed authentication.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from client.sdk import Authed
from integrations.mcp import AuthedMCPServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the example MCP server."""
    # Load environment variables
    load_dotenv()
    
    # Initialize Authed client
    authed = Authed(
        api_key=os.getenv("AUTHED_API_KEY"),
        base_url=os.getenv("AUTHED_API_URL", "https://api.getauthed.dev")
    )
    
    # Create MCP server with Authed authentication
    server = AuthedMCPServer("example-server", authed)
    
    # Register a resource handler
    @server.resource("/hello/{name}")
    async def hello_resource(name: str):
        # Get the agent_id from the request state
        from starlette.requests import Request
        request = Request.scope.get("request")
        agent_id = request.state.agent_id if request else "unknown"
        
        logger.info(f"Resource request from agent: {agent_id}")
        return f"Hello, {name}! You are authenticated as agent {agent_id}.", "text/plain"
    
    # Register a tool handler
    @server.tool("echo")
    async def echo_tool(message: str):
        # Get the agent_id from the request state
        from starlette.requests import Request
        request = Request.scope.get("request")
        agent_id = request.state.agent_id if request else "unknown"
        
        logger.info(f"Tool request from agent: {agent_id}")
        return {"message": message, "from_agent": agent_id}
    
    # Register a prompt handler
    @server.prompt("greeting")
    async def greeting_prompt(name: str = "World"):
        # Get the agent_id from the request state
        from starlette.requests import Request
        request = Request.scope.get("request")
        agent_id = request.state.agent_id if request else "unknown"
        
        logger.info(f"Prompt request from agent: {agent_id}")
        return f"Hello, {name}! Welcome to the MCP server. You are authenticated as agent {agent_id}."
    
    # Run the server
    logger.info("Starting MCP server...")
    await server.run(host="localhost", port=8000)

if __name__ == "__main__":
    asyncio.run(main()) 