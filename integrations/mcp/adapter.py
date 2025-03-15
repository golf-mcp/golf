"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
import httpx
from typing import Any, Dict, Optional, Union, List
from uuid import UUID

# Import Authed SDK
from client.sdk import Authed
from client.sdk.exceptions import AuthenticationError

# Import MCP SDK
from mcp.server import FastMCP
from mcp.types import Resource, Tool, Prompt
from mcp import ClientSession

# Import FastAPI/Starlette components for middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Configure logging
logger = logging.getLogger(__name__)

class AuthedMCPServerMiddleware(BaseHTTPMiddleware):
    """
    Middleware for MCP servers to use Authed for authentication.
    
    This middleware sits between MCP clients and servers, verifying Authed tokens
    before forwarding requests to the MCP server.
    """
    
    def __init__(self, app, authed_auth):
        """
        Initialize the middleware with an Authed auth handler.
        
        Args:
            app: The FastAPI/Starlette app
            authed_auth: Initialized Authed auth handler
        """
        super().__init__(app)
        self.authed_auth = authed_auth
    
    async def authenticate_request(self, request: Request) -> Optional[str]:
        """
        Authenticate a request using Authed.
        
        Args:
            request: The request to authenticate
            
        Returns:
            Agent ID if authentication is successful, None otherwise
        """
        try:
            # Get the request method and URL
            method = request.method
            url = str(request.url)
            
            # Verify the request using Authed
            result = await self.authed_auth.verify_request(
                method=method,
                url=url,
                headers=dict(request.headers)
            )
            
            # If verification is successful, extract the agent ID from the token
            if result:
                # The agent ID should be available in the token claims
                # This is a simplified implementation - in a real scenario,
                # you would extract the agent ID from the token claims
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "")
                    # In a real implementation, you would decode the token
                    # and extract the agent ID from the claims
                    # For now, we'll use a placeholder
                    return "agent_id_from_token"
                
            return None
        except AuthenticationError as e:
            logger.warning(f"Authentication error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {str(e)}")
            return None
    
    async def dispatch(self, request: Request, call_next):
        """
        Process a request with authentication.
        
        Args:
            request: The request to process
            call_next: Function to call next in the middleware chain
            
        Returns:
            Response
        """
        # Authenticate the request
        agent_id = await self.authenticate_request(request)
        if not agent_id:
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 401,
                        "message": "Authentication failed"
                    },
                    "id": None
                }
            )
        
        # Add agent_id to request state
        request.state.agent_id = agent_id
        
        # Call next middleware
        return await call_next(request)


class AuthedMCPServer:
    """
    MCP server with Authed authentication.
    
    This class wraps an MCP server with Authed authentication.
    """
    
    def __init__(self, name: str, registry_url: str, agent_id: str, agent_secret: str, private_key: str, public_key: str):
        """
        Initialize the server with Authed credentials.
        
        Args:
            name: Name of the MCP server
            registry_url: URL of the Authed registry
            agent_id: ID of the agent
            agent_secret: Secret of the agent
            private_key: Private key of the agent
            public_key: Public key of the agent
        """
        self.name = name
        
        # Initialize Authed SDK
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        
        # Create MCP server
        self.mcp = FastMCP(name)
        
        # Add authentication middleware to the FastAPI app
        self.mcp.app.add_middleware(AuthedMCPServerMiddleware, authed_auth=self.authed.auth)
    
    def resource(self, path: str = None):
        """
        Register a resource handler.
        
        Args:
            path: Resource path pattern
            
        Returns:
            Decorator function
        """
        return self.mcp.resource(path)
    
    def tool(self, name: str = None):
        """
        Register a tool handler.
        
        Args:
            name: Tool name
            
        Returns:
            Decorator function
        """
        return self.mcp.tool(name)
    
    def prompt(self, name: str = None):
        """
        Register a prompt handler.
        
        Args:
            name: Prompt name
            
        Returns:
            Decorator function
        """
        return self.mcp.prompt(name)
    
    async def run(self, host: str = "localhost", port: int = 8000):
        """
        Run the MCP server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        # Run the MCP server
        await self.mcp.run(host=host, port=port)


class AuthedMCPClient:
    """
    MCP client with Authed authentication.
    
    This class provides a client for making authenticated requests to MCP servers.
    """
    
    def __init__(self, registry_url: str, agent_id: str, agent_secret: str, private_key: str, public_key: str = None):
        """
        Initialize the client with Authed credentials.
        
        Args:
            registry_url: URL of the Authed registry
            agent_id: ID of the agent
            agent_secret: Secret of the agent
            private_key: Private key of the agent
            public_key: Public key of the agent (optional)
        """
        # Initialize Authed SDK
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        
        self._token_cache = {}  # Simple token cache
    
    async def get_token(self, target_server_id: Union[str, UUID]) -> str:
        """
        Get an interaction token for a target server.
        
        Args:
            target_server_id: ID of the target MCP server
            
        Returns:
            Authentication token
            
        Raises:
            AuthenticationError: If token retrieval fails
        """
        # Check cache first
        cache_key = str(target_server_id)
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        # Get new token
        token = await self.authed.auth.get_interaction_token(target_server_id)
        
        # Cache token
        self._token_cache[cache_key] = token
        
        return token
    
    async def connect(self, server_url: str, server_agent_id: Union[str, UUID]):
        """
        Connect to an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            
        Returns:
            MCP client session
        """
        # Get authentication token
        token = await self.get_token(server_agent_id)
        
        # Create HTTP client with authentication
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a custom transport for the MCP client
        # This is a simplified implementation - adjust based on actual MCP SDK
        async def read():
            async with httpx.AsyncClient(base_url=server_url, headers=headers) as client:
                response = await client.post("/jsonrpc")
                return response.json()
                
        async def write(data):
            async with httpx.AsyncClient(base_url=server_url, headers=headers) as client:
                response = await client.post("/jsonrpc", json=data)
                return response.json()
        
        # Create client session
        session = ClientSession(read, write)
        await session.initialize()
        return session
    
    async def list_resources(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Resource]:
        """
        List resources from an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            
        Returns:
            List of resources
        """
        session = await self.connect(server_url, server_agent_id)
        return await session.list_resources()
    
    async def list_tools(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Tool]:
        """
        List tools from an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            
        Returns:
            List of tools
        """
        session = await self.connect(server_url, server_agent_id)
        return await session.list_tools()
    
    async def list_prompts(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Prompt]:
        """
        List prompts from an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            
        Returns:
            List of prompts
        """
        session = await self.connect(server_url, server_agent_id)
        return await session.list_prompts()
    
    async def read_resource(self, server_url: str, server_agent_id: Union[str, UUID], resource_id: str) -> tuple:
        """
        Read a resource from an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            resource_id: ID of the resource to read
            
        Returns:
            Tuple of (content, mime_type)
        """
        session = await self.connect(server_url, server_agent_id)
        return await session.read_resource(resource_id)
    
    async def call_tool(self, server_url: str, server_agent_id: Union[str, UUID], tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Call a tool on an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            tool_name: Name of the tool to call
            arguments: Arguments for the tool
            
        Returns:
            Tool result
        """
        session = await self.connect(server_url, server_agent_id)
        return await session.call_tool(tool_name, arguments or {})
    
    async def get_prompt(self, server_url: str, server_agent_id: Union[str, UUID], prompt_name: str, arguments: Dict[str, str] = None) -> Any:
        """
        Get a prompt from an MCP server.
        
        Args:
            server_url: URL of the MCP server
            server_agent_id: ID of the MCP server agent
            prompt_name: Name of the prompt to get
            arguments: Arguments for the prompt
            
        Returns:
            Prompt result
        """
        session = await self.connect(server_url, server_agent_id)
        return await session.get_prompt(prompt_name, arguments or {})


async def register_mcp_server(authed: Authed, 
                             name: str, 
                             description: str, 
                             capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Register an MCP server as an agent in Authed.
    
    Args:
        authed: Initialized Authed client
        name: Name of the MCP server
        description: Description of the MCP server
        capabilities: Optional MCP server capabilities
        
    Returns:
        Dictionary with server registration details
    """
    # Generate key pair for the agent
    key_pair = await authed.create_key_pair()
    private_key = key_pair["private_key"]
    public_key = key_pair["public_key"]
    
    # Prepare metadata with MCP capabilities
    metadata = {
        "type": "mcp_server",
        "capabilities": capabilities or {}
    }
    
    # Register server as an agent in Authed
    agent = await authed.register_agent(
        name=name,
        description=description,
        public_key=public_key,
        metadata=json.dumps(metadata)
    )
    
    # Return the server information
    return {
        "agent_id": agent["id"],
        "private_key": private_key,
        "public_key": public_key,
        "name": name,
        "description": description,
        "metadata": metadata
    }


async def grant_mcp_access(authed: Authed, 
                          client_agent_id: Union[str, UUID], 
                          server_agent_id: Union[str, UUID], 
                          permissions: Optional[list] = None) -> bool:
    """
    Grant an MCP client access to an MCP server.
    
    Args:
        authed: Initialized Authed client
        client_agent_id: ID of the client agent
        server_agent_id: ID of the server agent
        permissions: Optional list of permissions
        
    Returns:
        True if successful, False otherwise
    """
    # Default permissions for MCP access
    if permissions is None:
        permissions = ["read", "execute"]
    
    try:
        # Grant permissions using Authed
        await authed.grant_permission(
            source_id=str(client_agent_id),
            target_id=str(server_agent_id),
            permissions=permissions
        )
        return True
    except Exception as e:
        logger.error(f"Error granting permissions: {str(e)}")
        return False 