"""Pre-build configuration for the basic example.

This file is executed before the build process starts.
It configures GitHub OAuth authentication for the example.
"""

from golf.auth import ProviderConfig, configure_auth

# Create GitHub OAuth provider configuration
github_provider = ProviderConfig(
    provider="github",
    client_id_env_var="GITHUB_CLIENT_ID",
    client_secret_env_var="GITHUB_CLIENT_SECRET",
    jwt_secret_env_var="JWT_SECRET",
    authorize_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
    userinfo_url="https://api.github.com/user",
    scopes=["read:user", "user:email"],
    issuer_url="http://127.0.0.1:3000",  # This should be your Golf server's accessible URL
    callback_path="/auth/callback",  # Golf's callback path
    token_expiration=3600,  # 1 hour
)

# Configure authentication with the provider
configure_auth(
    provider=github_provider,
    required_scopes=["read:user"],  # Require read:user scope for protected endpoints
)
