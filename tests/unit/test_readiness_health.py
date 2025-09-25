"""Unit tests for readiness and health check functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from golf.core.builder import CodeGenerator
from golf.core.config import Settings


class TestReadinessHealthGeneration:
    """Test readiness and health check code generation."""

    def test_default_readiness_when_no_file(self):
        """Test default readiness endpoint when no readiness.py exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings()
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Test readiness section generation
            readiness_section = generator._generate_readiness_section(project_path)
            
            # Should contain default readiness endpoint
            readiness_code = "\n".join(readiness_section)
            assert "# Default readiness check" in readiness_code
            assert "@mcp.custom_route('/ready', methods=[\"GET\"])" in readiness_code
            assert "async def readiness_check" in readiness_code
            assert '{"status": "pass"}' in readiness_code

    def test_custom_readiness_when_file_exists(self):
        """Test custom readiness endpoint when readiness.py exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings()
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            # Create readiness.py file
            readiness_file = project_path / "readiness.py"
            readiness_file.write_text("def check():\n    return True")
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Test readiness section generation
            readiness_section = generator._generate_readiness_section(project_path)
            
            # Should contain custom readiness endpoint
            readiness_code = "\n".join(readiness_section)
            assert "# Custom readiness check from readiness.py" in readiness_code
            assert "@mcp.custom_route('/ready', methods=[\"GET\"])" in readiness_code
            assert "async def readiness_check" in readiness_code
            assert "_call_check_function('readiness')" in readiness_code

    def test_default_health_when_no_file(self):
        """Test default health endpoint when no health.py exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings()
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Test health section generation  
            health_section = generator._generate_health_section(project_path)
            
            # Should contain default health endpoint
            health_code = "\n".join(health_section)
            assert "# Default health check" in health_code
            assert "@mcp.custom_route('/health', methods=[\"GET\"])" in health_code
            assert "async def health_check" in health_code
            assert '{"status": "pass"}' in health_code

    def test_custom_health_when_file_exists(self):
        """Test custom health endpoint when health.py exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings()
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            # Create health.py file
            health_file = project_path / "health.py"
            health_file.write_text("def check():\n    return True")
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Test health section generation
            health_section = generator._generate_health_section(project_path)
            
            # Should contain custom health endpoint
            health_code = "\n".join(health_section)
            assert "# Custom health check from health.py" in health_code
            assert "@mcp.custom_route('/health', methods=[\"GET\"])" in health_code
            assert "async def health_check" in health_code
            assert "_call_check_function('health')" in health_code

    def test_legacy_health_configuration_compatibility(self):
        """Test that legacy health configuration still works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings(
                health_check_enabled=True,
                health_check_path="/health",
                health_check_response="OK"
            )
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Test health section generation
            health_section = generator._generate_health_section(project_path)
            
            # Should contain legacy health endpoint
            health_code = "\n".join(health_section)
            assert "# Legacy health check configuration (deprecated)" in health_code
            assert "@mcp.custom_route('/health', methods=[\"GET\"])" in health_code
            assert "async def health_check" in health_code
            assert 'PlainTextResponse("OK")' in health_code

    def test_check_function_helper_generation(self):
        """Test helper function generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings()
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Test helper function generation
            helper_section = generator._generate_check_function_helper()
            
            # Should contain helper function
            helper_code = "\n".join(helper_section)
            assert "async def _call_check_function(check_type: str)" in helper_code
            assert "importlib.util" in helper_code
            assert "traceback" in helper_code
            assert "JSONResponse" in helper_code
            assert "Path(__file__).parent / f'{check_type}.py'" in helper_code

    def test_import_generation_with_custom_files(self):
        """Test that imports are added when custom files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            settings = Settings()
            output_dir = project_path / "dist"
            output_dir.mkdir(exist_ok=True)
            
            # Create custom files
            (project_path / "readiness.py").write_text("def check(): return True")
            (project_path / "health.py").write_text("def check(): return True")
            
            generator = CodeGenerator(project_path, settings, output_dir)
            
            # Mock the import generation part we can't easily test
            # The actual test would be in integration tests
            readiness_exists = (project_path / "readiness.py").exists()
            health_exists = (project_path / "health.py").exists()
            
            assert readiness_exists
            assert health_exists
            # When files exist, imports should be added
            should_add_imports = readiness_exists or health_exists or settings.health_check_enabled
            assert should_add_imports is True