"""
Example MCP Server with Authed Authentication

This example demonstrates how to:
1. Create an MCP server with Authed authentication
2. Set up SSE endpoints for bidirectional communication
3. Register and expose tools to authenticated clients
4. Handle both GET (SSE) and POST (message) requests securely

Usage:
    1. Copy .env.example to .env and fill in your Authed credentials
    2. Run the server: python simple_mcp_server.py
    3. The server will start on http://localhost:8000 by default

Security Notes:
    - Always use HTTPS in production
    - Keep your agent secrets secure
    - Make sure your agent ID is different from your clients
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any
from dotenv import load_dotenv

from authed.sdk import Authed
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.responses import Response as StarletteResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from authed_mcp.server import AuthedMiddleware

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMCPServer:
    def __init__(self):
        # Initialize Authed SDK with credentials from environment
        self.authed = Authed.initialize(
            registry_url=os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev"),
            agent_id=os.getenv("AUTHED_AGENT_ID"),
            agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
            private_key=os.getenv("AUTHED_PRIVATE_KEY"),
            public_key=os.getenv("AUTHED_PUBLIC_KEY")
        )
        
        # Initialize FastMCP server with a service name
        self.mcp = FastMCP("example-service")
        self.register_tools()
    
    def register_tools(self):
        """Register MCP tools that will be available to authenticated clients."""
        
        @self.mcp.tool()
        async def echo(message: str) -> Dict[str, Any]:
            """Simple echo tool for testing the connection."""
            logger.info(f"Echo tool called with message: {message}")
            return {"message": message}
        
        @self.mcp.tool()
        async def add_numbers(a: float, b: float) -> Dict[str, Any]:
            """Add two numbers together - example of a typed tool."""
            logger.info(f"Adding numbers: {a} + {b}")
            result = a + b
            return {"result": result}
    
    def create_app(self, debug: bool = False) -> Starlette:
        """Create a Starlette application with SSE transport and Authed protection.
        
        This sets up:
        1. SSE endpoint for client connections
        2. Message endpoint for client-to-server communication
        3. Authed authentication middleware
        4. Health check endpoint
        """
        # Create SSE transport for bidirectional communication
        sse = SseServerTransport("/messages/")
        
        # Create a handler for SSE connections
        async def handle_sse(request):
            """Handle incoming SSE connections from clients."""
            logger.info(f"SSE connection request from: {request.client}")
            
            async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,
            ) as (read_stream, write_stream):
                await self.mcp._mcp_server.run(
                    read_stream,
                    write_stream,
                    self.mcp._mcp_server.create_initialization_options(),
                )
        
        # Set up middleware with Authed authentication
        middleware = [
            Middleware(
                AuthedMiddleware,
                authed=self.authed,
                require_auth=True,  # Require authentication for all requests, setting this to False will allow unauthenticated requests
                debug=True
            )
        ]
        
        # Create a simple health check endpoint
        async def health_check(request):
            """Health check endpoint to verify server is running."""
            return StarletteResponse(
                content='{"status": "ok"}',
                media_type="application/json"
            )
        
        # Create the routes
        routes = [
            Route("/health", health_check),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
        
        # Create the app
        app = Starlette(
            debug=debug,
            middleware=middleware,
            routes=routes
        )
        
        return app

async def main():
    """Run the MCP server."""
    try:
        # Create server instance
        server = SimpleMCPServer()
        
        # Create the app
        app = server.create_app(debug=True)
        
        # Import uvicorn here to avoid potential import issues
        import uvicorn
        
        # Get port from environment or use default
        port = int(os.getenv("PORT", "8000"))
        
        # Run the server
        logger.info(f"Starting server on port {port}")
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 