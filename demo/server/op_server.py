import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from mcp.server.fastmcp import FastMCP
from authed.sdk import Authed
from fastapi import FastAPI
from authed.sdk.decorators.incoming.fastapi import verify_fastapi
from op_client import OnePasswordClient
from dotenv import load_dotenv
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from starlette.routing import Mount, Route
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import json
import base64

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

# Create a custom middleware for Authed authentication
class AuthedAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that verifies Authed authentication for all requests using SDK."""
    
    async def dispatch(self, request: StarletteRequest, call_next: Callable) -> StarletteResponse:
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Skip auth for SSE and messages endpoints
        # This is critical for SSE connections to work properly
        skip_auth_paths = ["/health", "/sse", "/messages/"]
        if any(skip_path in request.url.path for skip_path in skip_auth_paths):
            logger.info(f"Bypassing authentication for SSE endpoint: {request.url.path}")
            return await call_next(request)
            
        logger.debug(f"Verifying request to {request.url.path}")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Request URL: {request.url}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("Request missing Authorization header")
            return StarletteResponse(
                content=json.dumps({"error": "Unauthorized - Missing Authorization header"}),
                status_code=401,
                headers={"Content-Type": "application/json"}
            )
        
        # Get auth handler from Authed SDK
        auth_handler = authed.auth
        
        try:
            # Use the SDK's verify_request method - this is the proper way to verify
            # a request using the Authed SDK, exactly as in the fastapi.py decorator
            is_valid = await auth_handler.verify_request(
                request.method,
                str(request.url),
                dict(request.headers)
            )
            
            if not is_valid:
                logger.error("Request verification failed")
                return StarletteResponse(
                    content=json.dumps({"error": "Unauthorized - Invalid authentication"}),
                    status_code=401,
                    headers={"Content-Type": "application/json"}
                )
            
            # Add auth info to request state
            request.state.authenticated = True
            logger.info(f"Authentication successful for {request.url.path}")
            
            # Call the next middleware or endpoint
            return await call_next(request)
            
        except Exception as e:
            # Handle authentication errors
            logger.error(f"Authentication error: {str(e)}")
            return StarletteResponse(
                content=json.dumps({"error": f"Authentication failed: {str(e)}"}),
                status_code=401,
                headers={"Content-Type": "application/json"}
            )

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
    async def onepassword_get_secret(vault_id: str, item_id: str, field_name: Optional[str] = None) -> Any:
        """Get a secret from 1Password"""
        logger.info(f"Tool called: onepassword_get_secret(vault_id={vault_id}, item_id={item_id}, field_name={field_name})")
        return await op_client.get_secret(vault_id, item_id, field_name)
    
    # Get the underlying MCP server
    logger.info("Setting up MCP server...")
    mcp_server = mcp._mcp_server
    
    # Create a function to set up the Starlette app with SSE transport
    def create_app(debug: bool = False) -> Starlette:
        """Create a Starlette application with SSE transport and Authed protection."""
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request: StarletteRequest) -> None:
            # This is where SSE connections are handled
            logger.info(f"SSE connection request from: {request.client}")
            
            async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # type: ignore
            ) as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        
        # Set up middleware with Authed authentication
        middleware = [
            Middleware(AuthedAuthMiddleware),
        ]
        
        # Create the app with the proper routes and middleware
        app = Starlette(
            debug=debug,
            middleware=middleware,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        
        return app
    
    # Create a FastAPI app with Authed protection for REST endpoints
    fastapi_app = FastAPI()
    
    @fastapi_app.get("/health")
    async def health_check():
        """A simple health check endpoint."""
        return {"status": "ok", "message": "1Password MCP server is running"}
    
    @fastapi_app.get("/auth-check")
    @verify_fastapi
    async def auth_check():
        """A protected endpoint to verify Authed authentication."""
        return {"status": "ok", "message": "Authentication successful"}
    
except Exception as e:
    logger.error(f"Error during initialization: {str(e)}")
    import sys
    sys.exit(1)

if __name__ == "__main__":
    try:
        # Connect to 1Password
        logger.info("Connecting to 1Password...")
        asyncio.run(op_client.connect())
        logger.info("Successfully connected to 1Password")
        
        # Create the Starlette app with Authed protection
        logger.info("Creating Starlette app with Authed authentication...")
        app = create_app(debug=True)
        
        # Run the server
        logger.info("Starting the server...")
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error running the server: {str(e)}")
        import sys
        sys.exit(1)
   