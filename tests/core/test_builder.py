"""Tests for the Golf MCP builder module."""

from pathlib import Path

from golf.core.builder import build_manifest
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
        assert (
            annotations["title"] == "Delete_File"
        )  # Default title (underscores preserved)
        assert annotations["readOnlyHint"] is False
        assert annotations["destructiveHint"] is True
        assert annotations["idempotentHint"] is False
        assert annotations["openWorldHint"] is False

    def test_builds_manifest_with_readonly_annotations(
        self, sample_project: Path
    ) -> None:
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
        assert (
            annotations["title"] == "Read_File"
        )  # Default title should still be there

    def test_manifest_excludes_annotations_for_resources(
        self, sample_project: Path
    ) -> None:
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

    def test_manifest_with_multiple_tools_different_annotations(
        self, sample_project: Path
    ) -> None:
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
        assert (
            process_tool["annotations"]["title"] == "Process"
        )  # Should have default title


class TestCodeGeneration:
    """Test code generation with annotations."""

    def test_generates_server_with_annotations(
        self, sample_project: Path, temp_dir: Path
    ) -> None:
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

        # Should contain the tool registration with annotations
        assert "mcp.add_tool(" in server_code
        assert "annotations=" in server_code
        assert (
            '"readOnlyHint": False' in server_code
            or "'readOnlyHint': False" in server_code
        )
        assert (
            '"destructiveHint": True' in server_code
            or "'destructiveHint': True" in server_code
        )

    def test_generates_server_without_annotations(
        self, sample_project: Path, temp_dir: Path
    ) -> None:
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
        registration_start = -1
        for i, line in enumerate(lines):
            if "mcp.add_tool(" in line:
                # Look ahead for the tool name to make sure it's the right registration
                for j in range(i, min(i + 10, len(lines))):
                    if "simple_tool" in lines[j]:
                        registration_start = i
                        break
                if registration_start != -1:
                    break

        assert registration_start != -1, (
            "Could not find mcp.add_tool registration for simple_tool"
        )

        # Get the registration block (until the closing parenthesis)
        registration_end = registration_start
        paren_count = 0
        for i in range(registration_start, len(lines)):
            line = lines[i]
            paren_count += line.count("(") - line.count(")")
            if paren_count == 0 and ")" in line:
                registration_end = i
                break

        registration_block = "\n".join(lines[registration_start : registration_end + 1])

        # This tool should not have annotations since it doesn't define any
        assert "annotations=" not in registration_block


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
