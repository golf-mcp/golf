"""Modern authentication for Golf MCP servers using FastMCP 2.11+ providers.

This module provides authentication configuration and utilities for Golf servers,
leveraging FastMCP's built-in authentication system with JWT verification,
OAuth providers, and token management.
"""

from typing import Any

# Modern auth provider configurations and factory functions
from .providers import (
    AuthConfig,
    JWTAuthConfig,
    StaticTokenConfig,
    OAuthServerConfig,
    RemoteAuthConfig,
    OAuthProxyConfig,
)
from .factory import (
    create_auth_provider,
    create_simple_jwt_provider,
    create_dev_token_provider,
)
from .registry import (
    BaseProviderPlugin,
    AuthProviderFactory,
    get_provider_registry,
    register_provider_factory,
    register_provider_plugin,
)

# Re-export for backward compatibility
from .api_key import configure_api_key, get_api_key_config, is_api_key_configured
from .helpers import (
    debug_api_key_context,
    extract_token_from_header,
    get_api_key,
    get_provider_token,
    set_api_key,
)

# Public API
__all__ = [
    # Main configuration functions
    "configure_auth",
    "configure_jwt_auth",
    "configure_dev_auth",
    "configure_oauth_proxy",
    "get_auth_config",
    # Provider configurations
    "AuthConfig",
    "JWTAuthConfig",
    "StaticTokenConfig",
    "OAuthServerConfig",
    "RemoteAuthConfig",
    "OAuthProxyConfig",
    # Factory functions
    "create_auth_provider",
    "create_simple_jwt_provider",
    "create_dev_token_provider",
    # Provider registry and plugins
    "BaseProviderPlugin",
    "AuthProviderFactory",
    "get_provider_registry",
    "register_provider_factory",
    "register_provider_plugin",
    # API key functions (backward compatibility)
    "configure_api_key",
    "get_api_key_config",
    "is_api_key_configured",
    # Helper functions
    "debug_api_key_context",
    "extract_token_from_header",
    "get_api_key",
    "get_provider_token",
    "set_api_key",
]

# Global storage for auth configuration
_auth_config: AuthConfig | None = None


def configure_auth(config: AuthConfig) -> None:
    """Configure authentication for the Golf server.

    This function should be called in auth.py to set up authentication
    using FastMCP's modern auth providers.

    Args:
        config: Authentication configuration (JWT, OAuth, Static, or Remote)
                The required_scopes should be specified in the config itself.

    Examples:
        # JWT authentication with Auth0
        from golf.auth import configure_auth, JWTAuthConfig

        configure_auth(
            JWTAuthConfig(
                jwks_uri="https://your-domain.auth0.com/.well-known/jwks.json",
                issuer="https://your-domain.auth0.com/",
                audience="https://your-api.example.com",
                required_scopes=["read:data"],
            )
        )

        # Development with static tokens
        from golf.auth import configure_auth, StaticTokenConfig

        configure_auth(
            StaticTokenConfig(
                tokens={
                    "dev-token-123": {
                        "client_id": "dev-client",
                        "scopes": ["read", "write"],
                    }
                },
                required_scopes=["read"],
            )
        )

        # Full OAuth server
        from golf.auth import configure_auth, OAuthServerConfig

        configure_auth(
            OAuthServerConfig(
                base_url="https://your-server.example.com",
                valid_scopes=["read", "write", "admin"],
                default_scopes=["read"],
                required_scopes=["read"],
            )
        )
    """
    global _auth_config
    _auth_config = config


def configure_jwt_auth(
    *,
    jwks_uri: str | None = None,
    public_key: str | None = None,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    required_scopes: list[str] | None = None,
    **env_vars: str,
) -> None:
    """Convenience function to configure JWT authentication.

    Args:
        jwks_uri: JWKS URI for key fetching
        public_key: Static public key (PEM format)
        issuer: Expected issuer claim
        audience: Expected audience claim(s)
        required_scopes: Required scopes for all requests
        **env_vars: Environment variable names (public_key_env_var,
            jwks_uri_env_var, etc.)
    """
    config = JWTAuthConfig(
        jwks_uri=jwks_uri,
        public_key=public_key,
        issuer=issuer,
        audience=audience,
        required_scopes=required_scopes or [],
        **env_vars,
    )
    configure_auth(config)


def configure_dev_auth(
    tokens: dict[str, Any] | None = None,
    required_scopes: list[str] | None = None,
) -> None:
    """Convenience function to configure development authentication.

    Args:
        tokens: Token dictionary or None for defaults
        required_scopes: Required scopes for all requests
    """
    if tokens is None:
        tokens = {
            "dev-token-123": {
                "client_id": "dev-client",
                "scopes": ["read", "write"],
            },
            "admin-token-456": {
                "client_id": "admin-client",
                "scopes": ["read", "write", "admin"],
            },
        }

    config = StaticTokenConfig(
        tokens=tokens,
        required_scopes=required_scopes or [],
    )
    configure_auth(config)


def configure_oauth_proxy(
    upstream_authorization_endpoint: str,
    upstream_token_endpoint: str,
    upstream_client_id: str,
    upstream_client_secret: str,
    base_url: str,
    token_verifier_config: JWTAuthConfig | StaticTokenConfig,
    scopes_supported: list[str] | None = None,
    upstream_revocation_endpoint: str | None = None,
    redirect_path: str = "/oauth/callback",
) -> None:
    """Configure OAuth proxy authentication for non-DCR providers.

    This sets up an OAuth proxy that bridges MCP clients (expecting DCR) with
    traditional OAuth providers like GitHub, Google, Okta Web Apps that use
    fixed client credentials.

    Args:
        upstream_authorization_endpoint: Provider's authorization URL
        upstream_token_endpoint: Provider's token endpoint URL
        upstream_client_id: Your client ID registered with the provider
        upstream_client_secret: Your client secret from the provider
        base_url: This proxy server's public URL
        token_verifier_config: JWT or static token config for token verification
        scopes_supported: Scopes to advertise to MCP clients
        upstream_revocation_endpoint: Optional token revocation endpoint
        redirect_path: OAuth callback path (default: /oauth/callback)

    Note:
        Requires golf-mcp-enterprise package for implementation.
    """
    config = OAuthProxyConfig(
        upstream_authorization_endpoint=upstream_authorization_endpoint,
        upstream_token_endpoint=upstream_token_endpoint,
        upstream_client_id=upstream_client_id,
        upstream_client_secret=upstream_client_secret,
        upstream_revocation_endpoint=upstream_revocation_endpoint,
        base_url=base_url,
        redirect_path=redirect_path,
        scopes_supported=scopes_supported or [],
        token_verifier_config=token_verifier_config,
    )
    configure_auth(config)


def get_auth_config() -> AuthConfig | None:
    """Get the current auth configuration.

    Returns:
        AuthConfig if configured, None otherwise
    """
    return _auth_config


def is_auth_configured() -> bool:
    """Check if authentication is configured.

    Returns:
        True if authentication is configured, False otherwise
    """
    return _auth_config is not None


# Breaking change in Golf 0.2.x: Legacy auth system removed
# Users must migrate to modern auth configurations


def create_auth_provider_from_config() -> object | None:
    """Create an auth provider from the current configuration.

    Returns:
        FastMCP AuthProvider instance or None if not configured
    """
    config = get_auth_config()
    if not config:
        return None

    return create_auth_provider(config)
