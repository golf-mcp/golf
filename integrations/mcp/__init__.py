"""
Authed MCP Integration

This package provides integration between Authed authentication and the Model Context Protocol (MCP).
"""

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
    "create_client"
]

__version__ = "0.1.0" 