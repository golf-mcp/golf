import os
import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from authed.sdk import Authed
from fastapi import FastAPI
from authed.sdk.decorators.incoming.fastapi import verify_fastapi
from op_client import OnePasswordClient
from dotenv import load_dotenv
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.responses import Response as StarletteResponse
from starlette.routing import Route
from starlette.middleware import Middleware
# Import our new Authed-MCP middleware
from authed_mcp import AuthedMiddleware
import uvicorn
import json

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check for required environment variables
required_env_vars = [
    "AUTHED_REGISTRY_URL", 
    "AUTHED_AGENT_ID",
    "AUTHED_AGENT_SECRET",
    "OP_SERVICE_ACCOUNT_TOKEN"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these environment variables before running the server")
    import sys
    sys.exit(1)

# Initialize the Authed SDK
logger.info("Initializing Authed SDK...")
authed = Authed.initialize(
    registry_url=os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev"),
    agent_id=os.getenv("AUTHED_AGENT_ID"),
    agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
    private_key=os.getenv("AUTHED_PRIVATE_KEY"),
    public_key=os.getenv("AUTHED_PUBLIC_KEY")
)

# We're now using the middleware from authed-mcp package instead of defining our own

try:
    # Initialize FastMCP server
    logger.info("Initializing FastMCP server...")
    mcp = FastMCP("op-service")
    
    # Initialize the 1Password client
    logger.info("Initializing 1Password client...")
    op_client = OnePasswordClient()
    
    @mcp.tool()
    async def onepassword_list_vaults() -> List[Dict[str, str]]:
        """List all available 1Password vaults"""
        logger.info("Tool called: onepassword_list_vaults")
        return await op_client.list_vaults()
    
    @mcp.tool()
    async def onepassword_list_items(vault_id: str) -> List[Dict[str, str]]:
        """List all items in a 1Password vault"""
        logger.info(f"Tool called: onepassword_list_items(vault_id={vault_id})")
        return await op_client.list_items(vault_id)
    
    @mcp.tool()
    async def onepassword_get_secret(vault_id: str, item_id: str, field_name: Optional[str] = "credential") -> Any:
        """Get a secret from 1Password"""
        logger.info(f"Tool called: onepassword_get_secret(vault_id={vault_id}, item_id={item_id}, field_name={field_name})")
        return await op_client.get_secret(vault_id, item_id, field_name)
    
    # Get the underlying MCP server
    logger.info("Setting up MCP server...")
    mcp_server = mcp._mcp_server
    
    # Create a function to set up the Starlette app with SSE transport
    def create_app(debug: bool = False) -> Starlette:
        """Create a Starlette application with SSE transport and Authed protection."""
        # Create the SSE transport
        transport = SseServerTransport(mcp_server)
        
        # Set up the middleware with our imported AuthedMiddleware
        middleware = [
            Middleware(
                AuthedMiddleware,
                authed=authed,
                require_auth=True,
                debug=debug
            )
        ]
        
        # Create a simple health check endpoint
        async def health_check(request):
            return StarletteResponse(
                content=json.dumps({"status": "ok", "service": "op-service"}),
                media_type="application/json"
            )
        
        # Create the routes
        routes = [
            Route("/health", health_check),
            Route("/sse", transport.handle_request),
        ]
        
        # Create the app
        app = Starlette(
            debug=debug,
            middleware=middleware,
            routes=routes
        )
        
        return app
    
    # Create and run the app
    if __name__ == "__main__":
        # Create the app
        app = create_app(debug=True)
        
        # Get port from environment
        port = int(os.getenv("PORT", "8000"))
        
        # Run the app
        uvicorn.run(app, host="0.0.0.0", port=port)
        
except Exception as e:
    logger.error(f"Error initializing server: {str(e)}")
    raise
   