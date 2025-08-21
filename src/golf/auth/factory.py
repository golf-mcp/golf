"""Factory functions for creating FastMCP authentication providers."""

import os
from typing import Any

# Import these at runtime to avoid import errors during Golf installation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.server.auth.auth import AuthProvider
    from fastmcp.server.auth import JWTVerifier, StaticTokenVerifier
from mcp.server.auth.settings import RevocationOptions

from .providers import (
    AuthConfig,
    JWTAuthConfig,
    StaticTokenConfig,
    OAuthServerConfig,
    RemoteAuthConfig,
    OAuthProxyConfig,
)
from .registry import (
    get_provider_registry,
    create_auth_provider_from_registry,
)


def create_auth_provider(config: AuthConfig) -> "AuthProvider":
    """Create a FastMCP AuthProvider from Golf auth configuration.

    This function uses the provider registry system to allow extensibility.
    Built-in providers are automatically registered, and custom providers
    can be added via the registry system.

    Args:
        config: Golf authentication configuration

    Returns:
        Configured FastMCP AuthProvider instance

    Raises:
        ValueError: If configuration is invalid
        ImportError: If required dependencies are missing
        KeyError: If provider type is not registered
    """
    try:
        return create_auth_provider_from_registry(config)
    except KeyError:
        # Fall back to legacy dispatch for backward compatibility
        # This ensures existing code continues to work during transition
        if config.provider_type == "jwt":
            return _create_jwt_provider(config)
        elif config.provider_type == "static":
            return _create_static_provider(config)
        elif config.provider_type == "oauth_server":
            return _create_oauth_server_provider(config)
        elif config.provider_type == "remote":
            return _create_remote_provider(config)
        elif config.provider_type == "oauth_proxy":
            return _create_oauth_proxy_provider(config)
        else:
            raise ValueError(f"Unknown provider type: {config.provider_type}") from None


def _create_jwt_provider(config: JWTAuthConfig) -> "JWTVerifier":
    """Create JWT token verifier from configuration."""
    # Resolve runtime values from environment variables
    public_key = config.public_key
    if config.public_key_env_var:
        env_value = os.environ.get(config.public_key_env_var)
        if env_value:
            public_key = env_value

    jwks_uri = config.jwks_uri
    if config.jwks_uri_env_var:
        env_value = os.environ.get(config.jwks_uri_env_var)
        if env_value:
            jwks_uri = env_value

    issuer = config.issuer
    if config.issuer_env_var:
        env_value = os.environ.get(config.issuer_env_var)
        if env_value:
            issuer = env_value

    audience = config.audience
    if config.audience_env_var:
        env_value = os.environ.get(config.audience_env_var)
        if env_value:
            # Handle both string and comma-separated list
            if "," in env_value:
                audience = [s.strip() for s in env_value.split(",")]
            else:
                audience = env_value

    # Validate configuration
    if not public_key and not jwks_uri:
        raise ValueError("Either public_key or jwks_uri must be provided for JWT verification")

    if public_key and jwks_uri:
        raise ValueError("Provide either public_key or jwks_uri, not both")

    try:
        from fastmcp.server.auth import JWTVerifier
    except ImportError as e:
        raise ImportError("JWTVerifier not available. Please install fastmcp>=2.11.0") from e

    return JWTVerifier(
        public_key=public_key,
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=audience,
        algorithm=config.algorithm,
        required_scopes=config.required_scopes,
    )


def _create_static_provider(config: StaticTokenConfig) -> "StaticTokenVerifier":
    """Create static token verifier from configuration."""
    if not config.tokens:
        raise ValueError("Static token provider requires at least one token")

    try:
        from fastmcp.server.auth import StaticTokenVerifier
    except ImportError as e:
        raise ImportError("StaticTokenVerifier not available. Please install fastmcp>=2.11.0") from e

    return StaticTokenVerifier(
        tokens=config.tokens,
        required_scopes=config.required_scopes,
    )


def _create_oauth_server_provider(config: OAuthServerConfig) -> "AuthProvider":
    """Create OAuth authorization server provider from configuration."""
    try:
        from fastmcp.server.auth import OAuthProvider
    except ImportError as e:
        raise ImportError(
            "OAuthProvider not available in this FastMCP version. Please upgrade to FastMCP 2.11.0 or later."
        ) from e

    # Resolve runtime values from environment variables with validation
    base_url = config.base_url
    if config.base_url_env_var:
        env_value = os.environ.get(config.base_url_env_var)
        if env_value:
            # Apply the same validation as the config field to env var value
            try:
                from urllib.parse import urlparse

                env_value = env_value.strip()
                parsed = urlparse(env_value)

                if not parsed.scheme or not parsed.netloc:
                    raise ValueError(
                        f"Invalid base URL from environment variable {config.base_url_env_var}: '{env_value}'"
                    )

                if parsed.scheme not in ("http", "https"):
                    raise ValueError(f"Base URL from environment must use http/https: '{env_value}'")

                # Production HTTPS check
                is_production = (
                    os.environ.get("GOLF_ENV", "").lower() in ("prod", "production")
                    or os.environ.get("NODE_ENV", "").lower() == "production"
                    or os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
                )

                if is_production and parsed.scheme == "http":
                    raise ValueError(f"Base URL must use HTTPS in production: '{env_value}'")

                base_url = env_value

            except Exception as e:
                raise ValueError(f"Invalid base URL from environment variable {config.base_url_env_var}: {e}") from e

    # Additional security validations before creating provider
    from urllib.parse import urlparse

    # Validate final base_url
    parsed_base = urlparse(base_url)
    if not parsed_base.scheme or not parsed_base.netloc:
        raise ValueError(f"Invalid base URL: '{base_url}'")

    # Security check: prevent localhost in production
    is_production = (
        os.environ.get("GOLF_ENV", "").lower() in ("prod", "production")
        or os.environ.get("NODE_ENV", "").lower() == "production"
        or os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
    )

    if is_production and parsed_base.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        raise ValueError(f"Cannot use localhost/loopback addresses in production: '{base_url}'")

    # Client registration options - always disabled for security
    client_reg_options = None

    # Create revocation options
    revocation_options = None
    if config.allow_token_revocation:
        revocation_options = RevocationOptions(enabled=True)

    return OAuthProvider(
        base_url=base_url,
        issuer_url=config.issuer_url,
        service_documentation_url=config.service_documentation_url,
        client_registration_options=client_reg_options,
        revocation_options=revocation_options,
        required_scopes=config.required_scopes,
    )


def _create_remote_provider(config: RemoteAuthConfig) -> "AuthProvider":
    """Create remote auth provider from configuration."""
    try:
        from fastmcp.server.auth import RemoteAuthProvider
    except ImportError as e:
        raise ImportError(
            "RemoteAuthProvider not available in this FastMCP version. Please upgrade to FastMCP 2.11.0 or later."
        ) from e

    # Resolve runtime values from environment variables
    authorization_servers = config.authorization_servers
    if config.authorization_servers_env_var:
        env_value = os.environ.get(config.authorization_servers_env_var)
        if env_value:
            # Split comma-separated values and strip whitespace
            authorization_servers = [s.strip() for s in env_value.split(",")]

    resource_server_url = config.resource_server_url
    if config.resource_server_url_env_var:
        env_value = os.environ.get(config.resource_server_url_env_var)
        if env_value:
            resource_server_url = env_value

    # Create the underlying token verifier
    token_verifier = create_auth_provider(config.token_verifier_config)

    # Ensure it's actually a TokenVerifier
    if not hasattr(token_verifier, "verify_token"):
        raise ValueError(f"Remote auth provider requires a TokenVerifier, got {type(token_verifier).__name__}")

    # Update token verifier's required_scopes to match our scopes_supported for PRM
    # RemoteAuthProvider uses token_verifier.required_scopes for scopes_supported in PRM
    if config.scopes_supported and hasattr(token_verifier, "required_scopes"):
        token_verifier.required_scopes = list(config.scopes_supported)

    return RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=authorization_servers,
        resource_server_url=resource_server_url,
    )


def _create_oauth_proxy_provider(config: OAuthProxyConfig) -> "AuthProvider":
    """Create OAuth proxy provider - requires enterprise package."""
    try:
        # Try to import from enterprise package
        from golf_enterprise import create_oauth_proxy_provider

        return create_oauth_proxy_provider(config)
    except ImportError as e:
        raise ImportError(
            "OAuth Proxy requires golf-mcp-enterprise package. "
            "This feature provides OAuth proxy functionality for non-DCR providers "
            "(GitHub, Google, Okta Web Apps, etc.). "
            "Contact sales@golf.dev for enterprise licensing."
        ) from e


def create_simple_jwt_provider(
    *,
    jwks_uri: str | None = None,
    public_key: str | None = None,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    required_scopes: list[str] | None = None,
) -> "JWTVerifier":
    """Create a simple JWT provider for common use cases.

    This is a convenience function for creating JWT providers without
    having to construct the full configuration objects.

    Args:
        jwks_uri: JWKS URI for key fetching
        public_key: Static public key (PEM format)
        issuer: Expected issuer claim
        audience: Expected audience claim(s)
        required_scopes: Required scopes for all requests

    Returns:
        Configured JWTVerifier instance
    """
    config = JWTAuthConfig(
        jwks_uri=jwks_uri,
        public_key=public_key,
        issuer=issuer,
        audience=audience,
        required_scopes=required_scopes or [],
    )
    return _create_jwt_provider(config)


def create_dev_token_provider(
    tokens: dict[str, Any] | None = None,
    required_scopes: list[str] | None = None,
) -> "StaticTokenVerifier":
    """Create a static token provider for development.

    Args:
        tokens: Token dictionary or None for default dev tokens
        required_scopes: Required scopes for all requests

    Returns:
        Configured StaticTokenVerifier instance
    """
    if tokens is None:
        # Default development tokens
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
    return _create_static_provider(config)


def register_builtin_providers() -> None:
    """Register built-in authentication providers in the registry.

    This function registers the standard Golf authentication providers:
    - jwt: JWT token verification
    - static: Static token verification (development)
    - oauth_server: Full OAuth authorization server
    - remote: Remote authorization server integration

    Note: oauth_proxy provider is registered by the golf-mcp-enterprise package
    """
    registry = get_provider_registry()

    # Register built-in provider factories
    registry.register_factory("jwt", _create_jwt_provider)
    registry.register_factory("static", _create_static_provider)
    registry.register_factory("oauth_server", _create_oauth_server_provider)
    registry.register_factory("remote", _create_remote_provider)
    # oauth_proxy is registered by golf-mcp-enterprise package when installed


# Register built-in providers when module is imported
register_builtin_providers()
