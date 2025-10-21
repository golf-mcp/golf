"""Helper functions for working with authentication in MCP context."""

from contextvars import ContextVar


# Context variable to store the current request's API key
_current_api_key: ContextVar[str | None] = ContextVar("current_api_key", default=None)


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


def get_auth_token() -> str | None:
    """Get the authorization token from the current request context.

    This function should be used in tools to retrieve the authorization token
    (typically a JWT or OAuth token) that was sent in the request headers.

    Unlike get_api_key(), this function extracts the raw token from the Authorization
    header without stripping any prefix, making it suitable for passing through
    to upstream APIs that expect the full Authorization header value.

    Returns:
        The authorization token if available, None otherwise

    Example:
        # In a tool file
        from golf.auth import get_auth_token

        async def call_upstream_api():
            auth_token = get_auth_token()
            if not auth_token:
                return {"error": "No authorization token provided"}

            # Use the full token in upstream request
            headers = {"Authorization": f"Bearer {auth_token}"}
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data", headers=headers)
            ...
    """
    # Try to get directly from HTTP request if available (FastMCP pattern)
    try:
        # This follows the FastMCP pattern for accessing HTTP requests
        from fastmcp.server.dependencies import get_http_request

        request = get_http_request()

        if request and hasattr(request, "state") and hasattr(request.state, "auth_token"):
            return request.state.auth_token

        if request:
            # Extract authorization token from Authorization header
            auth_header = None
            for k, v in request.headers.items():
                if k.lower() == "authorization":
                    auth_header = v
                    break

            if auth_header:
                # Extract the token part (everything after "Bearer ")
                token = extract_token_from_header(auth_header)
                if token:
                    return token

                # If not Bearer format, return the whole header value minus "Bearer " prefix if present
                if auth_header.lower().startswith("bearer "):
                    return auth_header[7:]  # Remove "Bearer " prefix
                return auth_header

    except (ImportError, RuntimeError):
        # FastMCP not available or not in HTTP context
        pass
    except Exception:
        pass

    return None
