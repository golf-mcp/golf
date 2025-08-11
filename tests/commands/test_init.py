"""Tests for the golf init command."""

import json
from pathlib import Path

import pytest

from golf.commands.init import initialize_project


class TestInitCommand:
    """Test the init command functionality."""

    def test_creates_basic_project_structure(self, temp_dir: Path) -> None:
        """Test that init creates the expected project structure."""
        project_dir = temp_dir / "my_project"

        initialize_project("my_project", project_dir)

        # Check directory structure
        assert project_dir.exists()
        assert (project_dir / "golf.json").exists()
        assert (project_dir / "tools").is_dir()
        assert (project_dir / "resources").is_dir()
        assert (project_dir / "prompts").is_dir()
        assert (project_dir / ".gitignore").exists()

    def test_golf_json_has_correct_content(self, temp_dir: Path) -> None:
        """Test that golf.json is created with correct content."""
        project_dir = temp_dir / "test_project"

        initialize_project("test_project", project_dir)

        config = json.loads((project_dir / "golf.json").read_text())
        assert config["name"] == "basic-server-example"
        assert "description" in config
        assert config["transport"] == "http"

    def test_template_variable_substitution(self, temp_dir: Path) -> None:
        """Test that template files are copied correctly."""
        project_dir = temp_dir / "MyApp"

        initialize_project("MyApp", project_dir)

        # Check that golf.json has the template content
        config = json.loads((project_dir / "golf.json").read_text())
        assert config["name"] == "basic-server-example"
        assert "description" in config

        # Check .env file exists (no longer has GOLF_NAME)

    def test_handles_existing_empty_directory(self, temp_dir: Path) -> None:
        """Test that init works with an existing empty directory."""
        project_dir = temp_dir / "existing"
        project_dir.mkdir()

        # Should not raise an error
        initialize_project("existing", project_dir)

        assert (project_dir / "golf.json").exists()

    @pytest.mark.skip(reason="Requires interactive input handling")
    def test_prompts_for_non_empty_directory(self, temp_dir: Path) -> None:
        """Test that init prompts when directory is not empty."""
        # This would require mocking the Confirm.ask prompt
        pass

    def test_basic_template_includes_health_check(self, temp_dir: Path) -> None:
        """Test that basic template does not include health check configuration by default."""
        project_dir = temp_dir / "health_check_project"

        initialize_project("health_check_project", project_dir)

        # Check that golf.json has basic template content
        config = json.loads((project_dir / "golf.json").read_text())
        assert "health_check_enabled" not in config  # Should not be included by default
        assert "health_check_path" not in config
        assert "health_check_response" not in config

        # Should include the basic configuration fields
        assert config["name"] == "basic-server-example"
        assert "description" in config
        assert config["transport"] == "http"

    def test_basic_template_compatibility_with_health_check(self, temp_dir: Path) -> None:
        """Test that basic template is compatible with health check configuration."""
        project_dir = temp_dir / "health_check_project"

        initialize_project("health_check_project", project_dir)

        # Check that we can add health check configuration
        config_file = project_dir / "golf.json"
        config = json.loads(config_file.read_text())

        # Add health check configuration
        config.update(
            {
                "health_check_enabled": True,
                "health_check_path": "/status",
                "health_check_response": "API Ready",
            }
        )

        # Should be able to write back without issues
        config_file.write_text(json.dumps(config, indent=2))

        # Verify it can be read back
        updated_config = json.loads(config_file.read_text())
        assert updated_config["health_check_enabled"] is True
        assert updated_config["health_check_path"] == "/status"
        assert updated_config["health_check_response"] == "API Ready"
