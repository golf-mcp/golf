"""Modern authentication provider configurations for Golf MCP servers.

This module provides configuration classes for FastMCP 2.11+ authentication providers,
replacing the legacy custom OAuth implementation with the new built-in auth system.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class JWTAuthConfig(BaseModel):
    """Configuration for JWT token verification using FastMCP's JWTVerifier.

    Use this when you have JWT tokens issued by an external OAuth server
    (like Auth0, Okta, etc.) and want to verify them in your Golf server.
    """

    provider_type: Literal["jwt"] = "jwt"

    # JWT verification settings
    public_key: str | None = Field(None, description="PEM-encoded public key for JWT verification")
    jwks_uri: str | None = Field(None, description="URI to fetch JSON Web Key Set for verification")
    issuer: str | None = Field(None, description="Expected JWT issuer claim")
    audience: str | list[str] | None = Field(None, description="Expected JWT audience claim(s)")
    algorithm: str = Field("RS256", description="JWT signing algorithm")

    # Scope and access control
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required for all requests")

    # Environment variable names for runtime configuration
    public_key_env_var: str | None = Field(None, description="Environment variable name for public key")
    jwks_uri_env_var: str | None = Field(None, description="Environment variable name for JWKS URI")
    issuer_env_var: str | None = Field(None, description="Environment variable name for issuer")
    audience_env_var: str | None = Field(None, description="Environment variable name for audience")


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


# Union type for all auth configurations
AuthConfig = JWTAuthConfig | StaticTokenConfig | OAuthServerConfig | RemoteAuthConfig
