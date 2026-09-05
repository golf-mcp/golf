"""Authentication integration for the Golf MCP build process.

This module adds support for injecting authentication configuration
into the generated FastMCP application during the build process using
FastMCP 4.0.0 built-in auth providers.
"""

from golf.auth import get_auth_config
from golf.auth.api_key import get_api_key_config
from golf.auth.providers import AuthConfig


def _config_has_callables(config: AuthConfig) -> bool:
    """Check if an auth config has any callable fields that can't be serialized.

    Callable fields (like allowed_redirect_patterns_func) cannot be embedded
    in generated code using repr(), so configs with callables need to use
    runtime config loading instead.
    """
    # Check for OAuthProxyConfig callable fields
    callable_fields = [
        "allowed_redirect_patterns_func",
        "allowed_redirect_schemes_func",
        "redirect_uri_validator",
    ]

    for field_name in callable_fields:
        if hasattr(config, field_name) and getattr(config, field_name) is not None:
            return True

    return False


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

    # Check if the auth config has callable fields (can't be embedded with repr)
    has_callable_fields = _config_has_callables(auth_config)

    if has_callable_fields:
        # For configs with callables, import and use auth module at runtime
        # auth.py is copied to dist and imported to register the config
        auth_imports = [
            "import os",
            "from golf.auth import get_auth_config",
            "from golf.auth.factory import create_auth_provider",
            "# Import auth module to execute configure_*() and register auth config",
            "import auth  # noqa: F401 - executes auth.py to register config",
        ]

        setup_code_lines = [
            "# FastMCP 4.0.0 authentication setup (runtime config with callables)",
            "# Auth config registered by auth.py import above",
            "auth_config = get_auth_config()",
            "auth_provider = create_auth_provider(auth_config)",
            f"# Authentication configured with {auth_config.provider_type} provider",
            "",
        ]
    else:
        # For configs without callables, embed the configuration directly
        auth_imports = [
            "import os",
            "from golf.auth.factory import create_auth_provider",
            "from golf.auth.providers import (",
            "    RemoteAuthConfig, JWTAuthConfig, StaticTokenConfig,",
            "    OAuthServerConfig, OAuthProxyConfig,",
            ")",
        ]

        # Embed the auth configuration directly in the generated code
        # Convert the auth config to its string representation for embedding
        auth_config_repr = repr(auth_config)

        setup_code_lines = [
            "# FastMCP 4.0.0 authentication setup with embedded configuration",
            f"auth_config = {auth_config_repr}",
            "auth_provider = create_auth_provider(auth_config)",
            f"# Authentication configured with {auth_config.provider_type} provider",
            "",
        ]

    # FastMCP registers the provider and its routes via auth=
    fastmcp_args = {"auth": "auth_provider"}

    return {
        "imports": auth_imports,
        "setup_code": setup_code_lines,
        "fastmcp_args": fastmcp_args,
        "has_auth": True,
        "copy_auth_file": has_callable_fields,  # Copy auth.py to dist for runtime loading
    }


def generate_api_key_auth_components(
    server_name: str,
    opentelemetry_enabled: bool = False,
    transport: str = "streamable-http",
) -> dict:
    """Generate deprecated API-key header extraction components.

    This is not MCP authentication. The middleware extracts a caller-provided
    header for tools to forward upstream; Golf does not verify the value.
    """
    api_key_config = get_api_key_config()
    if not api_key_config:
        return {"imports": [], "setup_code": [], "fastmcp_args": {}, "has_auth": False}

    auth_imports = [
        "# Deprecated: API key header extraction (not MCP authentication)",
        "from golf.auth.api_key import ApiKeyMiddleware, configure_api_key",
    ]

    setup_code_lines = [
        "# Recreate API key header extraction from auth.py.",
        "# Golf does not validate the key value; the upstream API does.",
        "configure_api_key(",
        f"    header_name={repr(api_key_config.header_name)},",
        f"    header_prefix={repr(api_key_config.header_prefix)},",
        f"    required={repr(api_key_config.required)},",
        ")",
        "",
    ]

    return {
        "imports": auth_imports,
        "setup_code": setup_code_lines,
        "fastmcp_args": {},
        "has_auth": True,
    }


def generate_auth_routes() -> str:
    """Return no route code; FastMCP registers auth routes via ``auth=``."""
    return ""
