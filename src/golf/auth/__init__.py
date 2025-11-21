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
    extract_token_from_header,
    get_api_key,
    get_auth_token,
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
    "extract_token_from_header",
    "get_api_key",
    "get_auth_token",
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
    authorization_endpoint: str | None = None,
    token_endpoint: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    base_url: str | None = None,
    token_verifier_config: JWTAuthConfig | StaticTokenConfig | None = None,
    scopes_supported: list[str] | None = None,
    revocation_endpoint: str | None = None,
    redirect_path: str = "/oauth/callback",
    **env_vars: str,
) -> None:
    """Configure OAuth proxy authentication for non-DCR providers.

    All parameters can be provided either directly or via environment variables.
    For each parameter, you can provide the value directly or use the
    corresponding *_env_var parameter to specify an environment variable name.

    Examples:
        # Direct values (backward compatible)
        configure_oauth_proxy(
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            client_secret="my-secret",
            base_url="https://myserver.com",
            token_verifier_config=jwt_config,
        )

        # Environment variables only (new behavior)
        configure_oauth_proxy(
            authorization_endpoint_env_var="OAUTH_AUTH_ENDPOINT",
            token_endpoint_env_var="OAUTH_TOKEN_ENDPOINT",
            client_id_env_var="OAUTH_CLIENT_ID",
            client_secret_env_var="OAUTH_CLIENT_SECRET",
            base_url_env_var="OAUTH_BASE_URL",
            token_verifier_config=jwt_config,
        )

        # Mixed (direct values with env var overrides)
        configure_oauth_proxy(
            authorization_endpoint="https://default.example.com/authorize",
            authorization_endpoint_env_var="OAUTH_AUTH_ENDPOINT",  # Overrides at runtime
            # ...
        )

    Args:
        authorization_endpoint: OAuth provider's authorization endpoint URL
        token_endpoint: OAuth provider's token endpoint URL
        client_id: Your registered client ID with the OAuth provider
        client_secret: Your registered client secret with the OAuth provider
        base_url: Public URL of this OAuth proxy server
        token_verifier_config: JWT or Static token configuration for verifying tokens
        scopes_supported: List of OAuth scopes this proxy supports
        revocation_endpoint: Optional token revocation endpoint
        redirect_path: OAuth callback path (default: "/oauth/callback")
        **env_vars: Environment variable names for runtime configuration
            - authorization_endpoint_env_var: Env var for authorization endpoint
            - token_endpoint_env_var: Env var for token endpoint
            - client_id_env_var: Env var for client ID
            - client_secret_env_var: Env var for client secret
            - base_url_env_var: Env var for base URL
            - revocation_endpoint_env_var: Env var for revocation endpoint

    Raises:
        ValueError: If token_verifier_config is not provided or invalid
        ValueError: If required fields lack both direct value and env var
    """
    # Validate token_verifier_config is provided (always required)
    if token_verifier_config is None:
        raise ValueError("token_verifier_config is required and must be JWTAuthConfig or StaticTokenConfig")

    if not isinstance(token_verifier_config, (JWTAuthConfig, StaticTokenConfig)):
        raise ValueError(
            f"token_verifier_config must be JWTAuthConfig or StaticTokenConfig, "
            f"got {type(token_verifier_config).__name__}"
        )

    # Create config with all parameters (None values are OK now)
    config = OAuthProxyConfig(
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        client_id=client_id,
        client_secret=client_secret,
        revocation_endpoint=revocation_endpoint,
        base_url=base_url,
        redirect_path=redirect_path,
        scopes_supported=scopes_supported,
        token_verifier_config=token_verifier_config,
        **env_vars,
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
