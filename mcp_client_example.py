"""
Example MCP Client with Authed Authentication

This example demonstrates how to use an MCP client with Authed authentication.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional
from uuid import UUID

# Import Authed SDK
from client.sdk import Authed

# Import our adapter
from mcp_authed_adapter import AuthedMCPClientAdapter, grant_mcp_access

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMCPClient:
    """
    A simple MCP client implementation for demonstration purposes.
    """
    
    def __init__(self):
        """Initialize the MCP client."""
        pass
    
    async def send_request(self, request: Dict[str, Any], url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Send an MCP request to a server.
        
        In a real implementation, this would use HTTP to send the request.
        For this example, we'll simulate the request/response cycle.
        
        Args:
            request: The MCP request to send
            url: The URL of the MCP server
            headers: Optional request headers
            
        Returns:
            MCP response
        """
        logger.info(f"Sending request to {url}:")
        logger.info(f"  Headers: {headers}")
        logger.info(f"  Request: {json.dumps(request, indent=2)}")
        
        # In a real implementation, this would be an HTTP request
        # For this example, we'll just return a simulated response
        return {
            "jsonrpc": "2.0",
            "result": {
                "simulated": True,
                "message": "This is a simulated response. In a real implementation, this would be the response from the MCP server."
            },
            "id": request.get("id")
        }


async def setup_mcp_client_with_authed():
    """
    Set up an MCP client with Authed authentication.
    
    Returns:
        Tuple of (client, adapter)
    """
    # Initialize Authed from environment variables
    authed = Authed.from_env()
    
    # Create MCP client
    mcp_client = SimpleMCPClient()
    
    # Create Authed adapter for MCP client
    adapter = AuthedMCPClientAdapter(authed)
    
    return mcp_client, adapter, authed


async def load_mcp_server_info():
    """
    Load MCP server information from .env.mcp_server file.
    
    Returns:
        Dictionary with server information
    """
    try:
        server_info = {}
        with open(".env.mcp_server", "r") as f:
            for line in f:
                key, value = line.strip().split("=", 1)
                server_info[key] = value
        
        return {
            "agent_id": server_info.get("MCP_SERVER_AGENT_ID"),
            "public_key": server_info.get("MCP_SERVER_PUBLIC_KEY")
        }
    except FileNotFoundError:
        logger.error("MCP server info file (.env.mcp_server) not found. Run mcp_server_example.py first.")
        return None
    except Exception as e:
        logger.error(f"Error loading MCP server info: {str(e)}")
        return None


async def make_authenticated_request(client, adapter, server_agent_id, request):
    """
    Make an authenticated request to an MCP server.
    
    Args:
        client: The MCP client
        adapter: The Authed adapter
        server_agent_id: The ID of the MCP server
        request: The request to send
        
    Returns:
        MCP response
    """
    # Prepare request with authentication
    prepared = await adapter.prepare_request(
        request=request,
        target_server_id=server_agent_id
    )
    
    # Send request
    response = await client.send_request(
        request=prepared["request"],
        url=f"https://mcp-server/{server_agent_id}",  # Simulated URL
        headers=prepared["headers"]
    )
    
    return response


async def main():
    """Main function to demonstrate the MCP client with Authed authentication."""
    # Set up MCP client with Authed
    mcp_client, adapter, authed = await setup_mcp_client_with_authed()
    
    # Load MCP server info
    server_info = await load_mcp_server_info()
    if not server_info or not server_info.get("agent_id"):
        logger.error("Failed to load MCP server info. Exiting.")
        return
    
    server_agent_id = server_info["agent_id"]
    logger.info(f"Using MCP server with agent ID: {server_agent_id}")
    
    # Grant access to the MCP server (in a real scenario, this would be done during setup)
    client_agent_id = os.environ.get("AUTHED_AGENT_ID")
    if client_agent_id:
        logger.info(f"Granting access from client agent {client_agent_id} to server agent {server_agent_id}")
        success = await grant_mcp_access(
            authed=authed,
            client_agent_id=client_agent_id,
            server_agent_id=server_agent_id
        )
        
        if success:
            logger.info("Access granted successfully")
        else:
            logger.warning("Failed to grant access")
    else:
        logger.warning("AUTHED_AGENT_ID not found in environment variables")
    
    # Example request
    example_request = {
        "jsonrpc": "2.0",
        "method": "resources/get",
        "params": {
            "id": "sample_doc"
        },
        "id": "client-request-1"
    }
    
    # Make authenticated request
    logger.info("Making authenticated request to MCP server:")
    response = await make_authenticated_request(
        client=mcp_client,
        adapter=adapter,
        server_agent_id=server_agent_id,
        request=example_request
    )
    
    logger.info(f"Response: {json.dumps(response, indent=2)}")
    
    # Example tool execution request
    tool_request = {
        "jsonrpc": "2.0",
        "method": "tools/execute",
        "params": {
            "id": "echo",
            "params": {
                "message": "Hello from authenticated MCP client!"
            }
        },
        "id": "client-request-2"
    }
    
    # Make authenticated tool request
    logger.info("\nMaking authenticated tool request to MCP server:")
    tool_response = await make_authenticated_request(
        client=mcp_client,
        adapter=adapter,
        server_agent_id=server_agent_id,
        request=tool_request
    )
    
    logger.info(f"Response: {json.dumps(tool_response, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main()) 