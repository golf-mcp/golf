"""
Authed MCP Server CLI

A command-line tool for running MCP servers with Authed authentication.
"""

import argparse
import logging
import os
from typing import Any, Optional, Callable, Awaitable, Tuple
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
from mcp.server.sse import SseServerTransport
from mcp.server import Server
import httpx
from authed.sdk.auth.dpop import DPoPHandler

from .adapter import AuthedMCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    if verbose:
        logging.getLogger('authed.sdk').setLevel(logging.DEBUG)
        logging.getLogger('authed.sdk.auth').setLevel(logging.DEBUG)
    else:
        logging.getLogger('authed.sdk').setLevel(logging.INFO)
        logging.getLogger('authed.sdk.auth').setLevel(logging.INFO)


def create_server(registry_url: Optional[str] = None,
                 agent_id: Optional[str] = None,
                 agent_secret: Optional[str] = None,
                 private_key: Optional[str] = None,
                 public_key: Optional[str] = None,
                 name: str = "mcp-server") -> AuthedMCPServer:
    """
    Create an MCP server with Authed authentication.
    
    Args:
        registry_url: URL of the Authed registry
        agent_id: ID of the agent
        agent_secret: Secret of the agent
        private_key: Private key of the agent
        public_key: Public key of the agent
        name: Name of the MCP server
        
    Returns:
        AuthedMCPServer: Initialized server
    """
    # Use parameters if provided, otherwise fall back to environment variables
    registry_url = registry_url or os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
    agent_id = agent_id or os.getenv("AUTHED_AGENT_ID")
    agent_secret = agent_secret or os.getenv("AUTHED_AGENT_SECRET")
    private_key = private_key or os.getenv("AUTHED_PRIVATE_KEY")
    public_key = public_key or os.getenv("AUTHED_PUBLIC_KEY")
    
    # Validate required parameters
    if not all([agent_id, agent_secret, private_key]):
        raise ValueError(
            "Missing required credentials. Provide them as parameters or "
            "set AUTHED_AGENT_ID, AUTHED_AGENT_SECRET, and AUTHED_PRIVATE_KEY "
            "environment variables."
        )
    
    # Create MCP server with Authed authentication
    logger.debug(f"Creating AuthedMCPServer with name: {name}")
    server = AuthedMCPServer(
        name=name,
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    logger.debug("AuthedMCPServer created successfully")
    
    return server


def create_starlette_app(mcp_server: Server, authed_auth, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """Handle SSE connections with Authed authentication."""
        # Log the incoming request
        logger.info(f"Received SSE connection request from {request.client.host}")
        
        # Check for authentication headers
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("No Authorization header found")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
            
        # Verify the token
        if not auth_header.startswith("Bearer "):
            logger.warning("No Bearer token found in Authorization header")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed - no Bearer token"}
            )
            
        # Extract token from Authorization header
        token = auth_header.replace("Bearer ", "")
        
        # Extract DPoP proof from headers
        dpop_header = request.headers.get("dpop")
        if not dpop_header:
            logger.warning("Missing DPoP proof header")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed - missing DPoP proof header"}
            )
        
        try:
            # Create a new DPoP proof specifically for the verification request
            verify_url = f"{authed_auth.registry_url}/tokens/verify"
            dpop_handler = DPoPHandler()
            verification_proof = dpop_handler.create_proof(
                "POST",  # Verification endpoint uses POST
                verify_url,  # Use the verification endpoint URL
                authed_auth._private_key
            )
            
            # Set up verification headers
            verify_headers = {
                "authorization": f"Bearer {token}",
                "dpop": verification_proof,  # Use the new proof for verification
                "original-method": request.method  # Include original method
            }
            
            # Verify the token using standalone httpx client instead of authed_auth.client
            async with httpx.AsyncClient(base_url=authed_auth.registry_url) as client:
                response = await client.post(
                    "/tokens/verify",
                    headers=verify_headers,
                    json={"token": token}
                )
                
                if response.status_code != 200:
                    logger.warning(f"Token verification failed: {response.text}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": f"Authentication failed: {response.text}"}
                    )
                logger.info("Token verified successfully")
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Authentication failed: {str(e)}"}
            )
        
        # If authentication is successful, proceed with the connection
        try:
            async with sse.connect_sse(
                    request.scope,
                    request.receive,
                    request._send,  # noqa: SLF001
            ) as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        except Exception as e:
            logger.error(f"Error handling SSE connection: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Server error: {str(e)}"}
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


def run_server(server: AuthedMCPServer, host: str = "0.0.0.0", port: int = 8000, debug: bool = False) -> None:
    """
    Run the MCP server with Starlette and Uvicorn.
    
    Args:
        server: The AuthedMCPServer instance
        host: Host to bind to
        port: Port to listen on
        debug: Whether to enable debug mode
    """
    # Get the internal MCP server
    mcp_server = server.mcp._mcp_server
    
    # Create a Starlette app with SSE transport and authentication
    starlette_app = create_starlette_app(
        mcp_server, 
        server.authed.auth,
        debug=debug
    )
    
    # Run the server
    logger.info(f"Starting MCP server '{server.name}' on {host}:{port}...")
    uvicorn.run(starlette_app, host=host, port=port, log_level="debug" if debug else "info")


class McpServerBuilder:
    """Builder class for creating and configuring an MCP server."""
    
    def __init__(self, name: str = "mcp-server"):
        """Initialize the server builder with a name."""
        self.name = name
        self.resources = []
        self.tools = []
        self.prompts = []
        
    def add_resource(self, path: str, handler: Callable[[Any], Awaitable[Tuple[Any, str]]]) -> 'McpServerBuilder':
        """
        Add a resource handler to the server.
        
        Args:
            path: Resource path pattern
            handler: Async resource handler function
            
        Returns:
            McpServerBuilder: self for chaining
        """
        self.resources.append((path, handler))
        return self
        
    def add_tool(self, name: str, handler: Callable[[Any], Awaitable[Any]]) -> 'McpServerBuilder':
        """
        Add a tool handler to the server.
        
        Args:
            name: Tool name
            handler: Async tool handler function
            
        Returns:
            McpServerBuilder: self for chaining
        """
        self.tools.append((name, handler))
        return self
        
    def add_prompt(self, name: str, handler: Callable[[Any], Awaitable[str]]) -> 'McpServerBuilder':
        """
        Add a prompt handler to the server.
        
        Args:
            name: Prompt name
            handler: Async prompt handler function
            
        Returns:
            McpServerBuilder: self for chaining
        """
        self.prompts.append((name, handler))
        return self
        
    def build(self) -> AuthedMCPServer:
        """
        Build and configure the server.
        
        Returns:
            AuthedMCPServer: Configured server
        """
        # Create the server
        server = create_server(name=self.name)
        
        # Register resources
        for path, handler in self.resources:
            server.resource(path)(handler)
            
        # Register tools
        for name, handler in self.tools:
            server.tool(name)(handler)
            
        # Register prompts
        for name, handler in self.prompts:
            server.prompt(name)(handler)
            
        return server


def register_default_handlers(server: AuthedMCPServer) -> None:
    """
    Register default handlers for the server (for demo purposes).
    
    Args:
        server: The AuthedMCPServer instance
    """
    # Register a default resource handler
    @server.resource("hello/{name}")
    async def hello_resource(name: str):
        logger.info(f"Resource request for name: {name}")
        return f"Hello, {name}!", "text/plain"
    
    # Register a default tool handler
    @server.tool("echo")
    async def echo_tool(message: str):
        logger.info(f"Tool request with message: {message}")
        return {"message": message}
    
    # Register a default prompt handler
    @server.prompt("greeting")
    async def greeting_prompt(name: str = "World"):
        logger.info(f"Prompt request for name: {name}")
        return f"Hello, {name}! Welcome to the MCP server."


def main() -> None:
    """Run the MCP server CLI."""
    parser = argparse.ArgumentParser(description="Authed MCP Server CLI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--name", default="mcp-server", help="Name of the MCP server")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--demo", action="store_true", help="Register demo handlers")
    parser.add_argument("--registry-url", help="URL of the Authed registry")
    parser.add_argument("--agent-id", help="ID of the agent")
    parser.add_argument("--agent-secret", help="Secret of the agent")
    parser.add_argument("--private-key", help="Private key of the agent")
    parser.add_argument("--public-key", help="Public key of the agent")
    
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(args.verbose)
    
    try:
        # Create the server
        server = create_server(
            registry_url=args.registry_url,
            agent_id=args.agent_id,
            agent_secret=args.agent_secret,
            private_key=args.private_key,
            public_key=args.public_key,
            name=args.name
        )
        
        # Register demo handlers if requested
        if args.demo:
            logger.info("Registering demo handlers...")
            register_default_handlers(server)
        
        # Run the server
        run_server(
            server,
            host=args.host,
            port=args.port,
            debug=args.verbose
        )
    except ValueError as e:
        logger.error(str(e))
        parser.print_help()
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        if args.verbose:
            logger.exception(e)


if __name__ == "__main__":
    main() 