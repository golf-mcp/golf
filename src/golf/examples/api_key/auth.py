"""API key authentication configuration for your Golf MCP server.

This example shows how to configure API key authentication, which is useful
for services that require API tokens (like GitHub, OpenAI, etc.).
"""

from golf.auth import configure_api_key

# Configure API key extraction from Authorization header
# This will extract API keys from headers like: Authorization: Bearer your-api-key
configure_api_key(
    header_name="Authorization",
    header_prefix="Bearer ",  # Will strip "Bearer " prefix from the header value
    required=True,  # Reject requests without a valid API key
)