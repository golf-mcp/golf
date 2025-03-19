"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
from uuid import UUID
from typing import Any, Dict, Optional, Union, List


# Import Authed SDK
from authed import Authed

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
        logger.info(f"Initializing Authed SDK for server with agent_id: {agent_id}")
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        logger.info(f"Authed SDK initialized successfully for server")
        
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
        logger.info(f"Initializing Authed SDK for client with agent_id: {agent_id}")
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        logger.info(f"Authed SDK initialized successfully for client")
    
    async def connect_and_execute(self, server_url: str, server_agent_id: Union[str, UUID], operation, method: str = "GET"):
        """Connect to an MCP server and execute an operation."""
        # Use the protect_request method to get properly formatted headers
        headers = await self.authed.auth.protect_request(
            method=method,
            url=server_url,
            target_agent_id=server_agent_id
        )
        
        logger.info(f"Connecting to MCP server at {server_url} with Authed token")
        logger.debug(f"Using headers: {headers}")
        logger.debug(f"Using HTTP method: {method}")
        
        # Use a context manager to ensure proper cleanup
        try:
            logger.info(f"Establishing SSE connection to {server_url}")
            async with sse_client(url=server_url, headers=headers) as streams:
                logger.info(f"SSE connection established, initializing MCP session")
                session = ClientSession(*streams)
                await session.initialize()
                
                # Execute the operation
                logger.info(f"Executing MCP operation")
                result = await operation(session)
                
                # Return the result
                logger.info(f"MCP operation completed successfully")
                return result
        except Exception as e:
            logger.error(f"Error during MCP operation: {str(e)}")
            raise
    
    async def list_resources(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Resource]:
        """List resources from an MCP server."""
        logger.info(f"Listing resources from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_resources()
        )
    
    async def list_tools(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Tool]:
        """List tools from an MCP server."""
        logger.info(f"Listing tools from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_tools()
        )
    
    async def list_prompts(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Prompt]:
        """List prompts from an MCP server."""
        logger.info(f"Listing prompts from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_prompts()
        )
    
    async def read_resource(self, server_url: str, server_agent_id: Union[str, UUID], resource_id: str) -> tuple:
        """Read a resource from an MCP server."""
        logger.info(f"Reading resource {resource_id} from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.read_resource(resource_id)
        )
    
    async def call_tool(self, server_url: str, server_agent_id: Union[str, UUID], tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on an MCP server."""
        logger.info(f"Calling tool {tool_name} on server: {server_agent_id} with arguments: {arguments}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.call_tool(tool_name, arguments or {})
        )
    
    async def get_prompt(self, server_url: str, server_agent_id: Union[str, UUID], prompt_name: str, arguments: Dict[str, str] = None) -> Any:
        """Get a prompt from an MCP server."""
        logger.info(f"Getting prompt {prompt_name} from server: {server_agent_id} with arguments: {arguments}")
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