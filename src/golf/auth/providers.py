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
        is_production = (
            os.environ.get("GOLF_ENV", "").lower() in ("prod", "production")
            or os.environ.get("NODE_ENV", "").lower() == "production"
            or os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
        )

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
                    stacklevel=2,
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
    handling authorization flows and token issuance.

    Security Considerations:
        - URLs are validated to prevent SSRF attacks
        - Scopes are validated against OAuth 2.0 standards
        - Base URL must use HTTPS in production environments
        - Client registration is disabled for security
    """

    provider_type: Literal["oauth_server"] = "oauth_server"

    # OAuth server URLs
    base_url: str = Field(..., description="Public URL of this Golf server (must use HTTPS in production)")
    issuer_url: str | None = Field(None, description="OAuth issuer URL (defaults to base_url, must be HTTPS)")
    service_documentation_url: str | None = Field(None, description="URL of service documentation")

    # Client registration settings
    valid_scopes: list[str] = Field(
        default_factory=list, description="Valid scopes for client registration (OAuth 2.0 format)"
    )
    default_scopes: list[str] = Field(default_factory=list, description="Default scopes for new clients")

    # Token revocation settings
    allow_token_revocation: bool = Field(True, description="Allow token revocation")

    # Access control
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required for all requests")

    # Environment variable names for runtime configuration
    base_url_env_var: str | None = Field(None, description="Environment variable name for base URL")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL for security and format compliance."""
        if not v or not v.strip():
            raise ValueError("base_url cannot be empty")

        url = v.strip()
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid base URL format: '{url}' - must include scheme and netloc")

            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Base URL must use http or https scheme: '{url}'")

            # Warn about HTTP in production-like environments
            is_production = (
                os.environ.get("GOLF_ENV", "").lower() in ("prod", "production")
                or os.environ.get("NODE_ENV", "").lower() == "production"
                or os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
            )

            if is_production and parsed.scheme == "http":
                import warnings

                warnings.warn(
                    f"Base URL '{url}' uses HTTP in production environment. "
                    "HTTPS is strongly recommended for OAuth servers to prevent token interception.",
                    UserWarning,
                    stacklevel=2,
                )

            # Prevent common SSRF targets
            if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
                if is_production:
                    raise ValueError(f"Base URL cannot use localhost/loopback addresses in production: '{url}'")

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid base URL '{url}': {e}") from e

        return url

    @field_validator("issuer_url", "service_documentation_url")
    @classmethod
    def validate_optional_urls(cls, v: str | None) -> str | None:
        """Validate optional URLs for security and format compliance."""
        if not v:
            return v

        url = v.strip()
        if not url:
            return None

        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL format: '{url}' - must include scheme and netloc")

            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"URL must use http or https scheme: '{url}'")

            # Check for HTTPS requirement in production for issuer URL
            if v == cls.__dict__.get("issuer_url"):  # This is the issuer_url field
                is_production = (
                    os.environ.get("GOLF_ENV", "").lower() in ("prod", "production")
                    or os.environ.get("NODE_ENV", "").lower() == "production"
                    or os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
                )

                if is_production and parsed.scheme == "http":
                    import warnings

                    warnings.warn(
                        f"Issuer URL '{url}' uses HTTP in production. HTTPS is required for OAuth issuer URLs.",
                        UserWarning,
                        stacklevel=2,
                    )

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid URL '{url}': {e}") from e

        return url

    @field_validator("valid_scopes", "default_scopes", "required_scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Validate OAuth 2.0 scopes format and security."""
        if not v:
            return v

        valid_scopes = []
        for scope in v:
            scope = scope.strip()
            if not scope:
                raise ValueError("Scopes cannot be empty or whitespace-only")

            # OAuth 2.0 scope format validation (RFC 6749)
            # Scopes should be ASCII printable characters except space, and no control characters
            if not all(32 < ord(c) < 127 and c not in ' "\\' for c in scope):
                raise ValueError(
                    f"Invalid scope format: '{scope}' - must be ASCII printable without spaces, quotes, or backslashes"
                )

            # Reasonable length limit to prevent abuse
            if len(scope) > 128:
                raise ValueError(f"Scope too long: '{scope}' - maximum 128 characters")

            # Prevent potentially dangerous scope names
            dangerous_scopes = {"admin", "root", "superuser", "system", "*", "all"}
            if scope.lower() in dangerous_scopes:
                import warnings

                warnings.warn(
                    f"Potentially dangerous scope detected: '{scope}'. "
                    "Consider using more specific, principle-of-least-privilege scopes.",
                    UserWarning,
                    stacklevel=2,
                )

            valid_scopes.append(scope)

        return valid_scopes

    @model_validator(mode="after")
    def validate_oauth_server_config(self) -> "OAuthServerConfig":
        """Validate OAuth server configuration for security and consistency."""
        # Validate default_scopes are subset of valid_scopes
        if self.default_scopes and self.valid_scopes:
            invalid_defaults = set(self.default_scopes) - set(self.valid_scopes)
            if invalid_defaults:
                raise ValueError(f"default_scopes contains invalid scopes not in valid_scopes: {invalid_defaults}")

        # Validate required_scopes are subset of valid_scopes
        if self.required_scopes and self.valid_scopes:
            invalid_required = set(self.required_scopes) - set(self.valid_scopes)
            if invalid_required:
                raise ValueError(f"required_scopes contains invalid scopes not in valid_scopes: {invalid_required}")

        return self


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

    # Scopes this resource supports (advertised via /.well-known/oauth-protected-resource)
    scopes_supported: list[str] = Field(
        default_factory=list,
        description="Scopes this resource supports (advertised via /.well-known/oauth-protected-resource)",
    )

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
                raise ValueError(f"Invalid URL format for resource server: '{url}' - must include scheme and netloc")
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Resource server URL must use http or https scheme: '{url}'")
        except Exception as e:
            raise ValueError(f"Invalid resource server URL '{url}': {e}") from e

        return url

    @field_validator("scopes_supported")
    @classmethod
    def validate_scopes_supported(cls, v: list[str]) -> list[str]:
        """Validate scopes_supported format and security."""
        if not v:
            return v

        cleaned_scopes = []
        for scope in v:
            scope = scope.strip()
            if not scope:
                raise ValueError("Scopes cannot be empty or whitespace-only")

            # OAuth 2.0 scope format validation (RFC 6749)
            if not all(32 < ord(c) < 127 and c not in ' "\\' for c in scope):
                raise ValueError(
                    f"Invalid scope format: '{scope}' - must be ASCII printable without spaces, quotes, or backslashes"
                )

            # Reasonable length limit to prevent abuse
            if len(scope) > 128:
                raise ValueError(f"Scope too long: '{scope}' - maximum 128 characters")

            # Warn about potentially dangerous scope names
            dangerous_scopes = {"admin", "root", "superuser", "system", "*", "all"}
            if scope.lower() in dangerous_scopes:
                import warnings

                warnings.warn(
                    f"Potentially dangerous scope detected: '{scope}'. "
                    "Consider using more specific, principle-of-least-privilege scopes.",
                    UserWarning,
                    stacklevel=2,
                )

            cleaned_scopes.append(scope)

        return cleaned_scopes

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
            not config.public_key
            and not config.jwks_uri
            and not config.public_key_env_var
            and not config.jwks_uri_env_var
        ):
            raise ValueError(
                "JWT token verifier config must provide public_key, jwks_uri, or their environment variable equivalents"
            )

        # For static token configs, ensure they have tokens
        if isinstance(config, StaticTokenConfig) and not config.tokens:
            raise ValueError("Static token verifier config must provide at least one token")

        # Convenience: if user didn't set scopes_supported, default to verifier.required_scopes
        if not self.scopes_supported:
            if hasattr(config, "required_scopes") and config.required_scopes:
                self.scopes_supported = list(config.required_scopes)

        return self


class OAuthProxyConfig(BaseModel):
    """Configuration for OAuth proxy functionality (requires golf-mcp-enterprise).

    This configuration enables bridging MCP clients (which expect Dynamic Client
    Registration) with OAuth providers that use fixed client credentials like
    GitHub Apps, Google Cloud Console apps, Okta Web Applications, etc.

    The proxy acts as a DCR-capable authorization server to MCP clients while
    using your fixed upstream client credentials with the actual OAuth provider.

    Note: This class provides configuration only. The actual implementation
    requires the golf-mcp-enterprise package.
    """

    provider_type: Literal["oauth_proxy"] = "oauth_proxy"

    # Upstream OAuth provider configuration
    upstream_authorization_endpoint: str = Field(..., description="Upstream provider's authorization endpoint URL")
    upstream_token_endpoint: str = Field(..., description="Upstream provider's token endpoint URL")
    upstream_client_id: str = Field(..., description="Your registered client ID with the upstream provider")
    upstream_client_secret: str = Field(..., description="Your registered client secret with the upstream provider")
    upstream_revocation_endpoint: str | None = Field(None, description="Optional upstream token revocation endpoint")

    # This proxy server configuration
    base_url: str = Field(..., description="Public URL of this OAuth proxy server")
    redirect_path: str = Field("/oauth/callback", description="OAuth callback path (must match provider registration)")

    # Scopes and token verification
    scopes_supported: list[str] = Field(default_factory=list, description="Scopes supported by this proxy")
    token_verifier_config: JWTAuthConfig | StaticTokenConfig = Field(
        ..., description="Token verifier configuration for validating upstream tokens"
    )

    # Environment variable names for runtime configuration
    upstream_authorization_endpoint_env_var: str | None = Field(
        None, description="Environment variable name for upstream authorization endpoint"
    )
    upstream_token_endpoint_env_var: str | None = Field(
        None, description="Environment variable name for upstream token endpoint"
    )
    upstream_client_id_env_var: str | None = Field(None, description="Environment variable name for upstream client ID")
    upstream_client_secret_env_var: str | None = Field(
        None, description="Environment variable name for upstream client secret"
    )
    upstream_revocation_endpoint_env_var: str | None = Field(
        None, description="Environment variable name for upstream revocation endpoint"
    )
    base_url_env_var: str | None = Field(None, description="Environment variable name for base URL")

    @field_validator("upstream_authorization_endpoint", "upstream_token_endpoint", "base_url")
    @classmethod
    def validate_required_urls(cls, v: str) -> str:
        """Validate required URLs are properly formatted."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")

        url = v.strip()
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL format: '{url}' - must include scheme and netloc")
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"URL must use http or https scheme: '{url}'")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid URL '{url}': {e}") from e

        return url

    @field_validator("upstream_revocation_endpoint")
    @classmethod
    def validate_optional_url(cls, v: str | None) -> str | None:
        """Validate optional URLs are properly formatted."""
        if not v:
            return v

        url = v.strip()
        if not url:
            return None

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL format: '{url}' - must include scheme and netloc")
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"URL must use http or https scheme: '{url}'")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid URL '{url}': {e}") from e

        return url

    @field_validator("scopes_supported")
    @classmethod
    def validate_scopes_supported(cls, v: list[str]) -> list[str]:
        """Validate scopes_supported format and security."""
        if not v:
            return v

        cleaned_scopes = []
        for scope in v:
            scope = scope.strip()
            if not scope:
                raise ValueError("Scopes cannot be empty or whitespace-only")

            # OAuth 2.0 scope format validation (RFC 6749)
            if not all(32 < ord(c) < 127 and c not in ' "\\' for c in scope):
                raise ValueError(
                    f"Invalid scope format: '{scope}' - must be ASCII printable without spaces, quotes, or backslashes"
                )

            # Reasonable length limit to prevent abuse
            if len(scope) > 128:
                raise ValueError(f"Scope too long: '{scope}' - maximum 128 characters")

            cleaned_scopes.append(scope)

        return cleaned_scopes

    @model_validator(mode="after")
    def validate_oauth_proxy_config(self) -> "OAuthProxyConfig":
        """Validate OAuth proxy configuration consistency."""
        # Validate token verifier config is compatible
        if not isinstance(self.token_verifier_config, JWTAuthConfig | StaticTokenConfig):
            raise ValueError(
                f"token_verifier_config must be JWTAuthConfig or StaticTokenConfig, got {type(self.token_verifier_config).__name__}"
            )

        # Warn about HTTPS requirements in production
        is_production = (
            os.environ.get("GOLF_ENV", "").lower() in ("prod", "production")
            or os.environ.get("NODE_ENV", "").lower() == "production"
            or os.environ.get("ENVIRONMENT", "").lower() in ("prod", "production")
        )

        if is_production:
            from urllib.parse import urlparse

            urls_to_check = [
                ("base_url", self.base_url),
                ("upstream_authorization_endpoint", self.upstream_authorization_endpoint),
                ("upstream_token_endpoint", self.upstream_token_endpoint),
            ]

            if self.upstream_revocation_endpoint:
                urls_to_check.append(("upstream_revocation_endpoint", self.upstream_revocation_endpoint))

            for field_name, url in urls_to_check:
                parsed = urlparse(url)
                if parsed.scheme == "http":
                    import warnings

                    warnings.warn(
                        f"OAuth proxy {field_name} '{url}' uses HTTP in production environment. "
                        "HTTPS is strongly recommended for OAuth endpoints to prevent token interception.",
                        UserWarning,
                        stacklevel=2,
                    )

        return self


# Union type for all auth configurations
AuthConfig = JWTAuthConfig | StaticTokenConfig | OAuthServerConfig | RemoteAuthConfig | OAuthProxyConfig
