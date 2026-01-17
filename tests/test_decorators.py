"""Tests for Golf decorators module."""

from golf import prompt, resource, tool
from golf.decorators import prompt as prompt_dec
from golf.decorators import resource as resource_dec
from golf.decorators import tool as tool_dec


class TestDecorators:
    """Test the decorator functions."""

    def test_tool_decorator_sets_golf_name(self) -> None:
        """Test that @tool sets _golf_name attribute."""

        @tool(name="my_tool")
        def my_func() -> str:
            return "result"

        assert hasattr(my_func, "_golf_name")
        assert my_func._golf_name == "my_tool"

    def test_resource_decorator_sets_golf_name(self) -> None:
        """Test that @resource sets _golf_name attribute."""

        @resource(name="my_resource")
        def my_func() -> str:
            return "result"

        assert hasattr(my_func, "_golf_name")
        assert my_func._golf_name == "my_resource"

    def test_prompt_decorator_sets_golf_name(self) -> None:
        """Test that @prompt sets _golf_name attribute."""

        @prompt(name="my_prompt")
        def my_func() -> str:
            return "result"

        assert hasattr(my_func, "_golf_name")
        assert my_func._golf_name == "my_prompt"

    def test_decorator_preserves_function(self) -> None:
        """Test that decorator returns the same function."""

        @tool(name="test")
        def original() -> str:
            return "original"

        assert original() == "original"

    def test_decorators_exported_from_main_package(self) -> None:
        """Test that decorators are accessible from golf package."""
        # These imports should work
        assert tool_dec is tool
        assert resource_dec is resource
        assert prompt_dec is prompt
