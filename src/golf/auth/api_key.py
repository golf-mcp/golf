"""Deprecated caller API-key extraction for Golf MCP servers.

This module is not MCP authentication. It extracts a caller-provided header so
tools can forward that credential to an upstream API, which is responsible for
validating it. Golf does not compare the value against any expected secret.

Never configure this as a way to expose or forward inbound MCP resource tokens
to upstream services. Prefer FastMCP JWT/OAuth authentication instead.
"""

from __future__ import annotations

import warnings
from collections.abc import Awaitable, Callable, Mapping

from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_UNPROTECTED_PATHS = frozenset({"/metrics", "/health"})

_DEPRECATION_MESSAGE = (
    "configure_api_key() is deprecated and is not MCP authentication. "
    "It only extracts a caller-provided header for get_api_key() so tools can "
    "forward that credential to an upstream API, which is responsible for "
    "validating it. Golf does not verify API key values. Use configure_jwt_auth() "
    "or configure_dev_auth() to authenticate MCP clients. This helper will be "
    "removed in a future release."
)


class ApiKeyConfig(BaseModel):
    """Configuration for deprecated caller API-key header extraction."""

    header_name: str = Field("X-API-Key", description="Name of the header containing the API key")
    header_prefix: str = Field(
        "",
        description="Optional prefix to strip from the header value (e.g., 'Bearer ')",
    )
    required: bool = Field(True, description="Whether the header must be present on inbound requests")


# Global configuration storage
_api_key_config: ApiKeyConfig | None = None


def configure_api_key(header_name: str = "X-API-Key", header_prefix: str = "", required: bool = True) -> None:
    """Extract a caller-provided API key from request headers.

    Deprecated: this is not MCP-server authentication. The extracted value is
    made available to tools via ``get_api_key()`` so they can call an upstream
    API. That upstream service validates the key. Golf never checks the value.

    Args:
        header_name: Name of the header containing the API key (default: "X-API-Key")
        header_prefix: Optional prefix to strip from the header value (e.g., "Bearer ")
        required: Whether the header must be present for all requests (default: True)

    Example:
        # In auth.py — prefer JWT/OAuth instead of this helper
        from golf.auth.api_key import configure_api_key

        configure_api_key(
            header_name="Authorization",
            header_prefix="Bearer ",
            required=True,
        )
    """
    warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)

    global _api_key_config
    _api_key_config = ApiKeyConfig(header_name=header_name, header_prefix=header_prefix, required=required)


def get_api_key_config() -> ApiKeyConfig | None:
    """Get the current API key extraction configuration.

    Returns:
        The API key configuration if set, None otherwise
    """
    return _api_key_config


def is_api_key_configured() -> bool:
    """Check if deprecated API key header extraction is configured.

    Returns:
        True if API key extraction is configured, False otherwise
    """
    return _api_key_config is not None


def reset_api_key_config() -> None:
    """Clear process-global API key configuration.

    The builder calls this before loading a project's auth.py so one project
    cannot inherit another project's API-key settings.
    """
    global _api_key_config
    _api_key_config = None


def extract_api_key_from_headers(headers: Mapping[str, str], config: ApiKeyConfig) -> str | None:
    """Extract and normalize the API key from request headers."""
    raw: str | None = None
    for name, value in headers.items():
        if name.lower() == config.header_name.lower():
            raw = value
            break

    if raw is None:
        return None

    if config.header_prefix and raw.startswith(config.header_prefix):
        raw = raw[len(config.header_prefix) :]

    stripped = raw.strip()
    return stripped or None


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Extract a caller-provided API key; do not treat the value as authenticated.

    When ``required`` is True, a missing header is rejected so tools have a
    credential to forward upstream. The value itself is not verified here.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in _UNPROTECTED_PATHS:
            return await call_next(request)

        config = get_api_key_config()
        if config is None:
            return await call_next(request)

        provided = extract_api_key_from_headers(request.headers, config)
        if provided:
            request.state.api_key = provided
            from golf.auth.helpers import set_api_key

            set_api_key(provided)

        if config.required and not provided:
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "detail": f"Missing required {config.header_name} header",
                },
                status_code=401,
                headers={"WWW-Authenticate": f'{config.header_name} realm="MCP Server"'},
            )

        return await call_next(request)
