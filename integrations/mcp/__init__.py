"""
Authed MCP Integration

This package provides integration between Authed authentication and the Model Context Protocol (MCP).
"""

# Import all public components to make them available at the root level
from .adapter import (
    AuthedMCPServer,
    AuthedMCPClient,
    register_mcp_server,
    grant_mcp_access
)

from .server import (
    create_server,
    run_server,
    McpServerBuilder,
    register_default_handlers
)

from .client import (
    create_client
)

# Import the modules directly for use in entry points
from . import server
from . import client

__all__ = [
    # Adapter classes
    "AuthedMCPServer",
    "AuthedMCPClient",
    "register_mcp_server",
    "grant_mcp_access",
    
    # Server helper functions
    "create_server",
    "run_server",
    "McpServerBuilder",
    "register_default_handlers",
    
    # Client helper functions
    "create_client",
    
    # Modules
    "server",
    "client"
]

__version__ = "0.1.0" 