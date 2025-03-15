"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
from typing import Any, Dict, Optional, Union, List, Callable, Awaitable
from uuid import UUID

# Import Authed SDK
from client.sdk import Authed
from client.sdk.exceptions import AuthenticationError

# Import MCP SDK
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, Prompt
from mcp.server.models import InitializationOptions

# Configure logging
logger = logging.getLogger(__name__)

class AuthedMCPServerMiddleware:
    """
    Middleware for MCP servers to use Authed for authentication.
    
    This middleware sits between MCP clients and servers, verifying Authed tokens
    before forwarding requests to the MCP server.
    """
    
    def __init__(self, authed: Authed):
        """
        Initialize the middleware with an Authed client.
        
        Args:
            authed: Initialized Authed client
        """
        self.authed = authed
    
    async def authenticate_request(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Authenticate a request using Authed.
        
        Args:
            headers: Request headers containing authentication token
            
        Returns:
            Agent ID if authentication is successful, None otherwise
        """
        # Extract token from Authorization header
        auth_header = headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            return None
            
        token = auth_header.replace("Bearer ", "")
        
        try:
            # Verify the token using Authed
            verification_result = await self.authed.verify_token(token)
            if verification_result and verification_result.get("agent_id"):
                return verification_result["agent_id"]
            return None
        except AuthenticationError as e:
            logger.warning(f"Authentication error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {str(e)}")
            return None
    
    async def __call__(self, request, call_next):
        """
        Process a request with authentication.
        
        Args:
            request: The request to process
            call_next: Function to call next in the middleware chain
            
        Returns:
            Response
        """
        # Get headers from request
        headers = dict(request.headers)
        
        # Authenticate the request
        agent_id = await self.authenticate_request(headers)
        if not agent_id:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": 401,
                    "message": "Authentication failed"
                },
                "id": None
            }
        
        # Add agent_id to request state
        request.state.agent_id = agent_id
        
        # Call next middleware
        return await call_next(request)


class AuthedMCPServer:
    """
    MCP server with Authed authentication.
    
    This class wraps an MCP server with Authed authentication.
    """
    
    def __init__(self, name: str, authed: Authed):
        """
        Initialize the server with an Authed client.
        
        Args:
            name: Name of the MCP server
            authed: Initialized Authed client
        """
        self.name = name
        self.authed = authed
        self.mcp = FastMCP(name)
        self.auth_middleware = AuthedMCPServerMiddleware(authed)
        
        # Add authentication middleware
        self.mcp.app.middleware("http")(self.auth_middleware)
    
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
        # Register the server with Authed
        server_info = await register_mcp_server(
            authed=self.authed,
            name=self.name,
            description=f"MCP server: {self.name}",
            capabilities=self.mcp.get_capabilities()
        )
        
        logger.info(f"Registered MCP server with Authed: {server_info['agent_id']}")
        
        # Save server credentials to .env file for future use
        with open(f".env.mcp_server.{self.name}", "w") as f:
            f.write(f"MCP_SERVER_AGENT_ID={server_info['agent_id']}\n")
            f.write(f"MCP_SERVER_PRIVATE_KEY={server_info['private_key']}\n")
            f.write(f"MCP_SERVER_PUBLIC_KEY={server_info['public_key']}\n")
        
        # Run the MCP server
        await self.mcp.run(host=host, port=port)


class AuthedMCPClient:
    """
    MCP client with Authed authentication.
    
    This class provides a client for making authenticated requests to MCP servers.
    """
    
    def __init__(self, authed: Authed):
        """
        Initialize the client with an Authed client.
        
        Args:
            authed: Initialized Authed client
        """
        self.authed = authed
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
        token = await self.authed.get_interaction_token(target_server_id)
        
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
        from mcp import ClientSession, HttpServerParameters
        
        # Get authentication token
        token = await self.get_token(server_agent_id)
        
        # Create server parameters
        server_params = HttpServerParameters(
            url=server_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Create client session
        from mcp.client.http import http_client
        async with http_client(server_params) as (read, write):
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
    # Generate key pair
    private_key, public_key = authed.generate_key_pair()
    
    # Prepare metadata
    metadata = {
        "type": "mcp_server",
        "capabilities": capabilities or {}
    }
    
    # Register server as an agent
    agent = await authed.register_agent(
        name=name,
        description=description,
        public_key=public_key,
        metadata=json.dumps(metadata)
    )
    
    return {
        "agent_id": agent.id,
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
        # Grant permissions
        await authed.grant_permission(
            source_agent_id=client_agent_id,
            target_agent_id=server_agent_id,
            permissions=permissions
        )
        return True
    except Exception as e:
        logger.error(f"Error granting permissions: {str(e)}")
        return False 