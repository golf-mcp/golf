"""
Script to run the MCP server independently with SSE transport.
"""

import json
import logging
import os
import pathlib
import sys
import argparse
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport
from mcp.server import Server

from adapter import AuthedMCPServer

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set Authed SDK logger to DEBUG
logging.getLogger('client.sdk').setLevel(logging.DEBUG)
logging.getLogger('client.sdk.auth').setLevel(logging.DEBUG)

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        # Log the incoming request
        logger.info(f"Received SSE connection request from {request.client.host}")
        logger.debug(f"Request headers: {request.headers}")
        
        # Check for authentication headers
        auth_header = request.headers.get("Authorization")
        if auth_header:
            logger.info(f"Request includes Authorization header: {auth_header[:15]}...")
        else:
            logger.warning("Request does not include Authorization header")
        
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            logger.info("SSE connection established, running MCP server")
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

def main():
    """Run the MCP server."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to listen on')
    args = parser.parse_args()
    
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
    logger.info("Creating AuthedMCPServer...")
    server = AuthedMCPServer(
        name="example-server",
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    logger.info("AuthedMCPServer created successfully")
    
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
    
    # Get the internal MCP server
    mcp_server = server.mcp._mcp_server  # Access the internal server
    
    # Create a Starlette app with SSE transport
    logger.info("Creating Starlette app with SSE transport...")
    starlette_app = create_starlette_app(mcp_server, debug=True)
    
    # Run the server
    logger.info(f"Starting MCP server on {args.host}:{args.port}...")
    uvicorn.run(starlette_app, host=args.host, port=args.port, log_level="debug")

if __name__ == "__main__":
    main()
