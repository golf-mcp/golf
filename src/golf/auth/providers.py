"""Modern authentication provider configurations for Golf MCP servers.

This module provides configuration classes for FastMCP 2.11+ authentication providers,
replacing the legacy custom OAuth implementation with the new built-in auth system.
"""

import os
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class JWTAuthConfig(BaseModel):
    """Configuration for JWT token verification using FastMCP's JWTVerifier.

    Use this when you have JWT tokens issued by an external OAuth server
    (like Auth0, Okta, etc.) and want to verify them in your Golf server.

    Security Note:
        For production use, it's strongly recommended to specify both `issuer` and `audience`
        to ensure tokens are validated against the expected issuer and intended audience.
        This prevents token misuse across different services or environments.
    """

    provider_type: Literal["jwt"] = "jwt"

    # JWT verification settings
    public_key: str | None = Field(None, description="PEM-encoded public key for JWT verification")
    jwks_uri: str | None = Field(None, description="URI to fetch JSON Web Key Set for verification")
    issuer: str | None = Field(None, description="Expected JWT issuer claim (strongly recommended for production)")
    audience: str | list[str] | None = Field(
        None, description="Expected JWT audience claim(s) (strongly recommended for production)"
    )
    algorithm: str = Field("RS256", description="JWT signing algorithm")

    # Scope and access control
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required for all requests")

    # Environment variable names for runtime configuration
    public_key_env_var: str | None = Field(None, description="Environment variable name for public key")
    jwks_uri_env_var: str | None = Field(None, description="Environment variable name for JWKS URI")
    issuer_env_var: str | None = Field(None, description="Environment variable name for issuer")
    audience_env_var: str | None = Field(None, description="Environment variable name for audience")

    @model_validator(mode="after")
    def validate_jwt_config(self) -> "JWTAuthConfig":
        """Validate JWT configuration requirements."""
        # Ensure exactly one of public_key or jwks_uri is provided
        if not self.public_key and not self.jwks_uri and not self.public_key_env_var and not self.jwks_uri_env_var:
            raise ValueError("Either public_key, jwks_uri, or their environment variable equivalents must be provided")
        
        if (self.public_key or self.public_key_env_var) and (self.jwks_uri or self.jwks_uri_env_var):
            raise ValueError("Provide either public_key or jwks_uri (or their env vars), not both")

        # Warn about missing issuer/audience in production-like environments
        is_production = os.environ.get("GOLF_ENV", "").lower() in ("prod", "production") or \
                       os.environ.get("NODE_ENV", "").lower() == "production" or \
                       os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
        
        if is_production:
            missing_fields = []
            if not self.issuer and not self.issuer_env_var:
                missing_fields.append("issuer")
            if not self.audience and not self.audience_env_var:
                missing_fields.append("audience")
            
            if missing_fields:
                import warnings
                warnings.warn(
                    f"JWT configuration is missing recommended fields for production: {', '.join(missing_fields)}. "
                    "This may allow tokens from unintended issuers or audiences to be accepted.",
                    UserWarning,
                    stacklevel=2
                )
        
        return self


class StaticTokenConfig(BaseModel):
    """Configuration for static token verification for development/testing.

    Use this for local development and testing when you need predictable
    API keys without setting up a full OAuth server.

    WARNING: Never use in production!
    """

    provider_type: Literal["static"] = "static"

    # Static tokens mapping: token_string -> metadata
    tokens: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Static tokens with their metadata (client_id, scopes, expires_at)",
    )

    # Scope and access control
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required for all requests")


class OAuthServerConfig(BaseModel):
    """Configuration for full OAuth authorization server using FastMCP's OAuthProvider.

    Use this when you want your Golf server to act as a complete OAuth server,
    handling client registration, authorization flows, and token issuance.
    """

    provider_type: Literal["oauth_server"] = "oauth_server"

    # OAuth server URLs
    base_url: str = Field(..., description="Public URL of this Golf server")
    issuer_url: str | None = Field(None, description="OAuth issuer URL (defaults to base_url)")
    service_documentation_url: str | None = Field(None, description="URL of service documentation")

    # Client registration settings
    allow_client_registration: bool = Field(True, description="Allow dynamic client registration")
    valid_scopes: list[str] = Field(default_factory=list, description="Valid scopes for client registration")
    default_scopes: list[str] = Field(default_factory=list, description="Default scopes for new clients")

    # Token revocation settings
    allow_token_revocation: bool = Field(True, description="Allow token revocation")

    # Access control
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required for all requests")

    # Environment variable names for runtime configuration
    base_url_env_var: str | None = Field(None, description="Environment variable name for base URL")


class RemoteAuthConfig(BaseModel):
    """Configuration for remote authorization server integration.

    Use this when you have token verification logic and want to advertise
    the authorization servers that issue valid tokens (RFC 9728 compliance).
    """

    provider_type: Literal["remote"] = "remote"

    # Authorization servers that issue tokens
    authorization_servers: list[str] = Field(
        ..., description="List of authorization server URLs that issue valid tokens"
    )

    # This server's URL
    resource_server_url: str = Field(..., description="URL of this resource server")

    # Token verification (delegate to another config)
    token_verifier_config: JWTAuthConfig | StaticTokenConfig = Field(
        ..., description="Configuration for the underlying token verifier"
    )

    # Environment variable names for runtime configuration
    authorization_servers_env_var: str | None = Field(
        None, description="Environment variable name for comma-separated authorization server URLs"
    )
    resource_server_url_env_var: str | None = Field(
        None, description="Environment variable name for resource server URL"
    )

    @field_validator("authorization_servers")
    @classmethod
    def validate_authorization_servers(cls, v: list[str]) -> list[str]:
        """Validate authorization servers are non-empty and valid URLs."""
        if not v:
            raise ValueError(
                "authorization_servers cannot be empty - at least one authorization server URL is required"
            )
        
        valid_urls = []
        for url in v:
            url = url.strip()
            if not url:
                raise ValueError("authorization_servers cannot contain empty URLs")
            
            # Validate URL format
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError(
                        f"Invalid URL format for authorization server: '{url}' - must include scheme and netloc"
                    )
                if parsed.scheme not in ("http", "https"):
                    raise ValueError(f"Authorization server URL must use http or https scheme: '{url}'")
            except Exception as e:
                raise ValueError(f"Invalid authorization server URL '{url}': {e}") from e
            
            valid_urls.append(url)
        
        return valid_urls

    @field_validator("resource_server_url")
    @classmethod
    def validate_resource_server_url(cls, v: str) -> str:
        """Validate resource server URL is a valid URL."""
        if not v or not v.strip():
            raise ValueError("resource_server_url cannot be empty")
        
        url = v.strip()
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(
                    f"Invalid URL format for resource server: '{url}' - must include scheme and netloc"
                )
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Resource server URL must use http or https scheme: '{url}'")
        except Exception as e:
            raise ValueError(f"Invalid resource server URL '{url}': {e}") from e
        
        return url

    @model_validator(mode="after")
    def validate_token_verifier_compatibility(self) -> "RemoteAuthConfig":
        """Validate that the token verifier config is compatible with token verification."""
        # The duck-typing check is already handled by the factory function, but we can
        # add a basic sanity check here that the config types are ones we know work
        config = self.token_verifier_config
        
        if not isinstance(config, JWTAuthConfig | StaticTokenConfig):
            raise ValueError(
                f"token_verifier_config must be JWTAuthConfig or StaticTokenConfig, got {type(config).__name__}"
            )
        
        # For JWT configs, ensure they have the minimum required fields
        if isinstance(config, JWTAuthConfig) and (
            not config.public_key and not config.jwks_uri and 
            not config.public_key_env_var and not config.jwks_uri_env_var
        ):
            raise ValueError(
                "JWT token verifier config must provide public_key, jwks_uri, or their environment variable equivalents"
            )
        
        # For static token configs, ensure they have tokens
        if isinstance(config, StaticTokenConfig) and not config.tokens:
            raise ValueError("Static token verifier config must provide at least one token")
        
        return self


# Union type for all auth configurations
AuthConfig = JWTAuthConfig | StaticTokenConfig | OAuthServerConfig | RemoteAuthConfig
