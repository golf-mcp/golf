"""
MCP-Authed Integration

This package provides integration between Authed authentication and Model Context Protocol (MCP).
"""

from .adapter import (
    AuthedMCPServer,
    AuthedMCPClient,
    AuthedMCPServerMiddleware,
    register_mcp_server,
    grant_mcp_access
)

__all__ = [
    'AuthedMCPServer',
    'AuthedMCPClient',
    'AuthedMCPServerMiddleware',
    'register_mcp_server',
    'grant_mcp_access'
] 