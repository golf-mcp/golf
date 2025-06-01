"""Integration tests for health check functionality."""

import json
from pathlib import Path


from golf.commands.build import build_project
from golf.commands.init import initialize_project
from golf.core.config import load_settings


class TestHealthCheckIntegration:
    """Integration tests for health check functionality from init to build."""

    def test_health_check_full_workflow(self, temp_dir: Path) -> None:
        """Test complete workflow: init project with health check -> build -> verify output."""
        project_dir = temp_dir / "health_check_project"
        
        # Initialize project
        initialize_project("health_check_project", project_dir, template="basic")
        
        # Update config to enable health check
        config_file = project_dir / "golf.json"
        config = json.loads(config_file.read_text())
        config.update({
            "health_check_enabled": True,
            "health_check_path": "/healthz",
            "health_check_response": "Healthy"
        })
        config_file.write_text(json.dumps(config, indent=2))
        
        # Build the project
        settings = load_settings(project_dir)
        output_dir = project_dir / "dist"
        
        build_project(project_dir, settings, output_dir, build_env="prod")
        
        # Verify build output
        server_file = output_dir / "server.py"
        assert server_file.exists()
        
        server_code = server_file.read_text()
        
        # Verify health check is included
        assert "from starlette.requests import Request" in server_code
        assert "from starlette.responses import PlainTextResponse" in server_code
        assert "@mcp.custom_route(\"/healthz\", methods=[\"GET\"])" in server_code
        assert 'return PlainTextResponse("Healthy")' in server_code
        
        # Verify pyproject.toml includes required dependencies
        pyproject_file = output_dir / "pyproject.toml"
        assert pyproject_file.exists()
        pyproject_content = pyproject_file.read_text()
        assert "fastmcp" in pyproject_content

    def test_health_check_with_api_key_template(self, temp_dir: Path) -> None:
        """Test health check integration with API key template."""
        project_dir = temp_dir / "api_key_health_project"
        
        # Initialize with API key template
        initialize_project("api_key_health_project", project_dir, template="api_key")
        
        # Update config to enable health check
        config_file = project_dir / "golf.json"
        config = json.loads(config_file.read_text())
        config.update({
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_response": "API server is healthy"
        })
        config_file.write_text(json.dumps(config, indent=2))
        
        # Build the project
        settings = load_settings(project_dir)
        output_dir = project_dir / "dist"
        
        build_project(project_dir, settings, output_dir, build_env="dev", copy_env=True)
        
        # Verify both health check and auth components are present
        server_file = output_dir / "server.py"
        server_code = server_file.read_text()
        
        # Health check should be present
        assert "@mcp.custom_route(\"/health\", methods=[\"GET\"])" in server_code
        assert 'return PlainTextResponse("API server is healthy")' in server_code
        
        # API key auth should also be present (from template)
        assert "configure_api_key" in server_code or "API" in server_code

    def test_health_check_disabled_by_default(self, temp_dir: Path) -> None:
        """Test that health check is disabled by default in new projects."""
        project_dir = temp_dir / "default_project"
        
        # Initialize project with defaults
        initialize_project("default_project", project_dir, template="basic")
        
        # Build without modifying config
        settings = load_settings(project_dir)
        output_dir = project_dir / "dist"
        
        build_project(project_dir, settings, output_dir, build_env="prod")
        
        # Verify health check is NOT included
        server_file = output_dir / "server.py"
        server_code = server_file.read_text()
        
        assert "@mcp.custom_route" not in server_code
        assert "health_check" not in server_code
        assert "PlainTextResponse" not in server_code

    def test_health_check_with_opentelemetry(self, temp_dir: Path) -> None:
        """Test health check integration with OpenTelemetry enabled."""
        project_dir = temp_dir / "otel_health_project"
        
        # Initialize project
        initialize_project("otel_health_project", project_dir, template="basic")
        
        # Update config to enable both health check and OpenTelemetry
        config_file = project_dir / "golf.json"
        config = json.loads(config_file.read_text())
        config.update({
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_response": "Service OK",
            "opentelemetry_enabled": True,
            "opentelemetry_default_exporter": "console"
        })
        config_file.write_text(json.dumps(config, indent=2))
        
        # Build the project
        settings = load_settings(project_dir)
        output_dir = project_dir / "dist"
        
        build_project(project_dir, settings, output_dir, build_env="prod")
        
        # Verify both health check and OpenTelemetry are present
        server_file = output_dir / "server.py"
        server_code = server_file.read_text()
        
        # Health check should be present
        assert "@mcp.custom_route(\"/health\", methods=[\"GET\"])" in server_code
        assert 'return PlainTextResponse("Service OK")' in server_code
        
        # OpenTelemetry should be present
        assert "opentelemetry" in server_code or "telemetry" in server_code

    def test_health_check_with_multiple_transports(self, temp_dir: Path) -> None:
        """Test health check works with different transport configurations."""
        transport_configs = [
            {"transport": "sse"},
            {"transport": "streamable-http"},
            {"transport": "stdio"}
        ]
        
        for i, transport_config in enumerate(transport_configs):
            project_dir = temp_dir / f"transport_project_{i}"
            
            # Initialize project
            initialize_project(f"transport_project_{i}", project_dir, template="basic")
            
            # Update config
            config_file = project_dir / "golf.json"
            config = json.loads(config_file.read_text())
            config.update({
                "health_check_enabled": True,
                "health_check_path": "/health",
                "health_check_response": f"Transport {transport_config['transport']} OK",
                **transport_config
            })
            config_file.write_text(json.dumps(config, indent=2))
            
            # Build the project
            settings = load_settings(project_dir)
            output_dir = project_dir / "dist"
            
            build_project(project_dir, settings, output_dir, build_env="prod")
            
            # Verify health check is present regardless of transport
            server_file = output_dir / "server.py"
            server_code = server_file.read_text()
            
            if transport_config["transport"] != "stdio":
                # HTTP-based transports should have health check
                assert "@mcp.custom_route(\"/health\", methods=[\"GET\"])" in server_code
                assert f'return PlainTextResponse("Transport {transport_config["transport"]} OK")' in server_code
            else:
                # stdio transport should still include health check code, even if not usable
                assert "@mcp.custom_route(\"/health\", methods=[\"GET\"])" in server_code


class TestHealthCheckValidation:
    """Test validation and error handling for health check configuration."""

    def test_health_check_with_invalid_path(self, temp_dir: Path) -> None:
        """Test that health check works with various path formats."""
        project_dir = temp_dir / "path_test_project"
        
        # Initialize project
        initialize_project("path_test_project", project_dir, template="basic")
        
        # Test various path formats
        test_paths = [
            "/health",
            "/api/health",
            "/status/check",
            "/healthz",
            "/ping"
        ]
        
        for path in test_paths:
            # Update config
            config_file = project_dir / "golf.json"
            config = json.loads(config_file.read_text())
            config.update({
                "health_check_enabled": True,
                "health_check_path": path,
                "health_check_response": "OK"
            })
            config_file.write_text(json.dumps(config, indent=2))
            
            # Build should succeed
            settings = load_settings(project_dir)
            output_dir = project_dir / "dist"
            
            # Clean output directory
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
            
            build_project(project_dir, settings, output_dir, build_env="prod")
            
            # Verify correct path is used
            server_file = output_dir / "server.py"
            server_code = server_file.read_text()
            
            assert f"@mcp.custom_route(\"{path}\", methods=[\"GET\"])" in server_code

    def test_health_check_with_special_characters_in_response(self, temp_dir: Path) -> None:
        """Test health check with special characters in response text."""
        project_dir = temp_dir / "special_chars_project"
        
        # Initialize project
        initialize_project("special_chars_project", project_dir, template="basic")
        
        # Test response with special characters
        special_response = 'Service "Health" Status: OK & Running!'
        
        # Update config
        config_file = project_dir / "golf.json"
        config = json.loads(config_file.read_text())
        config.update({
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_response": special_response
        })
        config_file.write_text(json.dumps(config, indent=2))
        
        # Build should succeed
        settings = load_settings(project_dir)
        output_dir = project_dir / "dist"
        
        build_project(project_dir, settings, output_dir, build_env="prod")
        
        # Verify response is properly escaped in generated code
        server_file = output_dir / "server.py"
        server_code = server_file.read_text()
        
        # The response should be present (possibly escaped)
        assert 'PlainTextResponse(' in server_code
        assert 'Health' in server_code
        assert 'Running' in server_code 