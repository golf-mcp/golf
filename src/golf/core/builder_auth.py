"""Authentication integration for the Golf MCP build process.

This module adds support for injecting authentication configuration
into the generated FastMCP application during the build process using
FastMCP 2.11+ built-in auth providers.
"""

from golf.auth import get_auth_config, is_auth_configured
from golf.auth.api_key import get_api_key_config
from golf.auth.providers import AuthConfig


def generate_auth_code(
    server_name: str,
    host: str = "localhost",
    port: int = 3000,
    https: bool = False,
    opentelemetry_enabled: bool = False,
    transport: str = "streamable-http",
) -> dict:
    """Generate authentication components for the FastMCP app using modern
    auth providers.

    Returns a dictionary with:
        - imports: List of import statements
        - setup_code: Auth setup code (provider configuration, etc.)
        - fastmcp_args: Dict of arguments to add to FastMCP constructor
        - has_auth: Whether auth is configured
    """
    # Check for API key configuration first
    api_key_config = get_api_key_config()
    if api_key_config:
        return generate_api_key_auth_components(server_name, opentelemetry_enabled, transport)

    # Check for modern auth configuration
    auth_config = get_auth_config()
    if not auth_config:
        # If no auth config, return empty components
        return {"imports": [], "setup_code": [], "fastmcp_args": {}, "has_auth": False}

    # Validate that we have a modern auth config
    if not isinstance(auth_config, AuthConfig):
        raise ValueError(
            f"Invalid auth configuration type: {type(auth_config).__name__}. "
            "Golf 0.2.x requires modern auth configurations (JWTAuthConfig, "
            "StaticTokenConfig, OAuthServerConfig, or RemoteAuthConfig). "
            "Please update your auth.py file."
        )

    # Generate modern auth components with embedded configuration
    auth_imports = [
        "import os",
        "import sys",
        "from golf.auth.factory import create_auth_provider",
        "from golf.auth.providers import RemoteAuthConfig, JWTAuthConfig, StaticTokenConfig, OAuthServerConfig, OAuthProxyConfig",
    ]

    # Embed the auth configuration directly in the generated code
    # Convert the auth config to its string representation for embedding
    auth_config_repr = repr(auth_config)

    setup_code_lines = [
        "# Modern FastMCP 2.11+ authentication setup with embedded configuration",
        f"auth_config = {auth_config_repr}",
        "try:",
        "    auth_provider = create_auth_provider(auth_config)",
        "    # Authentication configured with {auth_config.provider_type} provider",
        "except Exception as e:",
        "    print(f'Authentication setup failed: {e}', file=sys.stderr)",
        "    auth_provider = None",
        "",
    ]

    # FastMCP constructor arguments - FastMCP 2.11+ uses auth parameter
    fastmcp_args = {"auth": "auth_provider"}

    return {
        "imports": auth_imports,
        "setup_code": setup_code_lines,
        "fastmcp_args": fastmcp_args,
        "has_auth": True,
    }


def generate_api_key_auth_components(
    server_name: str,
    opentelemetry_enabled: bool = False,
    transport: str = "streamable-http",
) -> dict:
    """Generate authentication components for API key authentication.

    Returns a dictionary with:
        - imports: List of import statements
        - setup_code: Auth setup code (middleware setup)
        - fastmcp_args: Dict of arguments to add to FastMCP constructor
        - has_auth: Whether auth is configured
    """
    api_key_config = get_api_key_config()
    if not api_key_config:
        return {"imports": [], "setup_code": [], "fastmcp_args": {}, "has_auth": False}

    auth_imports = [
        "# API key authentication setup",
        "from golf.auth.api_key import get_api_key_config, configure_api_key",
        "from golf.auth import set_api_key",
        "from starlette.middleware.base import BaseHTTPMiddleware",
        "from starlette.requests import Request",
        "from starlette.responses import JSONResponse",
        "import os",
    ]

    setup_code_lines = [
        "# Recreate API key configuration from auth.py",
        "configure_api_key(",
        f"    header_name={repr(api_key_config.header_name)},",
        f"    header_prefix={repr(api_key_config.header_prefix)},",
        f"    required={repr(api_key_config.required)}",
        ")",
        "",
        "# Simplified API key middleware that validates presence",
        "class ApiKeyMiddleware(BaseHTTPMiddleware):",
        "    async def dispatch(self, request: Request, call_next):",
        "        # Debug mode from environment",
        "        debug = os.environ.get('GOLF_API_KEY_DEBUG', '').lower() == 'true'",
        "        ",
        "        # Skip auth for monitoring endpoints",
        "        path = request.url.path",
        "        if path in ['/metrics', '/health']:",
        "            return await call_next(request)",
        "        ",
        "        api_key_config = get_api_key_config()",
        "        ",
        "        if api_key_config:",
        "            # Extract API key from the configured header",
        "            header_name = api_key_config.header_name",
        "            header_prefix = api_key_config.header_prefix",
        "            ",
        "            # Case-insensitive header lookup",
        "            api_key = None",
        "            for k, v in request.headers.items():",
        "                if k.lower() == header_name.lower():",
        "                    api_key = v",
        "                    break",
        "            ",
        "            # Process the API key if found",
        "            if api_key:",
        "                # Strip prefix if configured",
        "                if header_prefix and api_key.startswith(header_prefix):",
        "                    api_key = api_key[len(header_prefix):]",
        "                ",
        "                # Store the API key in request state for tools to access",
        "                request.state.api_key = api_key",
        "                ",
        "                # Also store in context variable for tools",
        "                set_api_key(api_key)",
        "            ",
        "            # Check if API key is required but missing",
        "            if api_key_config.required and not api_key:",
        "                return JSONResponse(",
        "                    {'error': 'unauthorized', "
        "'detail': f'Missing required {header_name} header'},"
        "                    status_code=401,",
        "                    headers={'WWW-Authenticate': f'{header_name} realm=\"MCP Server\"'}",
        "                )",
        "        ",
        "        # Continue with the request",
        "        return await call_next(request)",
        "",
    ]

    # API key auth is handled via middleware, not FastMCP constructor args
    fastmcp_args = {}

    return {
        "imports": auth_imports,
        "setup_code": setup_code_lines,
        "fastmcp_args": fastmcp_args,
        "has_auth": True,
    }


def generate_auth_routes() -> str:
    """Generate code for auth routes in the FastMCP app.

    Auth providers (RemoteAuthProvider, OAuthProvider) provide OAuth metadata routes
    that need to be added to the server.
    """
    # API key auth doesn't need special routes
    api_key_config = get_api_key_config()
    if api_key_config:
        return ""

    # Check if auth is configured
    if not is_auth_configured():
        return ""

    # Auth providers provide OAuth metadata routes that need to be added to the server
    return """
# Add OAuth metadata routes from auth provider
if auth_provider and hasattr(auth_provider, 'get_routes'):
    auth_routes = auth_provider.get_routes()
    if auth_routes:
        # Add routes to FastMCP's additional HTTP routes list
        try:
            mcp._additional_http_routes.extend(auth_routes)
            # Added {len(auth_routes)} OAuth metadata routes
        except Exception as e:
            print(f"Warning: Failed to add OAuth routes: {e}")
"""
