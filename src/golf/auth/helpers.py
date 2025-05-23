"""Helper functions for working with authentication in MCP context."""

from typing import Optional
from contextvars import ContextVar

# Re-export get_access_token from the MCP SDK
from mcp.server.auth.middleware.auth_context import get_access_token

from .oauth import GolfOAuthProvider

# Context variable to store the active OAuth provider
_active_golf_oauth_provider: Optional[GolfOAuthProvider] = None

# Context variable to store the current request's API key
_current_api_key: ContextVar[Optional[str]] = ContextVar('current_api_key', default=None)

def _set_active_golf_oauth_provider(provider: GolfOAuthProvider) -> None:
    """
    Sets the active GolfOAuthProvider instance.
    Should only be called once during server startup.
    """
    global _active_golf_oauth_provider
    _active_golf_oauth_provider = provider

def get_provider_token() -> Optional[str]:
    """
    Get a provider token (e.g., GitHub token) associated with the current
    MCP session's access token.

    This relies on _set_active_golf_oauth_provider being called at server startup.
    """
    mcp_access_token = get_access_token() # From MCP SDK, uses its own ContextVar
    if not mcp_access_token:
        # No active MCP session token.
        return None

    provider = _active_golf_oauth_provider
    if not provider:
        return None
    
    if not hasattr(provider, "get_provider_token"):
        return None

    # Call the get_provider_token method on the actual GolfOAuthProvider instance
    return provider.get_provider_token(mcp_access_token.token)

def extract_token_from_header(auth_header: str) -> Optional[str]:
    """Extract bearer token from Authorization header.

    Args:
        auth_header: Authorization header value

    Returns:
        Bearer token or None if not present/valid
    """
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None

    return parts[1]

def set_api_key(api_key: Optional[str]) -> None:
    """Set the API key for the current request context.
    
    This is an internal function used by the middleware.
    
    Args:
        api_key: The API key to store in the context
    """
    _current_api_key.set(api_key)

def get_api_key() -> Optional[str]:
    """Get the API key from the current request context.
    
    This function should be used in tools to retrieve the API key
    that was sent in the request headers.
    
    Returns:
        The API key if available, None otherwise
        
    Example:
        # In a tool file
        from golf.auth import get_api_key
        
        async def call_api():
            api_key = get_api_key()
            if not api_key:
                return {"error": "No API key provided"}
            
            # Use the API key in your request
            headers = {"Authorization": f"Bearer {api_key}"}
            ...
    """
    return _current_api_key.get() 