"""
Test imports for the MCP integration.

This script tests that all components of the MCP integration can be imported correctly.
"""

def test_imports():
    """Test that all components of the MCP integration can be imported correctly."""
    try:
        # Import the main classes
        from integrations.mcp import (
            AuthedMCPServer,
            AuthedMCPClient,
            AuthedMCPServerMiddleware,
            register_mcp_server,
            grant_mcp_access
        )
        
        # Import MCP SDK components to verify they're accessible
        from mcp.server import Server
        from mcp.server.fastmcp import FastMCP
        from mcp.types import Resource, Tool, Prompt
        
        # Import FastAPI/Starlette components
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    test_imports() 