"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
import os
from typing import Any, Dict, Optional, Union, List
from uuid import UUID

# Import Authed SDK
from client.sdk import Authed

# Import MCP SDK
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, Prompt
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server import stdio

# Configure logging
logger = logging.getLogger(__name__)

class AuthedMCPServer:
    """
    MCP server with Authed authentication using stdio transport.
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
        
        # Store auth info for request verification
        self._auth_info = {
            "agent_id": agent_id,
            "auth_handler": self.authed.auth
        }
    
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
    
    async def run(self):
        """Run the MCP server using stdio transport."""
        # Run the MCP server with stdio transport
        async with stdio.stdio_server() as (read_stream, write_stream):
            await self.mcp.run(read_stream, write_stream)


class AuthedMCPClient:
    """
    MCP client with Authed authentication using stdio transport.
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
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        self._token_cache = {}
    
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
        cache_key = str(target_server_id)
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        token = await self.authed.auth.get_interaction_token(target_server_id)
        self._token_cache[cache_key] = token
        return token
    
    async def connect(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None, env: Dict[str, str] = None):
        """
        Connect to an MCP server using stdio.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            env: Environment variables for the server process
            
        Returns:
            MCP client session
        """
        # Get authentication token if server_agent_id is provided
        auth_env = env or {}
        if server_agent_id:
            token = await self.get_token(server_agent_id)
            auth_env["MCP_AUTH_TOKEN"] = token
        
        # Create server parameters
        server_params = StdioServerParameters(
            command=server_command,
            args=server_args or [],
            env=auth_env
        )
        
        # Create and initialize client session
        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.initialize()
        return session
    
    async def list_resources(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None) -> List[Resource]:
        """
        List resources from an MCP server.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            
        Returns:
            List of resources
        """
        session = await self.connect(server_command, server_args, server_agent_id)
        return await session.list_resources()
    
    async def read_resource(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None, resource_id: str = None) -> tuple:
        """
        Read a resource from an MCP server.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            resource_id: ID of the resource to read
            
        Returns:
            Tuple of (content, mime_type)
        """
        session = await self.connect(server_command, server_args, server_agent_id)
        return await session.read_resource(resource_id)
    
    async def list_tools(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None) -> List[Tool]:
        """
        List tools from an MCP server.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            
        Returns:
            List of tools
        """
        session = await self.connect(server_command, server_args, server_agent_id)
        return await session.list_tools()
    
    async def call_tool(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None, tool_name: str = None, arguments: Dict[str, Any] = None) -> Any:
        """
        Call a tool on an MCP server.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            tool_name: Name of the tool to call
            arguments: Arguments for the tool
            
        Returns:
            Tool result
        """
        session = await self.connect(server_command, server_args, server_agent_id)
        return await session.call_tool(tool_name, arguments or {})
    
    async def list_prompts(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None) -> List[Prompt]:
        """
        List prompts from an MCP server.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            
        Returns:
            List of prompts
        """
        session = await self.connect(server_command, server_args, server_agent_id)
        return await session.list_prompts()
    
    async def get_prompt(self, server_command: str, server_args: list = None, server_agent_id: Union[str, UUID] = None, prompt_name: str = None, arguments: Dict[str, Any] = None) -> Any:
        """
        Get a prompt from an MCP server.
        
        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
            server_agent_id: ID of the MCP server agent (for authentication)
            prompt_name: Name of the prompt to get
            arguments: Arguments for the prompt
            
        Returns:
            Prompt result
        """
        session = await self.connect(server_command, server_args, server_agent_id)
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