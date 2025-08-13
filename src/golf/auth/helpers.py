"""Helper functions for working with authentication in MCP context."""

from contextvars import ContextVar
from typing import Any

from starlette.requests import Request

# Context variable to store the current request's API key
_current_api_key: ContextVar[str | None] = ContextVar("current_api_key", default=None)


def get_provider_token() -> str | None:
    """
    Get a provider token (legacy function - no longer supported in Golf 0.2.x).

    In Golf 0.2.x, use FastMCP's built-in auth providers for OAuth flows.
    This function returns None and is kept for backwards compatibility.
    """
    # Legacy OAuth provider support removed in Golf 0.2.x
    # Use FastMCP 2.11+ auth providers instead
    return None


def extract_token_from_header(auth_header: str) -> str | None:
    """Extract bearer token from Authorization header.

    Args:
        auth_header: Authorization header value

    Returns:
        Bearer token or None if not present/valid
    """
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def set_api_key(api_key: str | None) -> None:
    """Set the API key for the current request context.

    This is an internal function used by the middleware.

    Args:
        api_key: The API key to store in the context
    """
    _current_api_key.set(api_key)


def get_api_key() -> str | None:
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
    # Try to get directly from HTTP request if available (FastMCP pattern)
    try:
        # This follows the FastMCP pattern for accessing HTTP requests
        from fastmcp.server.dependencies import get_http_request

        request = get_http_request()

        if request and hasattr(request, "state") and hasattr(request.state, "api_key"):
            api_key = request.state.api_key
            return api_key

        # Get the API key configuration
        from golf.auth.api_key import get_api_key_config

        api_key_config = get_api_key_config()

        if api_key_config and request:
            # Extract API key from headers
            header_name = api_key_config.header_name
            header_prefix = api_key_config.header_prefix

            # Case-insensitive header lookup
            api_key = None
            for k, v in request.headers.items():
                if k.lower() == header_name.lower():
                    api_key = v
                    break

            # Strip prefix if configured
            if api_key and header_prefix and api_key.startswith(header_prefix):
                api_key = api_key[len(header_prefix) :]

            if api_key:
                return api_key
    except (ImportError, RuntimeError):
        # FastMCP not available or not in HTTP context
        pass
    except Exception:
        pass

    # Final fallback: environment variable (for development/testing)
    import os

    env_api_key = os.environ.get("API_KEY")
    if env_api_key:
        return env_api_key

    return None


def get_api_key_from_request(request: Request) -> str | None:
    """Get the API key from a specific request object.

    This is useful when you have direct access to the request object.

    Args:
        request: The Starlette Request object

    Returns:
        The API key if available, None otherwise
    """
    # Check request state first (set by our middleware)
    if hasattr(request, "state") and hasattr(request.state, "api_key"):
        return request.state.api_key

    # Fall back to context variable
    return _current_api_key.get()


def debug_api_key_context() -> dict[str, Any]:
    """Debug function to inspect API key context.

    Returns a dictionary with debugging information about the current
    API key context. Useful for troubleshooting authentication issues.

    Returns:
        Dictionary with debug information
    """
    import asyncio
    import os
    import sys

    debug_info = {
        "context_var_value": _current_api_key.get(),
        "has_async_task": False,
        "task_id": None,
        "main_module_has_storage": False,
        "main_module_has_context": False,
        "request_id_from_context": None,
        "env_vars": {
            "API_KEY": bool(os.environ.get("API_KEY")),
            "GOLF_API_KEY_DEBUG": os.environ.get("GOLF_API_KEY_DEBUG", "false"),
        },
    }

    try:
        task = asyncio.current_task()
        if task:
            debug_info["has_async_task"] = True
            debug_info["task_id"] = id(task)
    except Exception:
        pass

    try:
        main_module = sys.modules.get("__main__")
        if main_module:
            debug_info["main_module_has_storage"] = hasattr(main_module, "api_key_storage")
            debug_info["main_module_has_context"] = hasattr(main_module, "request_id_context")

            if hasattr(main_module, "request_id_context"):
                request_id_context = main_module.request_id_context
                debug_info["request_id_from_context"] = request_id_context.get()
    except Exception:
        pass

    return debug_info
