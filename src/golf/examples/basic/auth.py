"""Authentication configuration for the basic Golf MCP server example.

This example shows different authentication options available in Golf 0.2.x:
- JWT authentication with static keys or JWKS endpoints (production)
- Static token authentication (development/testing)
- OAuth Server mode (full OAuth 2.0 server)
- Remote Authorization Server integration
"""

# Example 1: JWT authentication with a static public key
# from golf.auth import configure_auth, JWTAuthConfig
#
# configure_auth(
#     JWTAuthConfig(
#         public_key_env_var="JWT_PUBLIC_KEY",  # PEM-encoded public key
#         issuer="https://your-auth-server.com",
#         audience="https://your-golf-server.com",
#         required_scopes=["read:data"],
#     )
# )

# Example 2: JWT authentication with JWKS (recommended for production)
# from golf.auth import configure_auth, JWTAuthConfig
#
# configure_auth(
#     JWTAuthConfig(
#         jwks_uri_env_var="JWKS_URI",        # e.g., "https://your-domain.auth0.com/.well-known/jwks.json"
#         issuer_env_var="JWT_ISSUER",        # e.g., "https://your-domain.auth0.com/"
#         audience_env_var="JWT_AUDIENCE",    # e.g., "https://your-api.example.com"
#         required_scopes=["read:user"],
#     )
# )

# Example 3: OAuth Server mode - Golf acts as full OAuth 2.0 authorization server
# from golf.auth import configure_auth, OAuthServerConfig
#
# configure_auth(
#     OAuthServerConfig(
#         base_url_env_var="OAUTH_BASE_URL",          # e.g., "https://auth.example.com"
#         valid_scopes=["read", "write", "admin"],    # Scopes clients can request
#         default_scopes=["read"],                    # Default scopes for new clients
#         required_scopes=["read"],                   # Scopes required for all requests
#     )
# )

# Example 4: Remote Authorization Server integration
# from golf.auth import configure_auth, RemoteAuthConfig, JWTAuthConfig
#
# configure_auth(
#     RemoteAuthConfig(
#         authorization_servers_env_var="AUTH_SERVERS",    # Comma-separated: "https://auth1.com,https://auth2.com"
#         resource_server_url_env_var="RESOURCE_URL",     # This server's URL
#         token_verifier_config=JWTAuthConfig(
#             jwks_uri_env_var="JWKS_URI"
#         ),
#     )
# )

# Example 5: Static token authentication for development (NOT for production)
from golf.auth import configure_auth, StaticTokenConfig

configure_auth(
    StaticTokenConfig(
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
)
