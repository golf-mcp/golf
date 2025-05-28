"""OAuth provider configuration for GolfMCP authentication.

This module defines the ProviderConfig class used to configure
OAuth authentication for GolfMCP servers.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProviderConfig(BaseModel):
    """Configuration for an OAuth2 provider.

    This class defines the configuration for an OAuth2 provider,
    including the endpoints, credentials, and other settings needed
    to authenticate with the provider.
    """

    # Provider identification
    provider: str = Field(
        ..., description="Provider type (e.g., 'github', 'google', 'custom')"
    )

    # OAuth credentials - names of environment variables to read at runtime
    client_id_env_var: str = Field(
        ..., description="Name of environment variable for Client ID"
    )
    client_secret_env_var: str = Field(
        ..., description="Name of environment variable for Client Secret"
    )

    # These fields will store the actual values read at runtime in dist/server.py
    # They are made optional here as they are resolved in the generated code.
    client_id: str | None = Field(
        None, description="OAuth client ID (resolved at runtime)"
    )
    client_secret: str | None = Field(
        None, description="OAuth client secret (resolved at runtime)"
    )

    # OAuth endpoints (can be baked in)
    authorize_url: str = Field(..., description="Authorization endpoint URL")
    token_url: str = Field(..., description="Token endpoint URL")
    userinfo_url: str | None = Field(
        None, description="User info endpoint URL (for OIDC providers)"
    )

    jwks_uri: str | None = Field(
        None, description="JSON Web Key Set URI (for token validation)"
    )

    scopes: list[str] = Field(
        default_factory=list, description="OAuth scopes to request from the provider"
    )

    issuer_url: str | None = Field(
        None,
        description="OIDC issuer URL for discovery (if using OIDC) - will be overridden by runtime value in server.py",
    )

    callback_path: str = Field(
        "/auth/callback",
        description="Path on this server where the IdP should redirect after authentication",
    )

    # JWT configuration
    jwt_secret_env_var: str = Field(
        ..., description="Name of environment variable for JWT Secret"
    )
    jwt_secret: str | None = Field(
        None, description="Secret key for signing JWT tokens (resolved at runtime)"
    )
    token_expiration: int = Field(
        3600, description="JWT token expiration time in seconds", ge=60, le=86400
    )

    settings: dict[str, Any] = Field(
        default_factory=dict, description="Additional provider-specific settings"
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Validate the provider type.

        Ensures the provider type is a valid, supported provider.

        Args:
            value: The provider type

        Returns:
            The validated provider type

        Raises:
            ValueError: If the provider type is not supported
        """
        known_providers = {"custom", "github", "google", "jwks"}

        if value not in known_providers and not value.startswith("custom:"):
            raise ValueError(
                f"Unknown provider: '{value}'. Must be one of {known_providers} "
                "or start with 'custom:'"
            )
        return value

    def get_provider_name(self) -> str:
        """Get a clean provider name for display purposes.

        Returns:
            A human-readable provider name
        """
        if self.provider.startswith("custom:"):
            return self.provider[7:]  # Remove 'custom:' prefix
        return self.provider.capitalize()
