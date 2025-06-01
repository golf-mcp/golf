"""Tests for the Golf MCP parser module."""

from pathlib import Path

import pytest

from golf.core.parser import (
    AstParser,
    ComponentType,
    parse_project,
)


class TestComponentDiscovery:
    """Test component discovery functionality."""

    def test_discovers_tool_files(self, sample_project: Path) -> None:
        """Test that tool files are discovered correctly."""
        # Create a tool file
        tool_file = sample_project / "tools" / "test_tool.py"
        tool_file.write_text(
            '''"""Test tool."""

def run() -> dict:
    """Run the tool."""
    return {"result": "success"}

export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_directory(sample_project / "tools")

        assert len(components) == 1
        assert components[0].type == ComponentType.TOOL
        assert components[0].name == "test_tool"
        assert components[0].docstring == "Test tool."

    def test_discovers_nested_components(self, sample_project: Path) -> None:
        """Test discovery of components in nested directories."""
        # Create nested structure
        nested_dir = sample_project / "tools" / "payments" / "stripe"
        nested_dir.mkdir(parents=True)

        tool_file = nested_dir / "charge.py"
        tool_file.write_text(
            '''"""Create a charge."""

def run() -> dict:
    """Process payment."""
    return {"charged": True}

export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_directory(sample_project / "tools")

        assert len(components) == 1
        assert components[0].name == "charge-stripe-payments"
        assert components[0].parent_module == "payments.stripe"

    def test_skips_pycache_and_hidden_files(self, sample_project: Path) -> None:
        """Test that __pycache__ and hidden directories are skipped."""
        # Create __pycache__ directory
        pycache = sample_project / "tools" / "__pycache__"
        pycache.mkdir()
        (pycache / "test.pyc").write_text("compiled")

        # Create hidden directory
        hidden = sample_project / "tools" / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text(
            '''"""Secret tool."""
def run(): pass
export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_directory(sample_project / "tools")

        assert len(components) == 0

    def test_ignores_common_py_files(self, sample_project: Path) -> None:
        """Test that common.py files are not returned as components."""
        common_file = sample_project / "tools" / "common.py"
        common_file.write_text(
            '''"""Common utilities."""

def shared_function():
    return "shared"
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_directory(sample_project / "tools")

        assert len(components) == 0


class TestComponentParsing:
    """Test individual component parsing."""

    def test_parses_tool_with_input_output_classes(self, sample_project: Path) -> None:
        """Test parsing a tool with Input and Output Pydantic models."""
        tool_file = sample_project / "tools" / "calculator.py"
        tool_file.write_text(
            '''"""Calculator tool."""

from pydantic import BaseModel, Field
from typing import Annotated


class Input(BaseModel):
    """Input for calculator."""
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


class Output(BaseModel):
    """Output from calculator."""
    result: int


async def add(a: Annotated[int, Field(description="First number")], 
              b: Annotated[int, Field(description="Second number")]) -> Output:
    """Add two numbers."""
    return Output(result=a + b)


export = add
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.TOOL
        assert component.entry_function == "add"
        assert component.input_schema is not None
        assert "properties" in component.input_schema
        assert "a" in component.input_schema["properties"]
        assert "b" in component.input_schema["properties"]

    def test_parses_tool_with_annotations(self, sample_project: Path) -> None:
        """Test parsing a tool with annotations."""
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
    """Response from delete file tool."""
    success: bool
    message: str


async def delete_file(
    path: Annotated[str, Field(description="Path to file to delete")]
) -> Output:
    """Delete a file."""
    return Output(success=True, message="Deleted")


export = delete_file
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.TOOL
        assert component.annotations is not None
        assert component.annotations["readOnlyHint"] is False
        assert component.annotations["destructiveHint"] is True
        assert component.annotations["idempotentHint"] is False
        assert component.annotations["openWorldHint"] is False

    def test_parses_tool_with_readonly_annotations(self, sample_project: Path) -> None:
        """Test parsing a tool with read-only annotations."""
        tool_file = sample_project / "tools" / "read_file.py"
        tool_file.write_text(
            '''"""Read file tool."""

from typing import Annotated
from pydantic import BaseModel, Field

# Tool annotations - read-only operation
annotations = {
    "readOnlyHint": True
}


class Output(BaseModel):
    """Response from read file tool."""
    content: str


async def read_file(
    path: Annotated[str, Field(description="Path to file to read")]
) -> Output:
    """Read a file."""
    return Output(content="file content")


export = read_file
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.TOOL
        assert component.annotations is not None
        assert component.annotations["readOnlyHint"] is True
        # Should only have readOnlyHint since other hints are ignored when readOnlyHint is True
        assert len(component.annotations) == 1

    def test_parses_tool_without_annotations(self, sample_project: Path) -> None:
        """Test parsing a tool without annotations."""
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from typing import Annotated
from pydantic import BaseModel, Field


class Output(BaseModel):
    """Simple output."""
    result: str


async def simple_tool(
    input_text: Annotated[str, Field(description="Input text")]
) -> Output:
    """Simple tool without annotations."""
    return Output(result="processed")


export = simple_tool
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.TOOL
        assert component.annotations is None

    def test_handles_complex_annotations(self, sample_project: Path) -> None:
        """Test parsing tool with various annotation value types."""
        tool_file = sample_project / "tools" / "complex_annotations.py"
        tool_file.write_text(
            '''"""Tool with complex annotations."""

from pydantic import BaseModel

# Tool annotations with different value types
annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
    "customHint": "custom_value",
    "numericHint": 42
}


class Output(BaseModel):
    result: str


def complex_tool() -> Output:
    """Tool with complex annotations."""
    return Output(result="done")


export = complex_tool
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.TOOL
        assert component.annotations is not None
        assert component.annotations["readOnlyHint"] is False
        assert component.annotations["destructiveHint"] is True
        assert component.annotations["customHint"] == "custom_value"
        assert component.annotations["numericHint"] == 42

    def test_ignores_non_dict_annotations(self, sample_project: Path) -> None:
        """Test that non-dictionary annotations are ignored."""
        tool_file = sample_project / "tools" / "invalid_annotations.py"
        tool_file.write_text(
            '''"""Tool with invalid annotations."""

from pydantic import BaseModel

# This should be ignored since it's not a dictionary
annotations = "not a dict"


class Output(BaseModel):
    result: str


def invalid_tool() -> Output:
    """Tool with invalid annotations."""
    return Output(result="done")


export = invalid_tool
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.TOOL
        assert component.annotations is None

    def test_annotations_only_for_tools(self, sample_project: Path) -> None:
        """Test that annotations are only parsed for tools, not resources or prompts."""
        # Test resource with annotations (should be ignored)
        resource_file = sample_project / "resources" / "annotated_resource.py"
        resource_file.write_text(
            '''"""Resource with annotations."""

resource_uri = "test://data"

# This should be ignored for resources
annotations = {
    "readOnlyHint": True
}


def get_data() -> dict:
    """Get data."""
    return {"data": "value"}


export = get_data
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(resource_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.RESOURCE
        # Resources shouldn't have annotations parsed
        assert component.annotations is None

    def test_parses_resource_with_uri_template(self, sample_project: Path) -> None:
        """Test parsing a resource with URI template."""
        resource_file = sample_project / "resources" / "weather.py"
        resource_file.write_text(
            '''"""Weather resource."""

resource_uri = "weather://current/{city}"


async def get_weather(city: str) -> dict:
    """Get weather for a city."""
    return {"city": city, "temp": 72}


export = get_weather
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(resource_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.RESOURCE
        assert component.uri_template == "weather://current/{city}"
        assert component.parameters == ["city"]

    def test_parses_prompt(self, sample_project: Path) -> None:
        """Test parsing a prompt component."""
        prompt_file = sample_project / "prompts" / "greeting.py"
        prompt_file.write_text(
            '''"""Greeting prompt."""


async def greet(name: str) -> list:
    """Generate a greeting prompt."""
    return [
        {"role": "system", "content": "You are a friendly assistant."},
        {"role": "user", "content": f"Say hello to {name}"}
    ]


export = greet
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(prompt_file)

        assert len(components) == 1
        component = components[0]

        assert component.type == ComponentType.PROMPT
        assert component.parameters == ["name"]

    def test_fails_without_module_docstring(self, sample_project: Path) -> None:
        """Test that parsing fails without a module docstring."""
        tool_file = sample_project / "tools" / "no_docstring.py"
        tool_file.write_text(
            """
def run():
    return "no docstring"

export = run
"""
        )

        parser = AstParser(sample_project)
        with pytest.raises(ValueError, match="Missing module docstring"):
            parser.parse_file(tool_file)

    def test_fails_without_return_annotation(self, sample_project: Path) -> None:
        """Test that parsing fails without return type annotation."""
        tool_file = sample_project / "tools" / "no_return.py"
        tool_file.write_text(
            '''"""Tool without return type."""

def run():
    return "no return type"

export = run
'''
        )

        parser = AstParser(sample_project)
        with pytest.raises(ValueError, match="Missing return annotation"):
            parser.parse_file(tool_file)

    def test_handles_export_fallback_to_run(self, sample_project: Path) -> None:
        """Test fallback to 'run' function when no export is specified."""
        tool_file = sample_project / "tools" / "fallback.py"
        tool_file.write_text(
            '''"""Tool with run function."""

def run() -> dict:
    """Run the tool."""
    return {"status": "ok"}
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        assert components[0].entry_function == "run"


class TestIDGeneration:
    """Test component ID generation."""

    def test_simple_id_generation(self, sample_project: Path) -> None:
        """Test ID generation for files directly in category directory."""
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""
def run() -> str:
    return "simple"
export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert components[0].name == "simple"

    def test_nested_id_generation(self, sample_project: Path) -> None:
        """Test ID generation for nested files."""
        # Create nested structure: tools/payments/stripe/refund.py
        nested_dir = sample_project / "tools" / "payments" / "stripe"
        nested_dir.mkdir(parents=True)

        tool_file = nested_dir / "refund.py"
        tool_file.write_text(
            '''"""Refund tool."""
def run() -> dict:
    return {"refunded": True}
export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        # According to spec: filename + reversed parent dirs
        # refund + stripe + payments = "refund-stripe-payments"
        assert components[0].name == "refund-stripe-payments"

    def test_id_collision_detection(self, sample_project: Path) -> None:
        """Test that ID collisions are detected."""
        # Create two files that would generate the same ID
        tool1 = sample_project / "tools" / "test.py"
        tool1.write_text(
            '''"""Tool 1."""
def run() -> str:
    return "1"
export = run
'''
        )

        # Create a nested structure that would collide
        nested_dir = sample_project / "resources" / "test"
        nested_dir.mkdir(parents=True)

        # This would also generate ID "test"
        resource = sample_project / "resources" / "test.py"
        resource.write_text(
            '''"""Resource."""
resource_uri = "test://data"
def run() -> str:
    return "resource"
export = run
'''
        )

        with pytest.raises(ValueError, match="ID collision detected"):
            parse_project(sample_project)


class TestProjectParsing:
    """Test full project parsing."""

    def test_parse_complete_project(self, sample_project: Path) -> None:
        """Test parsing a complete project with multiple components."""
        # Create tool
        tool = sample_project / "tools" / "greet.py"
        tool.write_text(
            '''"""Greeting tool."""
def greet() -> str:
    """Greet someone."""
    return "Hello!"
export = greet
'''
        )

        # Create resource
        resource = sample_project / "resources" / "data.py"
        resource.write_text(
            '''"""Data resource."""
resource_uri = "data://items"
def get_data() -> list:
    """Get data."""
    return [1, 2, 3]
export = get_data
'''
        )

        # Create prompt
        prompt = sample_project / "prompts" / "chat.py"
        prompt.write_text(
            '''"""Chat prompt."""
def chat() -> list:
    """Start a chat."""
    return [{"role": "system", "content": "Chat started"}]
export = chat
'''
        )

        components = parse_project(sample_project)

        assert len(components[ComponentType.TOOL]) == 1
        assert len(components[ComponentType.RESOURCE]) == 1
        assert len(components[ComponentType.PROMPT]) == 1

        assert components[ComponentType.TOOL][0].name == "greet"
        assert components[ComponentType.RESOURCE][0].name == "data"
        assert components[ComponentType.PROMPT][0].name == "chat"


class TestASTDictionaryExtraction:
    """Test AST dictionary extraction helper method."""

    def test_extract_dict_with_boolean_values(self, sample_project: Path) -> None:
        """Test extracting dictionary with boolean values from AST."""
        tool_file = sample_project / "tools" / "bool_test.py"
        tool_file.write_text(
            '''"""Tool with boolean annotations."""

annotations = {
    "readOnlyHint": True,
    "destructiveHint": False
}

def run() -> str:
    return "test"

export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]
        assert component.annotations["readOnlyHint"] is True
        assert component.annotations["destructiveHint"] is False

    def test_extract_dict_with_mixed_types(self, sample_project: Path) -> None:
        """Test extracting dictionary with mixed value types."""
        tool_file = sample_project / "tools" / "mixed_test.py"
        tool_file.write_text(
            '''"""Tool with mixed type annotations."""

annotations = {
    "readOnlyHint": True,
    "customString": "test_value",
    "customNumber": 42,
    "customFloat": 3.14,
    "customNull": None
}

def run() -> str:
    return "test"

export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]
        assert component.annotations["readOnlyHint"] is True
        assert component.annotations["customString"] == "test_value"
        assert component.annotations["customNumber"] == 42
        assert component.annotations["customFloat"] == 3.14
        assert component.annotations["customNull"] is None

    def test_extract_dict_ignores_non_string_keys(self, sample_project: Path) -> None:
        """Test that non-string keys are ignored during extraction."""
        # This test is a bit artificial since we can't easily create non-string
        # keys in Python dict literals, but we can test the robustness
        tool_file = sample_project / "tools" / "string_keys_test.py"
        tool_file.write_text(
            '''"""Tool with string key annotations."""

annotations = {
    "readOnlyHint": True,
    "validKey": "validValue"
}

def run() -> str:
    return "test"

export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)

        assert len(components) == 1
        component = components[0]
        # Should have both valid string keys
        assert len(component.annotations) == 2
        assert component.annotations["readOnlyHint"] is True
        assert component.annotations["validKey"] == "validValue"

    def test_extract_dict_handles_complex_expressions(self, sample_project: Path) -> None:
        """Test that complex expressions in dict values are handled gracefully."""
        tool_file = sample_project / "tools" / "complex_test.py"
        tool_file.write_text(
            '''"""Tool with complex annotations."""

# Define a variable that could be used in complex expressions
some_var = "complex"

# This should only extract the simple literal values
annotations = {
    "readOnlyHint": True,
    "simpleString": "simple",
    "variableReference": some_var,  # This should be ignored (not a literal)
    "anotherSimple": False
}

def run() -> str:
    return "test"

export = run
'''
        )

        parser = AstParser(sample_project)
        components = parser.parse_file(tool_file)
        
        assert len(components) == 1
        component = components[0]
        
        # Should have extracted the simple literal values
        assert component.annotations["readOnlyHint"] is True
        assert component.annotations["simpleString"] == "simple"
        assert component.annotations["anotherSimple"] is False
        
        # Variable reference should be ignored (not present in annotations)
        assert "variableReference" not in component.annotations
