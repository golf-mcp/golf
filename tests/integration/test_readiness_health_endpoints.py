"""Integration tests for readiness and health check endpoints."""

import tempfile
from pathlib import Path

import pytest

from golf.core.builder import build_project
from golf.core.config import Settings, load_settings


class TestReadinessHealthEndpoints:
    """Test actual HTTP endpoints in built servers."""

    def test_default_endpoints_without_custom_files(self):
        """Test default behavior when no custom files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create minimal project structure
            (project_path / "golf.json").write_text('{"name": "test-server"}')
            
            # Create minimal components
            tools_dir = project_path / "tools"
            tools_dir.mkdir()
            (tools_dir / "test_tool.py").write_text("""
def test_function():
    '''Test tool function.'''
    return "test"
""")

            settings = load_settings(project_path)
            output_dir = project_path / "dist"
            
            # Build the project
            build_project(project_path, settings, output_dir)
            
            # Check generated server.py
            server_file = output_dir / "server.py"
            assert server_file.exists()
            
            server_content = server_file.read_text()
            
            # Should have default readiness endpoint
            assert "# Default readiness check" in server_content
            assert '@mcp.custom_route("/ready", methods=["GET"])' in server_content
            assert "async def readiness_check" in server_content
            assert '{"status": "pass"}' in server_content
            
            # Should have default health endpoint
            assert "# Default health check" in server_content
            assert '@mcp.custom_route("/health", methods=["GET"])' in server_content
            assert "async def health_check" in server_content

    def test_custom_endpoints_with_custom_files(self):
        """Test custom function integration end-to-end."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create minimal project structure
            (project_path / "golf.json").write_text('{"name": "test-server"}')
            
            # Create custom readiness.py
            (project_path / "readiness.py").write_text("""
def check():
    return {
        "status": "pass",
        "services": ["service-a", "service-b"]
    }
""")
            
            # Create custom health.py
            (project_path / "health.py").write_text("""
def check():
    return {
        "status": "pass",
        "uptime": "5 minutes"
    }
""")

            # Create minimal components
            tools_dir = project_path / "tools"
            tools_dir.mkdir()
            (tools_dir / "test_tool.py").write_text("""
def test_function():
    '''Test tool function.'''
    return "test"
""")

            settings = load_settings(project_path)
            output_dir = project_path / "dist"
            
            # Build the project
            build_project(project_path, settings, output_dir)
            
            # Check generated server.py
            server_file = output_dir / "server.py"
            assert server_file.exists()
            
            server_content = server_file.read_text()
            
            # Should have custom readiness endpoint
            assert "# Custom readiness check from readiness.py" in server_content
            assert '_call_check_function("readiness")' in server_content
            
            # Should have custom health endpoint
            assert "# Custom health check from health.py" in server_content
            assert '_call_check_function("health")' in server_content
            
            # Should have helper function
            assert "async def _call_check_function(check_type: str)" in server_content
            
            # Check that custom files were copied
            assert (output_dir / "readiness.py").exists()
            assert (output_dir / "health.py").exists()

    def test_authentication_bypass_behavior(self):
        """Test that endpoints work without authentication."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create minimal project structure with auth enabled
            (project_path / "golf.json").write_text('{"name": "test-server", "host": "localhost", "port": 3000}')
            
            # Create auth.py with authentication
            (project_path / "auth.py").write_text("""
from golf.auth import configure_dev_auth
configure_dev_auth(
    tokens={"test-token": {"client_id": "test-client", "scopes": ["read"]}},
    required_scopes=["read"]
)
""")

            # Create minimal components
            tools_dir = project_path / "tools"
            tools_dir.mkdir()
            (tools_dir / "test_tool.py").write_text("""
def test_function():
    '''Test tool function.'''
    return "test"
""")

            settings = load_settings(project_path)
            output_dir = project_path / "dist"
            
            # Build the project
            build_project(project_path, settings, output_dir)
            
            # Check generated server.py
            server_file = output_dir / "server.py"
            assert server_file.exists()
            
            server_content = server_file.read_text()
            
            # Should have readiness and health endpoints (which bypass auth by using @mcp.custom_route)
            assert '@mcp.custom_route("/ready", methods=["GET"])' in server_content
            assert '@mcp.custom_route("/health", methods=["GET"])' in server_content
            
            # Should have auth configuration
            assert "auth_config" in server_content

    def test_error_handling_for_missing_check_function(self):
        """Test graceful error handling for malformed custom files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create minimal project structure
            (project_path / "golf.json").write_text('{"name": "test-server"}')
            
            # Create readiness.py without check function
            (project_path / "readiness.py").write_text("""
def other_function():
    return "not a check function"
""")

            # Create minimal components
            tools_dir = project_path / "tools"
            tools_dir.mkdir()
            (tools_dir / "test_tool.py").write_text("""
def test_function():
    '''Test tool function.'''
    return "test"
""")

            settings = load_settings(project_path)
            output_dir = project_path / "dist"
            
            # Build the project
            build_project(project_path, settings, output_dir)
            
            # Check generated server.py
            server_file = output_dir / "server.py"
            assert server_file.exists()
            
            server_content = server_file.read_text()
            
            # Should still have custom readiness (it will handle the error at runtime)
            assert "# Custom readiness check from readiness.py" in server_content
            assert '_call_check_function("readiness")' in server_content
            
            # Should have error handling in helper function
            assert 'No check() function found in {check_type}.py' in server_content

    def test_legacy_health_configuration_still_works(self):
        """Test backward compatibility with legacy health configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create project with legacy health configuration
            (project_path / "golf.json").write_text("""
{
    "name": "test-server", 
    "health_check_enabled": true,
    "health_check_path": "/health",
    "health_check_response": "OK"
}
""")

            # Create minimal components
            tools_dir = project_path / "tools"
            tools_dir.mkdir()
            (tools_dir / "test_tool.py").write_text("""
def test_function():
    '''Test tool function.'''
    return "test"
""")

            settings = load_settings(project_path)
            output_dir = project_path / "dist"
            
            # Build the project
            build_project(project_path, settings, output_dir)
            
            # Check generated server.py
            server_file = output_dir / "server.py"
            assert server_file.exists()
            
            server_content = server_file.read_text()
            
            # Should have legacy health check
            assert "# Legacy health check configuration (deprecated)" in server_content
            assert 'PlainTextResponse("OK")' in server_content
            assert '@mcp.custom_route("/health", methods=["GET"])' in server_content
            
            # Should still have default readiness (no custom file)
            assert "# Default readiness check" in server_content