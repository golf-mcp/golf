"""
Authed MCP Integration

This package provides integration between Authed authentication and the Model Context Protocol (MCP).
"""

# Import server components
from .authed_mcp.server import (
    AuthedMiddleware
)

# Import client components
from .authed_mcp.client import (
    AuthedMCPHeaders,
    get_auth_headers
)

# Import the modules directly for use in entry points
from .authed_mcp import client
from .authed_mcp import server

__all__ = [
    # Server components
    "AuthedMiddleware",
    
    # Client components
    "AuthedMCPHeaders",
    "get_auth_headers",
    
    # Modules
    "client",
    "server"
]

__version__ = "0.1.0" 