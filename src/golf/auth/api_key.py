"""API Key authentication support for Golf MCP servers.

This module provides a simple API key pass-through mechanism for Golf servers,
allowing tools to access API keys from request headers and forward them to
upstream services.
"""

from pydantic import BaseModel, Field


class ApiKeyConfig(BaseModel):
    """Configuration for API key authentication."""

    header_name: str = Field("X-API-Key", description="Name of the header containing the API key")
    header_prefix: str = Field(
        "",
        description="Optional prefix to strip from the header value (e.g., 'Bearer ')",
    )
    required: bool = Field(True, description="Whether API key is required for all requests")


# Global configuration storage
_api_key_config: ApiKeyConfig | None = None


def configure_api_key(header_name: str = "X-API-Key", header_prefix: str = "", required: bool = True) -> None:
    """Configure API key extraction from request headers.

    This function should be called in auth.py to set up API key handling.

    Args:
        header_name: Name of the header containing the API key (default: "X-API-Key")
        header_prefix: Optional prefix to strip from the header value (e.g., "Bearer ")
        required: Whether API key is required for all requests (default: True)

    Example:
        # In auth.py
        from golf.auth.api_key import configure_api_key

        # Require API key for all requests
        configure_api_key(
            header_name="Authorization",
            header_prefix="Bearer ",
            required=True
        )

        # Or make API key optional (pass-through mode)
        configure_api_key(
            header_name="Authorization",
            header_prefix="Bearer ",
            required=False
        )
    """
    global _api_key_config
    _api_key_config = ApiKeyConfig(header_name=header_name, header_prefix=header_prefix, required=required)


def get_api_key_config() -> ApiKeyConfig | None:
    """Get the current API key configuration.

    Returns:
        The API key configuration if set, None otherwise
    """
    return _api_key_config


def is_api_key_configured() -> bool:
    """Check if API key authentication is configured.

    Returns:
        True if API key authentication is configured, False otherwise
    """
    return _api_key_config is not None
