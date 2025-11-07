"""Golf middleware support - re-exports FastMCP middleware with Golf branding."""

# Re-export FastMCP middleware components for user imports
from fastmcp.server.middleware import Middleware, MiddlewareContext

# Export commonly used types
__all__ = ["Middleware", "MiddlewareContext"]
