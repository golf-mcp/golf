"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
from typing import Any, Dict, Optional, Union
from uuid import UUID

# Import Authed SDK
from client.sdk import Authed
from client.sdk.exceptions import AuthenticationError

# MCP types (these would typically come from MCP SDK)
MCPRequest = Dict[str, Any]
MCPResponse = Dict[str, Any]
MCPError = Dict[str, Any]

logger = logging.getLogger(__name__)

class AuthedMCPServerAdapter:
    """
    Adapter for MCP servers to use Authed for authentication.
    
    This adapter sits between MCP clients and servers, verifying Authed tokens
    before forwarding requests to the MCP server.
    """
    
    def __init__(self, authed: Authed):
        """
        Initialize the adapter with an Authed client.
        
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
    
    async def process_mcp_request(self, 
                                 mcp_server_handler, 
                                 request: MCPRequest, 
                                 headers: Dict[str, str]) -> Union[MCPResponse, MCPError]:
        """
        Process an MCP request with authentication.
        
        Args:
            mcp_server_handler: Function to handle MCP requests
            request: The MCP request to process
            headers: Request headers
            
        Returns:
            MCP response or error
        """
        # Authenticate the request
        agent_id = await self.authenticate_request(headers)
        if not agent_id:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": 401,
                    "message": "Authentication failed"
                },
                "id": request.get("id")
            }
        
        # Add agent_id to request context
        if "context" not in request:
            request["context"] = {}
        request["context"]["agent_id"] = agent_id
        
        # Forward to MCP server handler
        try:
            return await mcp_server_handler(request)
        except Exception as e:
            logger.error(f"Error processing MCP request: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": 500,
                    "message": f"Internal server error: {str(e)}"
                },
                "id": request.get("id")
            }


class AuthedMCPClientAdapter:
    """
    Adapter for MCP clients to use Authed for authentication.
    
    This adapter prepares MCP requests with Authed authentication tokens
    before sending them to MCP servers.
    """
    
    def __init__(self, authed: Authed):
        """
        Initialize the adapter with an Authed client.
        
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
    
    async def prepare_request(self, 
                             request: MCPRequest, 
                             target_server_id: Union[str, UUID],
                             headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Prepare an MCP request with authentication.
        
        Args:
            request: The MCP request to prepare
            target_server_id: ID of the target MCP server
            headers: Optional additional headers
            
        Returns:
            Prepared request with authentication
        """
        # Get token for target server
        token = await self.get_token(target_server_id)
        
        # Prepare headers
        if headers is None:
            headers = {}
        
        headers["Authorization"] = f"Bearer {token}"
        
        # Return prepared request with headers
        return {
            "request": request,
            "headers": headers
        }


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