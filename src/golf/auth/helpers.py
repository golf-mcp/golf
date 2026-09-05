"""Helper functions for working with authentication in MCP context."""

from contextvars import ContextVar
from dataclasses import dataclass


# Context variable to store the current request's API key
_current_api_key: ContextVar[str | None] = ContextVar("current_api_key", default=None)


def extract_token_from_header(auth_header: str) -> str | None:
    """Extract a bearer value for custom API-key forwarding only.

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
    """Get a caller-provided key for forwarding to an upstream API.

    This helper does not authenticate the MCP client and does not expose
    credentials verified by FastMCP JWT/OAuth authentication. The returned
    value is whatever the caller sent; the upstream API is responsible for
    validating it. Use it only when that key was explicitly issued for the
    upstream API.

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
    try:
        from fastmcp.server.dependencies import get_http_request
        from golf.auth.api_key import extract_api_key_from_headers, get_api_key_config

        request = get_http_request()

        if request and hasattr(request, "state") and hasattr(request.state, "api_key"):
            return request.state.api_key

        api_key_config = get_api_key_config()
        if api_key_config and request:
            return extract_api_key_from_headers(request.headers, api_key_config)
    except (ImportError, RuntimeError):
        pass
    except Exception:
        pass

    import os

    return os.environ.get("API_KEY")


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
