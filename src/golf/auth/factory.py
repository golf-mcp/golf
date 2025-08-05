"""Factory functions for creating FastMCP authentication providers."""

import os
from typing import Any

# Import these at runtime to avoid import errors during Golf installation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from fastmcp.server.auth.providers.jwt import JWTVerifier, StaticTokenVerifier
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions

from .providers import (
    AuthConfig,
    JWTAuthConfig,
    StaticTokenConfig,
    OAuthServerConfig,
    RemoteAuthConfig,
)


def create_auth_provider(config: AuthConfig) -> "AuthProvider":
    """Create a FastMCP AuthProvider from Golf auth configuration.
    
    Args:
        config: Golf authentication configuration
        
    Returns:
        Configured FastMCP AuthProvider instance
        
    Raises:
        ValueError: If configuration is invalid
        ImportError: If required dependencies are missing
    """
    if config.provider_type == "jwt":
        return _create_jwt_provider(config)
    elif config.provider_type == "static":
        return _create_static_provider(config)
    elif config.provider_type == "oauth_server":
        return _create_oauth_server_provider(config)
    elif config.provider_type == "remote":
        return _create_remote_provider(config)
    else:
        raise ValueError(f"Unknown provider type: {config.provider_type}")


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
        from fastmcp.server.auth.providers.jwt import JWTVerifier
    except ImportError:
        raise ImportError(
            "JWTVerifier not available. Please install fastmcp>=2.11.0"
        )
    
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
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
    except ImportError:
        raise ImportError(
            "StaticTokenVerifier not available. Please install fastmcp>=2.11.0"
        )
    
    return StaticTokenVerifier(
        tokens=config.tokens,
        required_scopes=config.required_scopes,
    )


def _create_oauth_server_provider(config: OAuthServerConfig) -> "AuthProvider":
    """Create OAuth authorization server provider from configuration."""
    try:
        from fastmcp.server.auth import OAuthProvider
    except ImportError:
        raise ImportError(
            "OAuthProvider not available in this FastMCP version. "
            "Please upgrade to FastMCP 2.11.0 or later."
        )
    
    # Resolve runtime values from environment variables
    base_url = config.base_url
    if config.base_url_env_var:
        env_value = os.environ.get(config.base_url_env_var)
        if env_value:
            base_url = env_value
    
    # Create client registration options
    client_reg_options = None
    if config.allow_client_registration:
        client_reg_options = ClientRegistrationOptions(
            enabled=True,
            valid_scopes=config.valid_scopes,
            default_scopes=config.default_scopes,
        )
    
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
    except ImportError:
        raise ImportError(
            "RemoteAuthProvider not available in this FastMCP version. "
            "Please upgrade to FastMCP 2.11.0 or later."
        )
    
    # Create the underlying token verifier
    token_verifier = create_auth_provider(config.token_verifier_config)
    
    # Ensure it's actually a TokenVerifier
    if not hasattr(token_verifier, 'verify_token'):
        raise ValueError(
            "Remote auth provider requires a TokenVerifier, "
            f"got {type(token_verifier).__name__}"
        )
    
    return RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[config.authorization_servers],
        resource_server_url=config.resource_server_url,
    )


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