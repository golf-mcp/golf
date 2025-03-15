"""
Authed integration with Model Context Protocol (MCP).

This package provides adapters and utilities for integrating Authed authentication
with the Model Context Protocol (MCP).
"""

from .adapter import (
    AuthedMCPServerAdapter,
    AuthedMCPClientAdapter,
    register_mcp_server,
    grant_mcp_access
)

__all__ = [
    'AuthedMCPServerAdapter',
    'AuthedMCPClientAdapter',
    'register_mcp_server',
    'grant_mcp_access'
] 