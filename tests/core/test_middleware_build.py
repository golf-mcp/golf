"""Integration tests for middleware.py build process."""
import json
from pathlib import Path
from golf.core.builder import build_project
from golf.core.config import load_settings


class TestMiddlewareBuildIntegration:
    """Test middleware.py integration with full build process."""

    def test_middleware_copied_and_imported(self, sample_project: Path, temp_dir: Path):
        """Test middleware.py is copied to build dir and imported."""
        middleware_content = '''
from fastmcp.server.middleware import Middleware

class BuildTestMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        return await call_next(context)
'''
        
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text(middleware_content)

        # Build project
        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        # Verify middleware.py copied
        copied_middleware = output_dir / "middleware.py"
        assert copied_middleware.exists()
        assert copied_middleware.read_text().strip() == middleware_content.strip()

        # Verify server.py includes middleware
        server_file = output_dir / "server.py"
        server_content = server_file.read_text()
        assert "from middleware import BuildTestMiddleware" in server_content
        assert "mcp.add_middleware(BuildTestMiddleware())" in server_content

    def test_middleware_with_auth_integration(self, sample_project: Path, temp_dir: Path):
        """Test middleware works alongside auth.py."""
        # Create auth.py
        auth_file = sample_project / "auth.py"
        auth_file.write_text('''
from golf.auth import configure_api_key
configure_api_key()
''')

        # Create middleware.py
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class AuthTestMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        
        # Both auth and middleware should be present
        assert "# Configure authentication" in server_content or "ApiKeyMiddleware" in server_content
        assert "from middleware import AuthTestMiddleware" in server_content
        assert "mcp.add_middleware(AuthTestMiddleware())" in server_content

    def test_multiple_middleware_classes_integration(self, sample_project: Path, temp_dir: Path):
        """Test integration with multiple middleware classes."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class LoggingMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        print(f"Tool called: {context.message.params.name}")
        return await call_next(context)

class TimingMiddleware(Middleware):
    async def on_message(self, context, call_next):
        import time
        start = time.time()
        result = await call_next(context)
        print(f"Request took: {time.time() - start:.2f}s")
        return result
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        
        # Verify both middleware classes are imported and registered
        assert "from middleware import LoggingMiddleware, TimingMiddleware" in server_content
        assert "mcp.add_middleware(LoggingMiddleware())" in server_content
        assert "mcp.add_middleware(TimingMiddleware())" in server_content

    def test_build_without_middleware_file(self, sample_project: Path, temp_dir: Path):
        """Test build succeeds when no middleware.py file exists."""
        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        # Build should succeed
        server_file = output_dir / "server.py"
        assert server_file.exists()
        
        # Should not contain middleware code
        server_content = server_file.read_text()
        assert "from middleware import" not in server_content
        assert "mcp.add_middleware(" not in server_content

    def test_build_with_broken_middleware_file(self, sample_project: Path, temp_dir: Path):
        """Test build succeeds gracefully with broken middleware.py."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from nonexistent_module import SomeClass
syntax error here!
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        
        # Build should succeed despite broken middleware.py
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        # Server file should be created
        server_file = output_dir / "server.py"
        assert server_file.exists()
        
        # Should not contain middleware code due to error
        server_content = server_file.read_text()
        assert "from middleware import" not in server_content
        assert "mcp.add_middleware(" not in server_content

    def test_middleware_with_different_transports(self, sample_project: Path, temp_dir: Path):
        """Test middleware works with different transport types."""
        # Test with SSE transport
        config_file = sample_project / "golf.json"
        config = {"name": "TestProject", "transport": "sse"}
        config_file.write_text(json.dumps(config))

        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class TransportMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "sse_build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        assert "from middleware import TransportMiddleware" in server_content
        assert "mcp.add_middleware(TransportMiddleware())" in server_content
        assert 'transport="sse"' in server_content

        # Test with streamable-http transport
        config["transport"] = "streamable-http"
        config_file.write_text(json.dumps(config))

        settings = load_settings(sample_project)
        output_dir = temp_dir / "http_build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        assert "from middleware import TransportMiddleware" in server_content
        assert "mcp.add_middleware(TransportMiddleware())" in server_content
        assert 'transport="streamable-http"' in server_content

    def test_middleware_with_metrics_enabled(self, sample_project: Path, temp_dir: Path):
        """Test middleware integration with metrics enabled."""
        config_file = sample_project / "golf.json"
        config = {"name": "TestProject", "metrics_enabled": True}
        config_file.write_text(json.dumps(config))

        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class MetricsMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        
        # Both metrics and custom middleware should be present
        assert "from middleware import MetricsMiddleware" in server_content
        assert "mcp.add_middleware(MetricsMiddleware())" in server_content

    def test_middleware_with_health_checks(self, sample_project: Path, temp_dir: Path):
        """Test middleware integration with health checks enabled."""
        config_file = sample_project / "golf.json"
        config = {
            "name": "TestProject",
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_response": "OK"
        }
        config_file.write_text(json.dumps(config))

        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class HealthMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        
        # Both health checks and custom middleware should be present
        assert "from middleware import HealthMiddleware" in server_content
        assert "mcp.add_middleware(HealthMiddleware())" in server_content
        # Health check route should also be present
        assert '@mcp.custom_route("/health"' in server_content

    def test_middleware_file_copied_to_build_dir(self, sample_project: Path, temp_dir: Path):
        """Test that middleware.py is properly copied during build."""
        # Create middleware with specific content
        original_content = '''"""Custom middleware for testing."""
from golf.middleware import Middleware

class CopyTestMiddleware(Middleware):
    """Middleware to test file copying."""
    
    async def on_message(self, context, call_next):
        # Add custom logic here
        print("Processing message")
        return await call_next(context)
    
    async def on_call_tool(self, context, call_next):
        # Tool call middleware
        print(f"Tool: {context.message.params.name}")
        return await call_next(context)
'''
        
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text(original_content)

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        # Verify file was copied with exact content
        copied_file = output_dir / "middleware.py"
        assert copied_file.exists()
        assert copied_file.read_text() == original_content

        # Verify server.py imports the middleware
        server_content = (output_dir / "server.py").read_text()
        assert "from middleware import CopyTestMiddleware" in server_content
        assert "mcp.add_middleware(CopyTestMiddleware())" in server_content

    def test_middleware_duck_typing_in_build(self, sample_project: Path, temp_dir: Path):
        """Test that duck-typed middleware (without base class) works in build."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
# No import of Middleware base class - pure duck typing
class DuckTypedLogging:
    async def on_call_tool(self, context, call_next):
        print(f"Calling tool: {context.message.params.name}")
        return await call_next(context)

class DuckTypedAuth:
    async def on_message(self, context, call_next):
        print("Authenticating request")
        return await call_next(context)

class NotMiddleware:
    def some_method(self):
        pass
''')

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        server_content = (output_dir / "server.py").read_text()
        
        # Duck-typed middleware should be discovered and registered
        # Check that both are imported (order doesn't matter)
        assert "DuckTypedLogging" in server_content
        assert "DuckTypedAuth" in server_content
        assert "from middleware import" in server_content
        assert "mcp.add_middleware(DuckTypedLogging())" in server_content
        assert "mcp.add_middleware(DuckTypedAuth())" in server_content
        # Non-middleware class should not be included
        assert "NotMiddleware" not in server_content