"""Configure API key authentication for GitHub MCP server."""

from golf.auth import configure_api_key

# Configure Golf to extract GitHub personal access tokens from the Authorization header
# GitHub expects: Authorization: Bearer ghp_xxxx or Authorization: token ghp_xxxx
configure_api_key(
    header_name="Authorization",
    header_prefix="Bearer "  # Will handle both "Bearer " and "token " prefixes
)