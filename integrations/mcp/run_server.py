"""
Script to run the MCP server independently with SSE transport.
"""

import json
import logging
import os
import pathlib
import argparse
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport
from mcp.server import Server
from starlette.responses import JSONResponse
import httpx

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

def create_starlette_app(mcp_server: Server, authed_auth, *, debug: bool = False) -> Starlette:
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
            
            # Verify the token
            if auth_header.startswith("Bearer "):
                try:
                    # Verify the token using Authed
                    logger.info("Verifying token with Authed...")
                    
                    # Extract token from Authorization header
                    token = auth_header.replace("Bearer ", "")
                    
                    # Extract DPoP proof from headers
                    dpop_header = None
                    for header_name, header_value in request.headers.items():
                        if header_name.lower() == "dpop":
                            dpop_header = header_value
                            break
                    
                    if not dpop_header:
                        logger.warning("Missing DPoP proof header")
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "Authentication failed - missing DPoP proof header"}
                        )
                    
                    # Call registry's verify endpoint directly
                    verify_url = f"{authed_auth.registry_url}/tokens/verify"
                    
                    # Log the DPoP header for debugging
                    logger.debug(f"DPoP header: {dpop_header[:50]}...")
                    
                    # Parse the DPoP header to check the public key format
                    try:
                        import jwt
                        dpop_header_data = jwt.get_unverified_header(dpop_header)
                        logger.debug(f"DPoP header data: {dpop_header_data}")
                        
                        # Check if jwk is present
                        if 'jwk' not in dpop_header_data:
                            logger.error("Missing jwk in DPoP header")
                            return JSONResponse(
                                status_code=401,
                                content={"detail": "Authentication failed - missing jwk in DPoP header"}
                            )
                    except Exception as e:
                        logger.error(f"Error parsing DPoP header: {str(e)}")
                    
                    async with httpx.AsyncClient(
                        base_url=authed_auth.registry_url,
                        follow_redirects=False
                    ) as client:
                        try:
                            # Import the DPoP handler
                            from client.sdk.auth.dpop import DPoPHandler
                            
                            # Create a new DPoP proof specifically for the verification request
                            verify_url = f"{authed_auth.registry_url}/tokens/verify"
                            dpop_handler = DPoPHandler()
                            verification_proof = dpop_handler.create_proof(
                                "POST",  # Verification endpoint uses POST
                                verify_url,  # Use the verification endpoint URL
                                authed_auth._private_key
                            )
                            
                            logger.debug(f"Created new DPoP proof for verification: {verification_proof[:50]}...")
                            
                            # Set up verification headers
                            verify_headers = {
                                "authorization": f"Bearer {token}",
                                "dpop": verification_proof  # Use the new proof for verification
                            }
                            
                            logger.debug(f"Verify request headers keys: {verify_headers.keys()}")
                        except Exception as e:
                            logger.error(f"Error creating DPoP proof: {str(e)}")
                            # Fall back to the original DPoP proof if creation fails
                            verify_headers = {
                                "authorization": f"Bearer {token}",
                                "dpop": dpop_header
                            }
                        
                        # Send verification request
                        response = await client.post(
                            "/tokens/verify",
                            headers=verify_headers
                        )
                        
                        if response.status_code == 200:
                            logger.info("Token verified successfully")
                        else:
                            logger.warning(f"Token verification failed: {response.text}")
                            return JSONResponse(
                                status_code=401,
                                content={"detail": f"Authentication failed: {response.text}"}
                            )
                except Exception as e:
                    logger.error(f"Token verification failed: {str(e)}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": f"Authentication failed: {str(e)}"}
                    )
            else:
                logger.warning("No Bearer token found in Authorization header")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication failed - no Bearer token"}
                )
        else:
            logger.warning("No Authorization header found")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        # If authentication is successful, proceed with the connection
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
    
    # Create a Starlette app with SSE transport and authentication
    starlette_app = create_starlette_app(
        mcp_server, 
        server.authed.auth,  # Pass the auth handler
        debug=True
    )
    
    # Run the server
    logger.info(f"Starting MCP server on {args.host}:{args.port}...")
    uvicorn.run(starlette_app, host=args.host, port=args.port, log_level="debug")

if __name__ == "__main__":
    main()
