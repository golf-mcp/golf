"""Tests for Golf MCP configuration management."""

import json
from pathlib import Path

from golf.core.config import (
    find_config_path,
    find_project_root,
    load_settings,
)


class TestConfigDiscovery:
    """Test configuration file discovery."""

    def test_finds_golf_json_in_current_dir(self, temp_dir: Path) -> None:
        """Test finding golf.json in the current directory."""
        config_file = temp_dir / "golf.json"
        config_file.write_text('{"name": "TestProject"}')

        config_path = find_config_path(temp_dir)
        assert config_path == config_file

    def test_finds_golf_json_in_parent_dir(self, temp_dir: Path) -> None:
        """Test finding golf.json in a parent directory."""
        config_file = temp_dir / "golf.json"
        config_file.write_text('{"name": "TestProject"}')

        subdir = temp_dir / "subdir"
        subdir.mkdir()

        config_path = find_config_path(subdir)
        assert config_path == config_file

    def test_returns_none_when_no_config(self, temp_dir: Path) -> None:
        """Test that None is returned when no config file exists."""
        config_path = find_config_path(temp_dir)
        assert config_path is None


class TestProjectRoot:
    """Test project root discovery."""

    def test_finds_project_root(self, sample_project: Path) -> None:
        """Test finding project root from config file."""
        root, config = find_project_root(sample_project)
        assert root == sample_project
        assert config == sample_project / "golf.json"

    def test_finds_project_root_from_subdir(self, sample_project: Path) -> None:
        """Test finding project root from a subdirectory."""
        subdir = sample_project / "tools" / "nested"
        subdir.mkdir(parents=True)

        root, config = find_project_root(subdir)
        assert root == sample_project
        assert config == sample_project / "golf.json"


class TestSettingsLoading:
    """Test settings loading and parsing."""

    def test_loads_default_settings(self, temp_dir: Path) -> None:
        """Test loading settings with defaults when no config exists."""
        settings = load_settings(temp_dir)
        assert settings.name == "GolfMCP Project"
        assert settings.host == "127.0.0.1"
        assert settings.port == 3000
        assert settings.transport == "streamable-http"

    def test_loads_settings_from_json(self, temp_dir: Path) -> None:
        """Test loading settings from golf.json."""
        config = {
            "name": "MyProject",
            "description": "Test project",
            "host": "0.0.0.0",
            "port": 8080,
            "transport": "sse",
        }

        config_file = temp_dir / "golf.json"
        config_file.write_text(json.dumps(config))

        settings = load_settings(temp_dir)
        assert settings.name == "MyProject"
        assert settings.description == "Test project"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.transport == "sse"

    def test_env_file_override(self, temp_dir: Path) -> None:
        """Test that .env file values override defaults."""
        # Create .env file
        env_file = temp_dir / ".env"
        env_file.write_text("GOLF_PORT=9000\nGOLF_HOST=localhost")

        settings = load_settings(temp_dir)
        assert settings.port == 9000
        assert settings.host == "localhost"

    def test_health_check_defaults(self, temp_dir: Path) -> None:
        """Test health check default configuration values."""
        settings = load_settings(temp_dir)
        assert settings.health_check_enabled is False
        assert settings.health_check_path == "/health"
        assert settings.health_check_response == "OK"

    def test_health_check_configuration_from_json(self, temp_dir: Path) -> None:
        """Test loading health check configuration from golf.json."""
        config = {
            "name": "HealthProject",
            "health_check_enabled": True,
            "health_check_path": "/status",
            "health_check_response": "Service is healthy"
        }

        config_file = temp_dir / "golf.json"
        config_file.write_text(json.dumps(config))

        settings = load_settings(temp_dir)
        assert settings.health_check_enabled is True
        assert settings.health_check_path == "/status"
        assert settings.health_check_response == "Service is healthy"

    def test_health_check_partial_configuration(self, temp_dir: Path) -> None:
        """Test that partial health check configuration uses defaults for missing values."""
        config = {
            "name": "PartialHealthProject",
            "health_check_enabled": True
        }

        config_file = temp_dir / "golf.json"
        config_file.write_text(json.dumps(config))

        settings = load_settings(temp_dir)
        assert settings.health_check_enabled is True
        assert settings.health_check_path == "/health"  # default
        assert settings.health_check_response == "OK"  # default
