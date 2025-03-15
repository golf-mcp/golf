"""
Example MCP Server with Authed Authentication

This example demonstrates how to integrate an MCP server with Authed authentication.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

# Import Authed SDK
from client.sdk import Authed

# Import our adapter
from mcp_authed_adapter import AuthedMCPServerAdapter, register_mcp_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory MCP server implementation
class SimpleMCPServer:
    """
    A simple MCP server implementation for demonstration purposes.
    """
    
    def __init__(self):
        """Initialize the MCP server."""
        self.capabilities = {
            "resources": True,
            "tools": True
        }
        
        # Sample resources
        self.resources = {
            "sample_doc": {
                "content": "This is a sample document accessible via MCP.",
                "metadata": {
                    "type": "text/plain",
                    "created": "2024-11-25T12:00:00Z"
                }
            }
        }
        
        # Sample tools
        self.tools = {
            "echo": {
                "description": "Echo back the input",
                "parameters": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo"
                    }
                }
            }
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an MCP request.
        
        Args:
            request: The MCP request to handle
            
        Returns:
            MCP response
        """
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        # Check if this is a capabilities request
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "capabilities": self.capabilities
                },
                "id": request_id
            }
        
        # Handle resource requests
        elif method == "resources/get":
            resource_id = params.get("id")
            if resource_id in self.resources:
                return {
                    "jsonrpc": "2.0",
                    "result": self.resources[resource_id],
                    "id": request_id
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 404,
                        "message": f"Resource not found: {resource_id}"
                    },
                    "id": request_id
                }
        
        # Handle tool requests
        elif method == "tools/execute":
            tool_id = params.get("id")
            tool_params = params.get("params", {})
            
            if tool_id == "echo":
                message = tool_params.get("message", "")
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "output": message
                    },
                    "id": request_id
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 404,
                        "message": f"Tool not found: {tool_id}"
                    },
                    "id": request_id
                }
        
        # Handle unknown methods
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": 404,
                    "message": f"Method not found: {method}"
                },
                "id": request_id
            }


async def setup_mcp_server_with_authed():
    """
    Set up an MCP server with Authed authentication.
    
    Returns:
        Tuple of (server, adapter)
    """
    # Initialize Authed from environment variables
    authed = Authed.from_env()
    
    # Create MCP server
    mcp_server = SimpleMCPServer()
    
    # Register MCP server with Authed
    server_info = await register_mcp_server(
        authed=authed,
        name="Example MCP Server",
        description="A simple MCP server with Authed authentication",
        capabilities=mcp_server.capabilities
    )
    
    logger.info(f"Registered MCP server with Authed: {server_info['agent_id']}")
    
    # Save server credentials to .env file for future use
    with open(".env.mcp_server", "w") as f:
        f.write(f"MCP_SERVER_AGENT_ID={server_info['agent_id']}\n")
        f.write(f"MCP_SERVER_PRIVATE_KEY={server_info['private_key']}\n")
        f.write(f"MCP_SERVER_PUBLIC_KEY={server_info['public_key']}\n")
    
    # Create Authed adapter for MCP server
    adapter = AuthedMCPServerAdapter(authed)
    
    return mcp_server, adapter


async def handle_authenticated_request(mcp_server, adapter, request_data, headers):
    """
    Handle an authenticated MCP request.
    
    Args:
        mcp_server: The MCP server
        adapter: The Authed adapter
        request_data: The request data
        headers: The request headers
        
    Returns:
        MCP response
    """
    try:
        # Parse request
        request = json.loads(request_data)
        
        # Process request with authentication
        response = await adapter.process_mcp_request(
            mcp_server.handle_request,
            request,
            headers
        )
        
        return json.dumps(response)
    except json.JSONDecodeError:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {
                "code": 400,
                "message": "Invalid JSON"
            },
            "id": None
        })
    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            },
            "id": None
        })


async def main():
    """Main function to demonstrate the MCP server with Authed authentication."""
    # Set up MCP server with Authed
    mcp_server, adapter = await setup_mcp_server_with_authed()
    
    # Example request
    example_request = {
        "jsonrpc": "2.0",
        "method": "tools/execute",
        "params": {
            "id": "echo",
            "params": {
                "message": "Hello, authenticated MCP world!"
            }
        },
        "id": "1"
    }
    
    # Example headers (in a real scenario, these would come from an authenticated client)
    example_headers = {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
    
    # Handle request
    logger.info("Handling example request (this will fail without a valid token):")
    response = await handle_authenticated_request(
        mcp_server,
        adapter,
        json.dumps(example_request),
        example_headers
    )
    
    logger.info(f"Response: {response}")
    
    logger.info("\nTo use this MCP server:")
    logger.info("1. Register an agent as an MCP client")
    logger.info("2. Grant the client access to the MCP server")
    logger.info("3. Use the AuthedMCPClientAdapter to make authenticated requests")
    logger.info(f"4. The MCP server agent ID is saved in .env.mcp_server")


if __name__ == "__main__":
    asyncio.run(main()) 