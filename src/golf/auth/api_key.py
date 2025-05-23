"""API Key authentication support for Golf MCP servers.

This module provides a simple API key pass-through mechanism for Golf servers,
allowing tools to access API keys from request headers and forward them to
upstream services.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ApiKeyConfig(BaseModel):
    """Configuration for API key authentication."""
    
    header_name: str = Field(
        "X-API-Key",
        description="Name of the header containing the API key"
    )
    header_prefix: str = Field(
        "",
        description="Optional prefix to strip from the header value (e.g., 'Bearer ')"
    )


# Global configuration storage
_api_key_config: Optional[ApiKeyConfig] = None


def configure_api_key(
    header_name: str = "X-API-Key",
    header_prefix: str = ""
) -> None:
    """Configure API key extraction from request headers.
    
    This function should be called in pre_build.py to set up API key handling.
    
    Args:
        header_name: Name of the header containing the API key (default: "X-API-Key")
        header_prefix: Optional prefix to strip from the header value (e.g., "Bearer ")
        case_sensitive: Whether header name matching should be case-sensitive
        
    Example:
        # In pre_build.py
        from golf.auth.api_key import configure_api_key
        
        configure_api_key(
            header_name="Authorization",
            header_prefix="Bearer "
        )
    """
    global _api_key_config
    _api_key_config = ApiKeyConfig(
        header_name=header_name,
        header_prefix=header_prefix
    )


def get_api_key_config() -> Optional[ApiKeyConfig]:
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