"""Tests for middleware.py integration."""
import json
from pathlib import Path
from golf.core.builder import CodeGenerator
from golf.core.config import load_settings


class TestMiddlewareDiscovery:
    """Test middleware.py file discovery and class extraction."""

    def test_discovers_middleware_classes(self, sample_project: Path, temp_dir: Path):
        """Test basic middleware class discovery."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class LoggingMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        return await call_next(context)

class NotMiddleware:
    pass  # Should be ignored
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == ["LoggingMiddleware"]

    def test_discovers_multiple_middleware_methods(self, sample_project: Path, temp_dir: Path):
        """Test discovery of middleware with different methods."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class MessageMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)

class RequestMiddleware(Middleware):
    async def on_request(self, context, call_next):
        return await call_next(context)

class DispatchMiddleware(Middleware):
    def dispatch(self, context):
        pass
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        # Should discover all three middleware classes
        assert set(middleware_classes) == {"MessageMiddleware", "RequestMiddleware", "DispatchMiddleware"}

    def test_no_middleware_when_file_missing(self, sample_project: Path, temp_dir: Path):
        """Test graceful handling when middleware.py doesn't exist."""
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == []

    def test_ignores_classes_without_middleware_methods(self, sample_project: Path, temp_dir: Path):
        """Test that classes without middleware methods are ignored."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class ValidMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        return await call_next(context)

class RegularClass:
    def some_method(self):
        pass

class AnotherClass(Middleware):
    def regular_method(self):
        pass  # No middleware methods
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == ["ValidMiddleware"]


class TestMiddlewareCodeGeneration:
    """Test middleware code generation in server.py."""

    def test_generates_middleware_imports_and_registration(self, sample_project: Path, temp_dir: Path):
        """Test middleware imports and mcp.add_middleware calls."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class TestMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_content = server_file.read_text()

        assert "from middleware import TestMiddleware" in server_content
        assert "mcp.add_middleware(TestMiddleware())" in server_content

    def test_generates_multiple_middleware_registration(self, sample_project: Path, temp_dir: Path):
        """Test registration of multiple middleware classes."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class FirstMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)

class SecondMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_content = server_file.read_text()

        assert "from middleware import FirstMiddleware, SecondMiddleware" in server_content
        assert "mcp.add_middleware(FirstMiddleware())" in server_content
        assert "mcp.add_middleware(SecondMiddleware())" in server_content

    def test_no_middleware_code_when_missing(self, sample_project: Path, temp_dir: Path):
        """Test no middleware code when middleware.py missing."""
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_content = server_file.read_text()

        assert "from middleware import" not in server_content
        assert "mcp.add_middleware(" not in server_content


class TestMiddlewareErrorHandling:
    """Test error handling for malformed middleware.py."""

    def test_handles_syntax_error(self, sample_project: Path, temp_dir: Path):
        """Test graceful handling of syntax errors."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class TestMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context
# Missing closing parenthesis - syntax error
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == []  # Should return empty list on error

    def test_handles_import_error(self, sample_project: Path, temp_dir: Path):
        """Test graceful handling of import errors."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from nonexistent_module import SomeClass

class TestMiddleware:
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == []  # Should return empty list on error

    def test_build_succeeds_with_broken_middleware(self, sample_project: Path, temp_dir: Path):
        """Test that broken middleware doesn't break the build process."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from nonexistent_module import SomeClass
syntax error here!
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        
        # Build should succeed even with broken middleware.py
        generator.generate()

        # Server file should be created
        server_file = temp_dir / "server.py"
        assert server_file.exists()
        
        # Should not contain any middleware code
        server_content = server_file.read_text()
        assert "from middleware import" not in server_content
        assert "mcp.add_middleware(" not in server_content

    def test_handles_runtime_error_in_middleware(self, sample_project: Path, temp_dir: Path):
        """Test graceful handling of runtime errors in middleware.py."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
# This will cause a runtime error
1 / 0

class TestMiddleware:
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == []  # Should return empty list on error

    def test_handles_empty_middleware_file(self, sample_project: Path, temp_dir: Path):
        """Test handling of empty middleware.py file."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert middleware_classes == []


class TestMiddlewareDuckTyping:
    """Test middleware discovery using duck typing."""

    def test_discovers_middleware_without_base_class(self, sample_project: Path, temp_dir: Path):
        """Test middleware discovery using duck typing for methods."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
# No base class import - pure duck typing
class DuckTypedMiddleware:
    async def on_call_tool(self, context, call_next):
        return await call_next(context)

class AlsoMiddleware:
    async def dispatch(self, context, call_next):
        return await call_next(context)

class NotMiddleware:
    def some_other_method(self):
        pass
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert len(middleware_classes) == 2
        assert "DuckTypedMiddleware" in middleware_classes
        assert "AlsoMiddleware" in middleware_classes
        assert "NotMiddleware" not in middleware_classes

    def test_discovers_mixed_middleware_types(self, sample_project: Path, temp_dir: Path):
        """Test discovery of middleware with and without base class."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class InheritedMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)

class DuckTypedMiddleware:
    async def on_call_tool(self, context, call_next):
        return await call_next(context)

class NoMiddlewareMethods:
    def regular_method(self):
        pass
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        middleware_classes = generator._discover_middleware_classes(sample_project)
        
        assert len(middleware_classes) == 2
        assert "InheritedMiddleware" in middleware_classes
        assert "DuckTypedMiddleware" in middleware_classes
        assert "NoMiddlewareMethods" not in middleware_classes


class TestMiddlewareRegistrationOrder:
    """Test middleware registration order and positioning."""
    
    def test_middleware_registered_in_correct_order(self, sample_project: Path, temp_dir: Path):
        """Test middleware classes are registered in order of discovery."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class FirstMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)

class SecondMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)

class ThirdMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_content = server_file.read_text()

        # Find the positions of each middleware registration
        first_pos = server_content.find("mcp.add_middleware(FirstMiddleware())")
        second_pos = server_content.find("mcp.add_middleware(SecondMiddleware())")
        third_pos = server_content.find("mcp.add_middleware(ThirdMiddleware())")

        # Verify they appear in order
        assert first_pos < second_pos < third_pos
        
    def test_middleware_registered_after_components(self, sample_project: Path, temp_dir: Path):
        """Test middleware is registered after component registration."""
        middleware_file = sample_project / "middleware.py"
        middleware_file.write_text('''
from golf.middleware import Middleware

class TestMiddleware(Middleware):
    async def on_message(self, context, call_next):
        return await call_next(context)
''')
        
        # Create a tool to ensure we have components
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text('''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
''')

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_content = server_file.read_text()

        # Find positions
        tool_reg_pos = server_content.find("mcp.add_tool(")
        middleware_reg_pos = server_content.find("mcp.add_middleware(TestMiddleware())")

        # Middleware should be registered after tools
        assert middleware_reg_pos > tool_reg_pos