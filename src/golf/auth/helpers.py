"""Helper functions for working with authentication in MCP context."""

from contextvars import ContextVar
from dataclasses import dataclass


# Context variable to store the current request's API key
_current_api_key: ContextVar[str | None] = ContextVar("current_api_key", default=None)


def extract_token_from_header(auth_header: str) -> str | None:
    """Extract a bearer value for custom API-key authentication only.

    Do not use this helper to forward an MCP resource token to another API.
    MCP tokens are audience-bound credentials for this resource server.

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
    """Get a caller-provided key in explicit custom API-key mode.

    This helper does not expose credentials verified by FastMCP JWT/OAuth
    authentication. A custom API key may be used upstream only when that key
    was explicitly issued for the upstream API.

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


@dataclass(frozen=True)
class CallerAuth:
    """Non-secret identity metadata from a verified MCP access token."""

    client_id: str
    scopes: tuple[str, ...]
    subject: str | None
    resource: str | None


def get_caller_auth() -> CallerAuth | None:
    """Inspect verified caller identity without exposing the bearer token.

    The inbound MCP resource token is intentionally omitted and must never be
    forwarded to an upstream API. Use a separately configured upstream
    credential or an OAuth token-exchange/delegation flow instead.
    """
    try:
        from fastmcp.server.dependencies import get_access_token

        access_token = get_access_token()
    except (ImportError, RuntimeError):
        return None

    if access_token is None:
        return None

    return CallerAuth(
        client_id=access_token.client_id,
        scopes=tuple(access_token.scopes),
        subject=access_token.subject,
        resource=access_token.resource,
    )
