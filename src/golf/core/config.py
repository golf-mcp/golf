"""Configuration management for GolfMCP."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console

console = Console()


class AuthConfig(BaseModel):
    """Authentication configuration."""

    provider: str = Field(..., description="Authentication provider (e.g., 'jwks', 'google', 'github')")
    scopes: list[str] = Field(default_factory=list, description="Required OAuth scopes")
    client_id_env: str | None = Field(None, description="Environment variable name for client ID")
    client_secret_env: str | None = Field(None, description="Environment variable name for client secret")
    redirect_uri: str | None = Field(None, description="OAuth redirect URI (defaults to localhost callback)")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Validate the provider value."""
        valid_providers = {"jwks", "google", "github", "custom"}
        if value not in valid_providers and not value.startswith("custom:"):
            raise ValueError(f"Invalid provider '{value}'. Must be one of {valid_providers} or start with 'custom:'")
        return value


class DeployConfig(BaseModel):
    """Deployment configuration."""

    default: str = Field("vercel", description="Default deployment target")
    options: dict[str, Any] = Field(default_factory=dict, description="Target-specific options")


class Settings(BaseSettings):
    """GolfMCP application settings."""

    model_config = SettingsConfigDict(
        env_prefix="GOLF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    name: str = Field("GolfMCP Project", description="FastMCP instance name")
    description: str | None = Field(None, description="Project description")

    # Build settings
    output_dir: str = Field("dist", description="Build artifact folder")

    # Server settings
    host: str = Field("localhost", description="Server host")
    port: int = Field(3000, description="Server port")
    transport: str = Field(
        "streamable-http",
        description="Transport protocol (streamable-http, sse, stdio)",
    )

    # Auth settings
    auth: str | AuthConfig | None = Field(None, description="Authentication configuration or URI")

    # Deploy settings
    deploy: DeployConfig = Field(default_factory=DeployConfig, description="Deployment configuration")

    # Feature flags
    telemetry: bool = Field(True, description="Enable anonymous telemetry")

    # Project paths
    tools_dir: str = Field("tools", description="Directory containing tools")
    resources_dir: str = Field("resources", description="Directory containing resources")
    prompts_dir: str = Field("prompts", description="Directory containing prompts")

    # OpenTelemetry config
    opentelemetry_enabled: bool = Field(False, description="Enable OpenTelemetry tracing")
    opentelemetry_default_exporter: str = Field("console", description="Default OpenTelemetry exporter type")
    detailed_tracing: bool = Field(
        False, description="Enable detailed tracing with input/output capture (may contain sensitive data)"
    )

    # Health check configuration
    health_check_enabled: bool = Field(False, description="Enable health check endpoint")
    health_check_path: str = Field("/health", description="Health check endpoint path")
    health_check_response: str = Field("OK", description="Health check response text")

    # HTTP session behaviour
    stateless_http: bool = Field(
        False,
        description="Make Streamable-HTTP transport stateless (new session per request)",
    )

    # Metrics configuration
    metrics_enabled: bool = Field(False, description="Enable Prometheus metrics endpoint")
    metrics_path: str = Field("/metrics", description="Metrics endpoint path")


def find_config_path(start_path: Path | None = None) -> Path | None:
    """Find the golf config file by searching upwards from the given path.

    Args:
        start_path: Path to start searching from (defaults to current directory)

    Returns:
        Path to the config file if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.absolute()

    # Don't search above the home directory
    home = Path.home().absolute()

    while current != current.parent and current != home:
        # Check for JSON config first (preferred)
        json_config = current / "golf.json"
        if json_config.exists():
            return json_config

        # Fall back to TOML config
        toml_config = current / "golf.toml"
        if toml_config.exists():
            return toml_config

        current = current.parent

    return None


def find_project_root(
    start_path: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Find a GolfMCP project root by searching for a config file.

    This is the central project discovery function that should be used by all commands.

    Args:
        start_path: Path to start searching from (defaults to current directory)

    Returns:
        Tuple of (project_root, config_path) if a project is found, or
        (None, None) if not
    """
    config_path = find_config_path(start_path)
    if config_path:
        return config_path.parent, config_path
    return None, None


def load_settings(project_path: str | Path) -> Settings:
    """Load settings from a project directory.

    Args:
        project_path: Path to the project directory

    Returns:
        Settings object with values loaded from config files
    """
    # Convert to Path if needed
    if isinstance(project_path, str):
        project_path = Path(project_path)

    # Create default settings
    settings = Settings()

    # Check for .env file
    env_file = project_path / ".env"
    if env_file.exists():
        settings = Settings(_env_file=env_file)

        # Auto-enable OpenTelemetry if GOLF_API_KEY is present (from .env file)
        import os

        if os.environ.get("GOLF_API_KEY"):
            settings.opentelemetry_enabled = True

    # Try to load JSON config file first
    json_config_path = project_path / "golf.json"
    if json_config_path.exists():
        return _load_json_settings(json_config_path, settings)

    # No config file found, use defaults
    # Auto-enable OpenTelemetry if GOLF_API_KEY is present
    import os

    if os.environ.get("GOLF_API_KEY"):
        settings.opentelemetry_enabled = True

    return settings


def _load_json_settings(path: Path, settings: Settings) -> Settings:
    """Load settings from a JSON file."""
    try:
        import json

        with open(path) as f:
            config_data = json.load(f)

        # Update settings from config data
        for key, value in config_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        # Auto-enable OpenTelemetry if GOLF_API_KEY is present and telemetry wasn't explicitly configured
        import os

        if os.environ.get("GOLF_API_KEY") and "opentelemetry_enabled" not in config_data:
            settings.opentelemetry_enabled = True

        return settings
    except Exception as e:
        console.print(f"[bold red]Error loading JSON config from {path}: {e}[/bold red]")
        return settings
