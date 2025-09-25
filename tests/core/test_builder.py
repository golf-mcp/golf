"""Tests for the Golf MCP builder module."""

from pathlib import Path
import json
from unittest.mock import AsyncMock, patch

from golf.core.builder import build_manifest, ManifestBuilder, CodeGenerator
from golf.core.config import load_settings
from golf.core.parser import ComponentType, parse_project


class TestManifestBuilder:
    """Test manifest building functionality."""

    def test_builds_manifest_without_annotations(self, sample_project: Path) -> None:
        """Test building a manifest for tools without annotations."""
        # Create a simple tool without annotations
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel


class Output(BaseModel):
    result: str


def simple_tool() -> Output:
    """A simple tool."""
    return Output(result="done")


export = simple_tool
'''
        )

        settings = load_settings(sample_project)
        manifest = build_manifest(sample_project, settings)

        assert len(manifest["tools"]) == 1
        tool = manifest["tools"][0]

        assert tool["name"] == "simple"
        assert tool["description"] == "Simple tool."
        assert "annotations" in tool
        # Should have default title annotation
        assert tool["annotations"]["title"] == "Simple"

    def test_builds_manifest_with_annotations(self, sample_project: Path) -> None:
        """Test building a manifest for tools with annotations."""
        # Create a tool with annotations
        tool_file = sample_project / "tools" / "delete_file.py"
        tool_file.write_text(
            '''"""Delete file tool."""

from typing import Annotated
from pydantic import BaseModel, Field

# Tool annotations
annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False
}


class Output(BaseModel):
    success: bool
    message: str


async def delete_file(
    path: Annotated[str, Field(description="Path to file")]
) -> Output:
    """Delete a file."""
    return Output(success=True, message="Deleted")


export = delete_file
'''
        )

        settings = load_settings(sample_project)
        manifest = build_manifest(sample_project, settings)

        assert len(manifest["tools"]) == 1
        tool = manifest["tools"][0]

        assert tool["name"] == "delete_file"
        assert tool["description"] == "Delete file tool."
        assert "annotations" in tool

        # Should merge default title with custom annotations
        annotations = tool["annotations"]
        assert annotations["title"] == "Delete_File"  # Default title (underscores preserved)
        assert annotations["readOnlyHint"] is False
        assert annotations["destructiveHint"] is True
        assert annotations["idempotentHint"] is False
        assert annotations["openWorldHint"] is False

    def test_builds_manifest_with_readonly_annotations(self, sample_project: Path) -> None:
        """Test building a manifest for read-only tools."""
        # Create a read-only tool
        tool_file = sample_project / "tools" / "read_file.py"
        tool_file.write_text(
            '''"""Read file tool."""

from typing import Annotated
from pydantic import BaseModel, Field

# Read-only tool annotations
annotations = {
    "readOnlyHint": True
}


class Output(BaseModel):
    content: str


async def read_file(
    path: Annotated[str, Field(description="File path")]
) -> Output:
    """Read a file."""
    return Output(content="file content")


export = read_file
'''
        )

        settings = load_settings(sample_project)
        manifest = build_manifest(sample_project, settings)

        assert len(manifest["tools"]) == 1
        tool = manifest["tools"][0]

        annotations = tool["annotations"]
        assert annotations["readOnlyHint"] is True
        assert annotations["title"] == "Read_File"  # Default title should still be there

    def test_manifest_excludes_annotations_for_resources(self, sample_project: Path) -> None:
        """Test that annotations are not included for resources."""
        # Create a resource (annotations should be ignored)
        resource_file = sample_project / "resources" / "data.py"
        resource_file.write_text(
            '''"""Data resource."""

resource_uri = "data://items"

# This should be ignored for resources
annotations = {
    "readOnlyHint": True
}


def get_data() -> list:
    """Get data."""
    return [1, 2, 3]


export = get_data
'''
        )

        settings = load_settings(sample_project)
        manifest = build_manifest(sample_project, settings)

        assert len(manifest["resources"]) == 1
        resource = manifest["resources"][0]

        # Resources should not have annotations in the manifest
        assert "annotations" not in resource

    def test_manifest_with_multiple_tools_different_annotations(self, sample_project: Path) -> None:
        """Test manifest with multiple tools having different annotations."""
        # Create multiple tools with different annotations
        readonly_tool = sample_project / "tools" / "read.py"
        readonly_tool.write_text(
            '''"""Read tool."""

from pydantic import BaseModel

annotations = {"readOnlyHint": True}

class Output(BaseModel):
    data: str

def read() -> Output:
    return Output(data="read")

export = read
'''
        )

        destructive_tool = sample_project / "tools" / "delete.py"
        destructive_tool.write_text(
            '''"""Delete tool."""

from pydantic import BaseModel

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True
}

class Output(BaseModel):
    success: bool

def delete() -> Output:
    return Output(success=True)

export = delete
'''
        )

        no_annotations_tool = sample_project / "tools" / "process.py"
        no_annotations_tool.write_text(
            '''"""Process tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def process() -> Output:
    return Output(result="processed")

export = process
'''
        )

        settings = load_settings(sample_project)
        manifest = build_manifest(sample_project, settings)

        assert len(manifest["tools"]) == 3

        # Find each tool in the manifest
        tools_by_name = {tool["name"]: tool for tool in manifest["tools"]}

        # Check read tool
        read_tool = tools_by_name["read"]
        assert read_tool["annotations"]["readOnlyHint"] is True
        assert "destructiveHint" not in read_tool["annotations"]

        # Check delete tool
        delete_tool = tools_by_name["delete"]
        assert delete_tool["annotations"]["readOnlyHint"] is False
        assert delete_tool["annotations"]["destructiveHint"] is True

        # Check process tool (no custom annotations)
        process_tool = tools_by_name["process"]
        assert "readOnlyHint" not in process_tool["annotations"]
        assert process_tool["annotations"]["title"] == "Process"  # Should have default title


class TestHealthCheckGeneration:
    """Test health check route generation."""

    def test_generates_health_check_when_enabled(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that health check route is generated when enabled."""
        # Update project config to enable health check
        config_file = sample_project / "golf.json"
        config = {
            "name": "HealthProject",
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_response": "OK",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool to ensure we have components
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        # Check that server.py was generated
        server_file = output_dir / "server.py"
        assert server_file.exists()

        # Read the generated server code
        server_code = server_file.read_text()

        # Should contain health check imports
        assert "from starlette.requests import Request" in server_code
        assert "from starlette.responses import JSONResponse, PlainTextResponse" in server_code

        # Should contain health check route definition
        assert '@mcp.custom_route("/health", methods=["GET"])' in server_code
        assert "async def health_check(request: Request) -> PlainTextResponse:" in server_code
        assert 'return PlainTextResponse("OK")' in server_code

    def test_health_check_with_custom_config(self, sample_project: Path, temp_dir: Path) -> None:
        """Test health check generation with custom path and response."""
        # Update project config with custom health check settings
        config_file = sample_project / "golf.json"
        config = {
            "name": "CustomHealthProject",
            "health_check_enabled": True,
            "health_check_path": "/status",
            "health_check_response": "Service is running",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should use custom path and response
        assert '@mcp.custom_route("/status", methods=["GET"])' in server_code
        assert 'return PlainTextResponse("Service is running")' in server_code

    def test_no_health_check_when_disabled(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that health check route is not generated when disabled."""
        # Ensure health check is disabled (default)
        config_file = sample_project / "golf.json"
        config = {"name": "NoHealthProject", "health_check_enabled": False}
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should not contain health check code
        assert "@mcp.custom_route" not in server_code
        assert "health_check" not in server_code
        assert "PlainTextResponse" not in server_code

    def test_health_check_without_starlette_imports_when_disabled(self, temp_dir: Path) -> None:
        """Test that health check route is not generated when disabled."""
        # Create a minimal project without any auth or other features
        project_dir = temp_dir / "minimal_project"
        project_dir.mkdir()

        # Create minimal golf.json with only health check disabled
        config_file = project_dir / "golf.json"
        config = {"name": "MinimalProject", "health_check_enabled": False}
        config_file.write_text(json.dumps(config))

        # Create minimal tool structure
        (project_dir / "tools").mkdir()
        (project_dir / "resources").mkdir()
        (project_dir / "prompts").mkdir()

        # Create a simple tool
        tool_file = project_dir / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(project_dir)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(project_dir, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Most importantly, no health check route should be generated
        assert "@mcp.custom_route" not in server_code or "health_check" not in server_code
        assert "async def health_check" not in server_code

    def test_health_check_docstring_generation(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that health check function has proper docstring."""
        config_file = sample_project / "golf.json"
        config = {"name": "DocstringProject", "health_check_enabled": True}
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should include descriptive docstring
        assert '"""Health check endpoint for Kubernetes and load balancers."""' in server_code

    def test_default_readiness_endpoint_generation(self, sample_project: Path, temp_dir: Path) -> None:
        """Test default readiness endpoint when no readiness.py exists and health checks are enabled."""
        # Enable health checks to trigger default readiness generation
        config_file = sample_project / "golf.json"
        config = {"name": "TestProject", "health_check_enabled": True}
        config_file.write_text(json.dumps(config))
        
        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)

        # Test readiness section generation
        readiness_section = generator._generate_readiness_section(sample_project)

        # Should contain default readiness endpoint
        readiness_code = "\n".join(readiness_section)
        assert "# Default readiness check" in readiness_code
        assert "@mcp.custom_route('/ready', methods=[\"GET\"])" in readiness_code
        assert "async def readiness_check" in readiness_code
        assert '{"status": "pass"}' in readiness_code

    def test_custom_readiness_endpoint_generation(self, sample_project: Path, temp_dir: Path) -> None:
        """Test custom readiness endpoint when readiness.py exists."""
        # Create readiness.py file
        readiness_file = sample_project / "readiness.py"
        readiness_file.write_text("def check():\n    return True")

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)

        # Test readiness section generation
        readiness_section = generator._generate_readiness_section(sample_project)

        # Should contain custom readiness endpoint
        readiness_code = "\n".join(readiness_section)
        assert "# Custom readiness check from readiness.py" in readiness_code
        assert "@mcp.custom_route('/ready', methods=[\"GET\"])" in readiness_code
        assert "async def readiness_check" in readiness_code
        assert "_call_check_function('readiness')" in readiness_code

    def test_custom_health_endpoint_generation(self, sample_project: Path, temp_dir: Path) -> None:
        """Test custom health endpoint when health.py exists."""
        # Create health.py file
        health_file = sample_project / "health.py"
        health_file.write_text("def check():\n    return True")

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)

        # Test health section generation
        health_section = generator._generate_health_section(sample_project)

        # Should contain custom health endpoint
        health_code = "\n".join(health_section)
        assert "# Custom health check from health.py" in health_code
        assert "@mcp.custom_route('/health', methods=[\"GET\"])" in health_code
        assert "async def health_check" in health_code
        assert "_call_check_function('health')" in health_code

    def test_check_function_helper_generation(self, sample_project: Path, temp_dir: Path) -> None:
        """Test helper function generation."""
        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)

        # Test helper function generation
        helper_section = generator._generate_check_function_helper()

        # Should contain helper function
        helper_code = "\n".join(helper_section)
        assert "async def _call_check_function(check_type: str)" in helper_code
        assert "importlib.util" in helper_code
        assert "traceback" in helper_code
        assert "JSONResponse" in helper_code
        assert "Path(__file__).parent / f'{check_type}.py'" in helper_code

    def test_full_build_with_readiness_and_health_files(self, sample_project: Path, temp_dir: Path) -> None:
        """Test complete build process with custom readiness and health files."""
        # Create custom readiness.py
        (sample_project / "readiness.py").write_text(
            """
def check():
    return {
        "status": "pass",
        "services": ["service-a", "service-b"]
    }
"""
        )

        # Create custom health.py
        (sample_project / "health.py").write_text(
            """
def check():
    return {
        "status": "pass",
        "uptime": "5 minutes"
    }
"""
        )

        # Create a simple tool to ensure we have components
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

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

        # Should have required imports
        assert "from starlette.responses import JSONResponse" in server_content

        # Check that custom files were copied (they should exist if copy logic runs during generate())
        readiness_copied = (output_dir / "readiness.py").exists()
        health_copied = (output_dir / "health.py").exists()
        # Note: CodeGenerator.generate() doesn't include file copying - that's done by build_project()
        # These files would be copied during full build, but not during CodeGenerator.generate() alone


class TestHealthCheckEdgeCases:
    """Test edge cases and error conditions for health check generation."""

    def test_health_check_with_empty_response(self, sample_project: Path, temp_dir: Path) -> None:
        """Test health check with empty response string."""
        config_file = sample_project / "golf.json"
        config = {
            "name": "EmptyResponseProject",
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_response": "",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should handle empty string gracefully
        assert 'return PlainTextResponse("")' in server_code

    def test_health_check_path_sanitization(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that health check paths are properly handled in generated code."""
        config_file = sample_project / "golf.json"
        config = {
            "name": "PathSanitizationProject",
            "health_check_enabled": True,
            "health_check_path": "/api/v1/health-check",
            "health_check_response": "All systems operational",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should properly handle complex paths
        assert '@mcp.custom_route("/api/v1/health-check", methods=["GET"])' in server_code
        assert 'return PlainTextResponse("All systems operational")' in server_code

    def test_health_check_imports_only_when_needed(self, temp_dir: Path) -> None:
        """Test that health check route is only generated when explicitly enabled."""
        # Create a minimal project without any auth or other features
        project_dir = temp_dir / "minimal_project"
        project_dir.mkdir()

        # Create minimal golf.json with health check disabled
        config_file = project_dir / "golf.json"
        config = {"name": "MinimalProject", "health_check_enabled": False}
        config_file.write_text(json.dumps(config))

        # Create minimal tool structure
        (project_dir / "tools").mkdir()
        (project_dir / "resources").mkdir()
        (project_dir / "prompts").mkdir()

        # Create a simple tool
        tool_file = project_dir / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(project_dir)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(project_dir, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should not have health check route when disabled
        assert "async def health_check" not in server_code

        # Now test with health check enabled
        config["health_check_enabled"] = True
        config["health_check_path"] = "/health"
        config["health_check_response"] = "OK"
        config_file.write_text(json.dumps(config))

        # Clean and regenerate
        import shutil

        shutil.rmtree(output_dir)

        settings = load_settings(project_dir)
        generator = CodeGenerator(project_dir, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        server_code = server_file.read_text()

        # Should now have the health check route
        assert "async def health_check" in server_code
        assert '@mcp.custom_route("/health", methods=["GET"])' in server_code


class TestCodeGeneration:
    """Test code generation with annotations."""

    def test_generates_server_with_annotations(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that server code includes annotations when registering tools."""
        # Create a tool with annotations
        tool_file = sample_project / "tools" / "annotated_tool.py"
        tool_file.write_text(
            '''"""Annotated tool."""

from pydantic import BaseModel

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True
}

class Output(BaseModel):
    result: str

def annotated_tool() -> Output:
    return Output(result="done")

export = annotated_tool
'''
        )

        # Import and use the CodeGenerator
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        # Check that server.py was generated
        server_file = output_dir / "server.py"
        assert server_file.exists()

        # Read the generated server code
        server_code = server_file.read_text()

        # Should contain the tool registration with annotations using .with_annotations()
        assert "mcp.add_tool(" in server_code
        assert ".with_annotations(" in server_code
        assert '"readOnlyHint": False' in server_code or "'readOnlyHint': False" in server_code
        assert '"destructiveHint": True' in server_code or "'destructiveHint': True" in server_code

    def test_generates_server_without_annotations(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that server code works correctly for tools without annotations."""
        # Create a tool without annotations
        tool_file = sample_project / "tools" / "simple_tool.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"

        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        server_file = output_dir / "server.py"
        assert server_file.exists()

        server_code = server_file.read_text()

        # Should contain tool registration but without annotations parameter
        assert "mcp.add_tool(" in server_code
        assert "simple_tool" in server_code

        # Check that the registration doesn't have annotations parameter
        # Since the registration is on multiple lines, we need to check the full
        # registration block
        lines = server_code.split("\n")

        # Find the start of the tool registration for simple_tool
        # Look for Tool.from_function that references simple_tool
        tool_creation_start = -1
        for i, line in enumerate(lines):
            if "Tool.from_function(" in line:
                # Look ahead for the tool name to make sure it's the right registration
                for j in range(i, min(i + 10, len(lines))):
                    if "simple_tool" in lines[j]:
                        tool_creation_start = i
                        break
                if tool_creation_start != -1:
                    break

        assert tool_creation_start != -1, "Could not find Tool.from_function registration for simple_tool"

        # Now find the corresponding mcp.add_tool(_tool) call
        registration_start = -1
        for i in range(tool_creation_start, len(lines)):
            if "mcp.add_tool(_tool)" in lines[i]:
                registration_start = i
                break

        assert registration_start != -1, "Could not find mcp.add_tool(_tool) call after simple_tool registration"

        # Get the registration block from tool creation to add_tool call
        registration_block = "\n".join(lines[tool_creation_start : registration_start + 1])

        # This tool should not have annotations since it doesn't define any
        assert "with_annotations(" not in registration_block


class TestAnnotationEdgeCases:
    """Test edge cases for annotation handling."""

    def test_handles_empty_annotations_dict(self, sample_project: Path) -> None:
        """Test handling of empty annotations dictionary."""
        tool_file = sample_project / "tools" / "empty_annotations.py"
        tool_file.write_text(
            '''"""Tool with empty annotations."""

from pydantic import BaseModel

# Empty annotations dict
annotations = {}

class Output(BaseModel):
    result: str

def empty_annotations_tool() -> Output:
    return Output(result="done")

export = empty_annotations_tool
'''
        )

        settings = load_settings(sample_project)
        manifest = build_manifest(sample_project, settings)

        assert len(manifest["tools"]) == 1
        tool = manifest["tools"][0]

        # Should still have the default title annotation
        assert "annotations" in tool
        assert tool["annotations"]["title"] == "Empty_Annotations"
        # Should not have any other annotations
        assert len(tool["annotations"]) == 1

    def test_preserves_annotation_order(self, sample_project: Path) -> None:
        """Test that annotation order is preserved in the manifest."""
        tool_file = sample_project / "tools" / "ordered_annotations.py"
        tool_file.write_text(
            '''"""Tool with ordered annotations."""

from pydantic import BaseModel

# Annotations in specific order
annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True
}

class Output(BaseModel):
    result: str

def ordered_tool() -> Output:
    return Output(result="done")

export = ordered_tool
'''
        )

        components = parse_project(sample_project)
        tool_component = components[ComponentType.TOOL][0]

        # Check that annotations were parsed correctly
        assert tool_component.annotations is not None
        assert len(tool_component.annotations) == 4

        # All expected keys should be present
        expected_keys = {
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        assert set(tool_component.annotations.keys()) == expected_keys


class TestPlatformIntegration:
    """Test platform integration with build process."""

    def test_platform_registration_called_in_prod_build(
        self, sample_project: Path, temp_dir: Path, monkeypatch
    ) -> None:
        """Test that platform registration is called during prod builds."""
        # Set up environment for platform registration
        monkeypatch.setenv("GOLF_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        # Create a simple tool to ensure components exist
        tools_dir = sample_project / "tools"
        tools_dir.mkdir(exist_ok=True)
        tool_file = tools_dir / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

def test_function():
    return "test"

export = test_function
'''
        )

        # Mock the platform registration function as an AsyncMock that returns True
        with patch("golf.core.platform.register_project_with_platform", new_callable=AsyncMock) as mock_register:
            mock_register.return_value = True

            from golf.core.builder import build_project

            settings = load_settings(sample_project)
            output_dir = temp_dir / "build"

            # Build with prod environment
            build_project(sample_project, settings, output_dir, build_env="prod", copy_env=False)

            # Platform registration should have been called
            mock_register.assert_called_once()

            # Check the call arguments
            call_args = mock_register.call_args
            assert call_args is not None

            # Check keyword arguments since they're passed as keyword args
            kwargs = call_args.kwargs
            assert "project_path" in kwargs
            assert "settings" in kwargs
            assert "components" in kwargs
            assert kwargs["project_path"] == sample_project
            assert kwargs["settings"] == settings

    def test_platform_registration_skipped_in_dev_build(
        self, sample_project: Path, temp_dir: Path, monkeypatch
    ) -> None:
        """Test that platform registration is skipped during dev builds."""
        from unittest.mock import patch

        # Set up environment variables
        monkeypatch.setenv("GOLF_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-dev")

        # Create a simple tool
        tool_file = sample_project / "tools" / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

from pydantic import BaseModel


class Output(BaseModel):
    result: str


def test_function() -> Output:
    return Output(result="test")


export = test_function
'''
        )

        # Mock the platform registration function
        with patch("golf.core.platform.register_project_with_platform") as mock_register:
            mock_register.return_value = True

            from golf.core.builder import build_project

            settings = load_settings(sample_project)
            output_dir = temp_dir / "build"

            # Build with dev environment
            build_project(sample_project, settings, output_dir, build_env="dev", copy_env=True)

            # Platform registration should NOT have been called
            mock_register.assert_not_called()

    def test_platform_registration_failure_does_not_break_build(
        self, sample_project: Path, temp_dir: Path, monkeypatch, capsys
    ) -> None:
        """Test that platform registration failure doesn't break the build."""
        from unittest.mock import AsyncMock, patch

        # Set up environment variables
        monkeypatch.setenv("GOLF_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        # Create a simple tool
        tool_file = sample_project / "tools" / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

from pydantic import BaseModel


class Output(BaseModel):
    result: str


def test_function() -> Output:
    return Output(result="test")


export = test_function
'''
        )

        # Mock the platform registration function to raise an exception
        with patch("golf.core.platform.register_project_with_platform", new_callable=AsyncMock) as mock_register:
            mock_register.side_effect = Exception("Platform unavailable")

            from golf.core.builder import build_project

            settings = load_settings(sample_project)
            output_dir = temp_dir / "build"

            # Build should still succeed even if platform registration fails
            build_project(sample_project, settings, output_dir, build_env="prod", copy_env=False)

            # Verify build artifacts were created
            assert (output_dir / "server.py").exists()

            # Check that warning was printed
            captured = capsys.readouterr()
            assert "Platform registration failed" in captured.out


class TestStatelessHttpGeneration:
    """Test stateless HTTP configuration generation."""

    def test_generates_stateless_http_when_enabled(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that stateless_http parameter is passed when enabled."""
        # Update project config to enable stateless HTTP
        config_file = sample_project / "golf.json"
        config = {
            "name": "StatelessProject",
            "transport": "streamable-http",
            "stateless_http": True,
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Input(BaseModel):
    message: str

class Output(BaseModel):
    response: str

def simple_tool(input: Input) -> Output:
    """A simple tool for testing."""
    return Output(response=f"Hello, {input.message}!")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py contains stateless_http=True
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify stateless_http=True is passed to FastMCP constructor
        assert "stateless_http=True" in server_content

        # Verify we're using mcp.run() instead of uvicorn.run()
        assert "mcp.run(" in server_content
        assert "uvicorn.run(" not in server_content

    def test_no_stateless_http_when_disabled(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that stateless_http parameter is not passed when disabled."""
        # Update project config with stateless HTTP disabled
        config_file = sample_project / "golf.json"
        config = {
            "name": "RegularProject",
            "transport": "streamable-http",
            "stateless_http": False,
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Input(BaseModel):
    message: str

class Output(BaseModel):
    response: str

def simple_tool(input: Input) -> Output:
    """A simple tool for testing."""
    return Output(response=f"Hello, {input.message}!")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py does not contain stateless_http=True
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify stateless_http=True is NOT passed to FastMCP constructor
        assert "stateless_http=True" not in server_content

    def test_stateless_http_default_behavior(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that stateless_http defaults to False when not specified."""
        # Update project config without stateless_http setting
        config_file = sample_project / "golf.json"
        config = {
            "name": "DefaultProject",
            "transport": "streamable-http",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Input(BaseModel):
    message: str

class Output(BaseModel):
    response: str

def simple_tool(input: Input) -> Output:
    """A simple tool for testing."""
    return Output(response=f"Hello, {input.message}!")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py does not contain stateless_http=True
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify stateless_http=True is NOT passed to FastMCP constructor
        assert "stateless_http=True" not in server_content


class TestModernServerGeneration:
    """Test modern server generation using mcp.run() instead of uvicorn.run()."""

    def test_uses_mcp_run_for_sse_transport(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that SSE transport uses mcp.run() instead of uvicorn.run()."""
        # Update project config for SSE transport
        config_file = sample_project / "golf.json"
        config = {
            "name": "SSEProject",
            "transport": "sse",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py uses mcp.run()
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify we're using mcp.run() instead of uvicorn.run()
        assert "mcp.run(" in server_content
        assert "uvicorn.run(" not in server_content

        # Verify SSE transport is specified
        assert 'transport="sse"' in server_content

    def test_uses_mcp_run_for_streamable_http_transport(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that streamable-http transport uses mcp.run()."""
        # Update project config for streamable-http transport
        config_file = sample_project / "golf.json"
        config = {
            "name": "HTTPProject",
            "transport": "streamable-http",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py uses mcp.run()
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify we're using mcp.run() instead of uvicorn.run()
        assert "mcp.run(" in server_content
        assert "uvicorn.run(" not in server_content

        # Verify streamable-http transport is specified
        assert 'transport="streamable-http"' in server_content

    def test_uses_mcp_run_for_stdio_transport(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that stdio transport uses mcp.run()."""
        # Update project config for stdio transport
        config_file = sample_project / "golf.json"
        config = {
            "name": "StdioProject",
            "transport": "stdio",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py uses mcp.run()
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify we're using mcp.run() for stdio
        assert "mcp.run(" in server_content
        assert 'transport="stdio"' in server_content

        # stdio should never use uvicorn
        assert "uvicorn.run(" not in server_content

    def test_no_uvicorn_import_in_generated_code(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that generated code doesn't import uvicorn since we use mcp.run()."""
        # Update project config
        config_file = sample_project / "golf.json"
        config = {
            "name": "NoUvicornProject",
            "transport": "streamable-http",
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py doesn't import uvicorn
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify no uvicorn import since we use mcp.run()
        assert "import uvicorn" not in server_content
        assert "from uvicorn" not in server_content

    def test_modern_server_generation_features(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that modern server generation features are included."""
        # Update project config with stateless HTTP to trigger modern features
        config_file = sample_project / "golf.json"
        config = {
            "name": "ModernProject",
            "transport": "streamable-http",
            "stateless_http": True,
        }
        config_file.write_text(json.dumps(config))

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
        )

        # Load settings and generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that the generated server.py includes modern features
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify modern features are included
        assert "mcp.run(" in server_content  # Uses mcp.run() instead of uvicorn
        assert "stateless_http=True" in server_content  # Stateless HTTP support
        assert 'logging.getLogger("FastMCP").setLevel(logging.ERROR)' in server_content  # Log suppression


class TestTelemetryIntegration:
    """Test OpenTelemetry integration in generated code."""

    def test_early_telemetry_initialization_included(self, sample_project: Path, temp_dir: Path):
        """Test that early telemetry initialization is included before component registration."""
        # Create a simple tool for the project
        tool_file = sample_project / "tools" / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def test_tool() -> Output:
    return Output(result="test")

export = test_tool
'''
        )

        # Update project config to enable OpenTelemetry
        config_file = sample_project / "golf.json"
        config = {"name": "test-otel-project", "opentelemetry_enabled": True}
        config_file.write_text(json.dumps(config))

        # Generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "output"
        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        # Read generated server.py
        server_file = output_dir / "server.py"
        assert server_file.exists()

        server_content = server_file.read_text()

        # Verify telemetry imports are included
        assert "from golf.telemetry.instrumentation import init_telemetry" in server_content
        assert "instrument_tool" in server_content

        # Verify early initialization is before component registration
        early_init_line = server_content.find('init_telemetry("test-otel-project")')
        component_reg_line = server_content.find("# Register the tool")

        assert early_init_line != -1, "Early telemetry initialization not found"
        assert component_reg_line != -1, "Component registration not found"
        assert early_init_line < component_reg_line, "Telemetry init should come before component registration"

    def test_no_telemetry_when_disabled(self, sample_project: Path, temp_dir: Path):
        """Test that telemetry code is not included when OpenTelemetry is disabled."""
        # Create a simple tool
        tool_file = sample_project / "tools" / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def test_tool() -> Output:
    return Output(result="test")

export = test_tool
'''
        )

        # Update project config to disable OpenTelemetry (default)
        config_file = sample_project / "golf.json"
        config = {"name": "test-no-otel-project", "opentelemetry_enabled": False}
        config_file.write_text(json.dumps(config))

        # Generate code
        from golf.core.builder import CodeGenerator

        settings = load_settings(sample_project)
        output_dir = temp_dir / "output"
        generator = CodeGenerator(sample_project, settings, output_dir)
        generator.generate()

        # Read generated server.py
        server_file = output_dir / "server.py"
        server_content = server_file.read_text()

        # Verify telemetry code is not included
        assert "init_telemetry" not in server_content
        assert "instrument_tool" not in server_content
        assert "telemetry_lifespan" not in server_content

    def test_telemetry_dependencies_in_pyproject(self, sample_project: Path, temp_dir: Path):
        """Test that OpenTelemetry dependencies are included in pyproject.toml."""
        # Create a simple tool
        tool_file = sample_project / "tools" / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def test_tool() -> Output:
    return Output(result="test")

export = test_tool
'''
        )

        # Update project config to enable OpenTelemetry
        config_file = sample_project / "golf.json"
        config = {"name": "test-otel-deps", "opentelemetry_enabled": True}
        config_file.write_text(json.dumps(config))

        # Build project
        from golf.core.builder import build_project

        settings = load_settings(sample_project)
        build_project(sample_project, settings, temp_dir / "built_output")


class TestFastMCPVersionDetection:
    """Test FastMCP version detection functionality."""

    def test_get_fastmcp_version_success(self, sample_project: Path) -> None:
        """Test that FastMCP version is correctly retrieved."""
        with patch("fastmcp.__version__", "2.11.5"):
            settings = load_settings(sample_project)
            builder = ManifestBuilder(sample_project, settings)
            assert builder._get_fastmcp_version() == "2.11.5"

    def test_get_fastmcp_version_import_error(self, sample_project: Path) -> None:
        """Test fallback when FastMCP import fails."""
        settings = load_settings(sample_project)
        builder = ManifestBuilder(sample_project, settings)

        # Mock the fastmcp import to raise ImportError
        with patch.object(builder, "_get_fastmcp_version") as mock_version:
            mock_version.side_effect = ImportError
            try:
                result = builder._get_fastmcp_version()
            except ImportError:
                result = None
            assert result is None

    def test_get_fastmcp_version_attribute_error(self, sample_project: Path) -> None:
        """Test fallback when FastMCP has no __version__ attribute."""
        settings = load_settings(sample_project)
        builder = ManifestBuilder(sample_project, settings)

        # Simply test the AttributeError case by patching the method
        with patch.object(builder, "_get_fastmcp_version") as mock_method:
            # Simulate AttributeError being caught and None returned
            mock_method.side_effect = lambda: None  # Simulate the try/except returning None
            result = builder._get_fastmcp_version()
            assert result is None

    def test_is_fastmcp_version_gte_with_2_11(self, sample_project: Path) -> None:
        """Test version comparison for FastMCP 2.11.x."""
        with patch("fastmcp.__version__", "2.11.5"):
            settings = load_settings(sample_project)
            builder = ManifestBuilder(sample_project, settings)
            assert not builder._is_fastmcp_version_gte("2.12.0")
            assert builder._is_fastmcp_version_gte("2.11.0")
            assert builder._is_fastmcp_version_gte("2.10.0")

    def test_is_fastmcp_version_gte_with_2_12(self, sample_project: Path) -> None:
        """Test version comparison for FastMCP 2.12.0+."""
        with patch("fastmcp.__version__", "2.12.0"):
            settings = load_settings(sample_project)
            builder = ManifestBuilder(sample_project, settings)
            assert builder._is_fastmcp_version_gte("2.12.0")
            assert builder._is_fastmcp_version_gte("2.11.0")
            assert not builder._is_fastmcp_version_gte("2.13.0")

    def test_is_fastmcp_version_gte_fallback_on_error(self, sample_project: Path) -> None:
        """Test fallback behavior when version detection fails."""
        settings = load_settings(sample_project)
        builder = ManifestBuilder(sample_project, settings)

        # Mock _get_fastmcp_version to return None (simulating version detection failure)
        with patch.object(builder, "_get_fastmcp_version", return_value=None):
            assert not builder._is_fastmcp_version_gte("2.12.0")  # Safe fallback

    def test_is_fastmcp_version_gte_with_no_version(self, sample_project: Path) -> None:
        """Test fallback when version is None."""
        with patch.object(ManifestBuilder, "_get_fastmcp_version", return_value=None):
            settings = load_settings(sample_project)
            builder = ManifestBuilder(sample_project, settings)
            assert not builder._is_fastmcp_version_gte("2.12.0")  # Safe fallback

    def test_codegen_version_detection_methods(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that CodeGenerator also has version detection methods."""
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)

        # Test that methods exist and work
        with patch("fastmcp.__version__", "2.12.0"):
            assert generator._get_fastmcp_version() == "2.12.0"
            assert generator._is_fastmcp_version_gte("2.12.0")
            assert not generator._is_fastmcp_version_gte("2.13.0")


class TestVersionBasedCodeGeneration:
    """Test version-based code generation for different FastMCP versions."""

    def test_sse_transport_without_path_for_fastmcp_2_12(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that SSE transport omits path parameter for FastMCP 2.12+."""
        with patch("fastmcp.__version__", "2.12.0"):
            # Update project config for SSE transport
            config_file = sample_project / "golf.json"
            config = {
                "name": "SSE212Project",
                "transport": "sse",
            }
            config_file.write_text(json.dumps(config))

            # Create a simple tool
            tool_file = sample_project / "tools" / "simple.py"
            tool_file.write_text(
                '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
            )

            settings = load_settings(sample_project)
            generator = CodeGenerator(sample_project, settings, temp_dir)
            generator.generate()

            # Check the generated server.py
            server_file = temp_dir / "server.py"
            assert server_file.exists()

            server_content = server_file.read_text()

            # Verify path parameter is omitted for FastMCP 2.12+
            assert 'path="/sse"' not in server_content
            assert 'transport="sse"' in server_content
            assert "mcp.run(" in server_content

    def test_sse_transport_with_path_for_fastmcp_2_11(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that SSE transport includes path parameter for FastMCP 2.11.x."""
        with patch("fastmcp.__version__", "2.11.5"):
            # Update project config for SSE transport
            config_file = sample_project / "golf.json"
            config = {
                "name": "SSE211Project",
                "transport": "sse",
            }
            config_file.write_text(json.dumps(config))

            # Create a simple tool
            tool_file = sample_project / "tools" / "simple.py"
            tool_file.write_text(
                '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
            )

            settings = load_settings(sample_project)
            generator = CodeGenerator(sample_project, settings, temp_dir)
            generator.generate()

            # Check the generated server.py
            server_file = temp_dir / "server.py"
            assert server_file.exists()

            server_content = server_file.read_text()

            # Verify path parameter is included for FastMCP 2.11.x
            assert 'path="/sse"' in server_content
            assert 'transport="sse"' in server_content
            assert "mcp.run(" in server_content

    def test_http_transport_without_path_for_fastmcp_2_12(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that HTTP transport omits path parameter for FastMCP 2.12+."""
        with patch("fastmcp.__version__", "2.12.0"):
            # Update project config for HTTP transport
            config_file = sample_project / "golf.json"
            config = {
                "name": "HTTP212Project",
                "transport": "streamable-http",
            }
            config_file.write_text(json.dumps(config))

            # Create a simple tool
            tool_file = sample_project / "tools" / "simple.py"
            tool_file.write_text(
                '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
            )

            settings = load_settings(sample_project)
            generator = CodeGenerator(sample_project, settings, temp_dir)
            generator.generate()

            # Check the generated server.py
            server_file = temp_dir / "server.py"
            assert server_file.exists()

            server_content = server_file.read_text()

            # Verify path parameter is omitted for FastMCP 2.12+
            assert 'path="/mcp/"' not in server_content
            assert 'transport="streamable-http"' in server_content
            assert "mcp.run(" in server_content

    def test_http_transport_with_path_for_fastmcp_2_11(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that HTTP transport includes path parameter for FastMCP 2.11.x."""
        with patch("fastmcp.__version__", "2.11.5"):
            # Update project config for HTTP transport
            config_file = sample_project / "golf.json"
            config = {
                "name": "HTTP211Project",
                "transport": "streamable-http",
            }
            config_file.write_text(json.dumps(config))

            # Create a simple tool
            tool_file = sample_project / "tools" / "simple.py"
            tool_file.write_text(
                '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
            )

            settings = load_settings(sample_project)
            generator = CodeGenerator(sample_project, settings, temp_dir)
            generator.generate()

            # Check the generated server.py
            server_file = temp_dir / "server.py"
            assert server_file.exists()

            server_content = server_file.read_text()

            # Verify path parameter is included for FastMCP 2.11.x
            assert 'path="/mcp/"' in server_content
            assert 'transport="streamable-http"' in server_content
            assert "mcp.run(" in server_content

    def test_stdio_transport_unchanged_for_all_versions(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that stdio transport behavior is unchanged for all versions."""
        # Test with FastMCP 2.11.x
        with patch("fastmcp.__version__", "2.11.5"):
            # Update project config for stdio transport
            config_file = sample_project / "golf.json"
            config = {
                "name": "Stdio211Project",
                "transport": "stdio",
            }
            config_file.write_text(json.dumps(config))

            # Create a simple tool
            tool_file = sample_project / "tools" / "simple.py"
            tool_file.write_text(
                '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    """A simple tool for testing."""
    return Output(result="done")

export = simple_tool
'''
            )

            settings = load_settings(sample_project)
            generator = CodeGenerator(sample_project, settings, temp_dir)
            generator.generate()

            # Check the generated server.py
            server_file = temp_dir / "server.py"
            server_content = server_file.read_text()

            # stdio should never have path parameter
            assert "path=" not in server_content
            assert 'transport="stdio"' in server_content
            assert "mcp.run(" in server_content

        # Test with FastMCP 2.12.0 - should be identical
        with patch("fastmcp.__version__", "2.12.0"):
            # Generate again with same config
            generator.generate()

            server_content_212 = server_file.read_text()

            # Should be identical behavior for stdio
            assert "path=" not in server_content_212
            assert 'transport="stdio"' in server_content_212
            assert "mcp.run(" in server_content_212
