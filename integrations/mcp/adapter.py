"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
from typing import Any, Dict, Optional, Union, List
from uuid import UUID
from contextlib import AsyncExitStack

# Import Authed SDK
from client.sdk import Authed

# Import MCP SDK
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, Prompt
from mcp import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logger = logging.getLogger(__name__)

class AuthedMCPServer:
    """
    MCP server with Authed authentication.
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
    
    def resource(self, path: str = None):
        """Register a resource handler."""
        return self.mcp.resource(path)
    
    def tool(self, name: str = None):
        """Register a tool handler."""
        return self.mcp.tool(name)
    
    def prompt(self, name: str = None):
        """Register a prompt handler."""
        return self.mcp.prompt(name)
    
    def run(self):
        """Run the MCP server."""
        # Let the MCP server handle its own event loop
        return self.mcp.run()


class AuthedMCPClient:
    """
    MCP client with Authed authentication using SSE transport.
    """
    
    def __init__(self, registry_url: str, agent_id: str, agent_secret: str, private_key: str, public_key: str = None):
        """Initialize the client with Authed credentials."""
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        self._token_cache = {}
        # Don't store session and context managers as instance variables
        # Create a new connection for each request
    
    async def get_token(self, target_server_id: Union[str, UUID]) -> str:
        """Get an interaction token for a target server."""
        cache_key = str(target_server_id)
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        token = await self.authed.auth.get_interaction_token(target_server_id)
        self._token_cache[cache_key] = token
        return token
    
    async def connect_and_execute(self, server_url: str, server_agent_id: Union[str, UUID], operation):
        """Connect to an MCP server and execute an operation."""
        # Get authentication token
        token = await self.get_token(server_agent_id)
        
        # Set up SSE client with authentication
        headers = {"Authorization": f"Bearer {token}"}
        
        # Use a context manager to ensure proper cleanup
        async with sse_client(url=server_url, headers=headers) as streams:
            session = ClientSession(*streams)
            await session.initialize()
            
            # Execute the operation
            result = await operation(session)
            
            # Return the result
            return result
    
    async def list_resources(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Resource]:
        """List resources from an MCP server."""
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_resources()
        )
    
    async def list_tools(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Tool]:
        """List tools from an MCP server."""
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_tools()
        )
    
    async def list_prompts(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Prompt]:
        """List prompts from an MCP server."""
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_prompts()
        )
    
    async def read_resource(self, server_url: str, server_agent_id: Union[str, UUID], resource_id: str) -> tuple:
        """Read a resource from an MCP server."""
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.read_resource(resource_id)
        )
    
    async def call_tool(self, server_url: str, server_agent_id: Union[str, UUID], tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on an MCP server."""
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.call_tool(tool_name, arguments or {})
        )
    
    async def get_prompt(self, server_url: str, server_agent_id: Union[str, UUID], prompt_name: str, arguments: Dict[str, str] = None) -> Any:
        """Get a prompt from an MCP server."""
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.get_prompt(prompt_name, arguments or {})
        )


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
    default_permissions = [
        "mcp:list_tools",
        "mcp:call_tool",
        "mcp:list_resources",
        "mcp:read_resource",
        "mcp:list_prompts",
        "mcp:get_prompt"
    ]
    
    # Use provided permissions or defaults
    perms = permissions or default_permissions
    
    # Grant permissions
    try:
        await authed.grant_permission(
            source_id=client_agent_id,
            target_id=server_agent_id,
            permissions=perms
        )
        return True
    except Exception as e:
        logger.error(f"Error granting MCP access: {str(e)}")
        return False 