"""Authentication configuration for the basic Golf MCP server example.

This example shows different authentication options available in Golf 0.2.x:
- JWT authentication with static keys or JWKS endpoints (production)
- Development authentication with static tokens (development/testing)
"""

# Example 1: JWT authentication with a static public key
# from golf.auth import configure_jwt_auth
#
# configure_jwt_auth(
#     public_key_env_var="JWT_PUBLIC_KEY",  # PEM-encoded public key
#     issuer="https://your-auth-server.com",
#     audience="https://your-golf-server.com",
#     required_scopes=["read:data"],
# )

# Example 2: JWT authentication with JWKS (recommended for production)
# from golf.auth import configure_jwt_auth
#
# configure_jwt_auth(
#     jwks_uri_env_var="JWKS_URI",  # e.g., "https://your-domain.auth0.com/.well-known/jwks.json"
#     issuer_env_var="JWT_ISSUER",  # e.g., "https://your-domain.auth0.com/"
#     audience_env_var="JWT_AUDIENCE",  # e.g., "https://your-api.example.com"
#     required_scopes=["read:user"],
# )

# Example 3: Development authentication with static tokens (NOT for production)
from golf.auth import configure_dev_auth

configure_dev_auth(
    tokens={
        "dev-token-123": {
            "client_id": "dev-client",
            "scopes": ["read", "write"],
        },
        "admin-token-456": {
            "client_id": "admin-client",
            "scopes": ["read", "write", "admin"],
        },
    },
    required_scopes=["read"],
)
