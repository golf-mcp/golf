"""Tests for Golf MCP platform registration."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from golf.core.config import load_settings
from golf.core.parser import ComponentType, ParsedComponent, parse_project
from golf.core.platform import (
    _build_component_list,
    _get_component_counts,
    register_project_with_platform,
)


class TestPlatformRegistration:
    """Test platform registration functionality."""

    @pytest.mark.asyncio
    async def test_successful_registration(
        self, sample_project: Path, httpx_mock, monkeypatch
    ) -> None:
        """Test successful platform registration with API key and server ID."""
        # Set environment variables
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        # Create a sample tool
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

        # Mock successful HTTP response
        httpx_mock.add_response(
            method="POST",
            url="https://api.golf.dev/api/v1/projects",
            json={"status": "success", "project_id": "123"},
            status_code=200,
        )

        # Load settings and parse components
        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        # Test registration
        result = await register_project_with_platform(
            sample_project, settings, components
        )

        assert result is True

        # Verify the HTTP request was made correctly
        request = httpx_mock.get_request()
        assert request.method == "POST"
        assert request.url == "https://api.golf.dev/api/v1/projects"
        assert request.headers["Authorization"] == "Bearer test-api-key"
        assert request.headers["Content-Type"] == "application/json"
        assert "Golf-MCP/" in request.headers["User-Agent"]

        # Verify request payload
        payload = json.loads(request.content)
        assert payload["project_name"] == "TestProject"
        assert payload["server_id"] == "test-server-prod"
        assert payload["golf_version"] is not None
        assert "components" in payload
        assert "component_counts" in payload

    @pytest.mark.asyncio
    async def test_skips_registration_without_api_key(
        self, sample_project: Path, monkeypatch
    ) -> None:
        """Test that registration is skipped when no API key is provided."""
        # Ensure no API key is set
        monkeypatch.delenv("GOLF_PLATFORM_API_KEY", raising=False)
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        result = await register_project_with_platform(
            sample_project, settings, components
        )

        # Should return True (success) but skip registration
        assert result is True

    @pytest.mark.asyncio
    async def test_skips_registration_without_server_id(
        self, sample_project: Path, monkeypatch, capsys
    ) -> None:
        """Test that registration is skipped when no server ID is provided."""
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "test-api-key")
        # Ensure no server ID is set
        monkeypatch.delenv("GOLF_SERVER_ID", raising=False)

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        result = await register_project_with_platform(
            sample_project, settings, components
        )

        # Should return True (success) but skip registration
        assert result is True

        # Check that warning message was printed (handle multiline output)
        captured = capsys.readouterr()
        assert "GOLF_SERVER_ID environment variable required" in captured.out.replace("\n", " ").replace("  ", " ")

    @pytest.mark.asyncio
    async def test_handles_http_timeout(
        self, sample_project: Path, monkeypatch, capsys
    ) -> None:
        """Test handling of HTTP timeout errors."""
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        # Mock timeout exception
        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_context
            mock_context.post.side_effect = httpx.TimeoutException("Request timed out")

            result = await register_project_with_platform(
                sample_project, settings, components
            )

        assert result is False
        captured = capsys.readouterr()
        assert "Platform registration timed out" in captured.out

    @pytest.mark.asyncio
    async def test_handles_auth_errors(
        self, sample_project: Path, httpx_mock, monkeypatch, capsys
    ) -> None:
        """Test handling of authentication errors."""
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "invalid-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        # Mock 401 Unauthorized response
        httpx_mock.add_response(
            method="POST",
            url="https://api.golf.dev/api/v1/projects",
            status_code=401,
        )

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        result = await register_project_with_platform(
            sample_project, settings, components
        )

        assert result is False
        captured = capsys.readouterr()
        assert "invalid API key" in captured.out

    @pytest.mark.asyncio
    async def test_handles_forbidden_errors(
        self, sample_project: Path, httpx_mock, monkeypatch, capsys
    ) -> None:
        """Test handling of forbidden access errors."""
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "valid-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        # Mock 403 Forbidden response
        httpx_mock.add_response(
            method="POST",
            url="https://api.golf.dev/api/v1/projects",
            status_code=403,
        )

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        result = await register_project_with_platform(
            sample_project, settings, components
        )

        assert result is False
        captured = capsys.readouterr()
        assert "access denied" in captured.out

    @pytest.mark.asyncio
    async def test_handles_server_errors(
        self, sample_project: Path, httpx_mock, monkeypatch, capsys
    ) -> None:
        """Test handling of server errors."""
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        # Mock 500 Internal Server Error response
        httpx_mock.add_response(
            method="POST",
            url="https://api.golf.dev/api/v1/projects",
            status_code=500,
        )

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        result = await register_project_with_platform(
            sample_project, settings, components
        )

        assert result is False
        captured = capsys.readouterr()
        assert "HTTP 500" in captured.out

    @pytest.mark.asyncio
    async def test_handles_network_errors(
        self, sample_project: Path, monkeypatch, capsys
    ) -> None:
        """Test handling of network errors."""
        monkeypatch.setenv("GOLF_PLATFORM_API_KEY", "test-api-key")
        monkeypatch.setenv("GOLF_SERVER_ID", "test-server-prod")

        settings = load_settings(sample_project)
        components = parse_project(sample_project)

        # Mock network error
        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_context
            mock_context.post.side_effect = httpx.NetworkError("Connection failed")

            result = await register_project_with_platform(
                sample_project, settings, components
            )

        assert result is False
        captured = capsys.readouterr()
        assert "Platform registration failed" in captured.out


class TestComponentListBuilder:
    """Test component list building functionality."""

    def test_builds_component_list_with_tools(self, sample_project: Path) -> None:
        """Test building component list with tools."""
        # Create mock tool component
        tool_component = ParsedComponent(
            name="test-tool",
            type=ComponentType.TOOL,
            file_path=sample_project / "tools" / "test.py",
            module_path="tools/test.py",
            docstring="Test tool description",
            entry_function="test_function",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            annotations={"title": "Test Tool"},
            parameters=["name"],
        )

        components = {ComponentType.TOOL: [tool_component]}
        component_list = _build_component_list(components)

        assert len(component_list) == 1
        assert component_list[0]["name"] == "test-tool"
        assert component_list[0]["type"] == "tool"
        assert component_list[0]["description"] == "Test tool description"
        assert component_list[0]["entry_function"] == "test_function"
        assert component_list[0]["input_schema"] is not None
        assert component_list[0]["output_schema"] is not None
        assert component_list[0]["annotations"] == {"title": "Test Tool"}
        assert component_list[0]["parameters"] == ["name"]

    def test_builds_component_list_with_resources(self, sample_project: Path) -> None:
        """Test building component list with resources."""
        # Create mock resource component
        resource_component = ParsedComponent(
            name="test-resource",
            type=ComponentType.RESOURCE,
            file_path=sample_project / "resources" / "test.py",
            module_path="resources/test.py",
            docstring="Test resource description",
            entry_function="get_resource",
            uri_template="/api/users/{user_id}",
            parameters=["user_id"],
        )

        components = {ComponentType.RESOURCE: [resource_component]}
        component_list = _build_component_list(components)

        assert len(component_list) == 1
        assert component_list[0]["name"] == "test-resource"
        assert component_list[0]["type"] == "resource"
        assert component_list[0]["description"] == "Test resource description"
        assert component_list[0]["entry_function"] == "get_resource"
        assert component_list[0]["uri_template"] == "/api/users/{user_id}"
        assert component_list[0]["parameters"] == ["user_id"]

    def test_builds_component_list_with_prompts(self, sample_project: Path) -> None:
        """Test building component list with prompts."""
        # Create mock prompt component
        prompt_component = ParsedComponent(
            name="test-prompt",
            type=ComponentType.PROMPT,
            file_path=sample_project / "prompts" / "test.py",
            module_path="prompts/test.py",
            docstring="Test prompt description",
            entry_function="generate_prompt",
            parameters=["context"],
        )

        components = {ComponentType.PROMPT: [prompt_component]}
        component_list = _build_component_list(components)

        assert len(component_list) == 1
        assert component_list[0]["name"] == "test-prompt"
        assert component_list[0]["type"] == "prompt"
        assert component_list[0]["description"] == "Test prompt description"
        assert component_list[0]["entry_function"] == "generate_prompt"
        # Only check for parameters if they exist
        if "parameters" in component_list[0]:
            assert component_list[0]["parameters"] == ["context"]

    def test_handles_mixed_component_types(self, sample_project: Path) -> None:
        """Test building component list with mixed component types."""
        tool_component = ParsedComponent(
            name="tool",
            type=ComponentType.TOOL,
            file_path=sample_project / "tools" / "tool.py",
            module_path="tools/tool.py",
            docstring="Tool description",
        )

        resource_component = ParsedComponent(
            name="resource",
            type=ComponentType.RESOURCE,
            file_path=sample_project / "resources" / "resource.py",
            module_path="resources/resource.py",
            docstring="Resource description",
            uri_template="/api/resource",
        )

        prompt_component = ParsedComponent(
            name="prompt",
            type=ComponentType.PROMPT,
            file_path=sample_project / "prompts" / "prompt.py",
            module_path="prompts/prompt.py",
            docstring="Prompt description",
        )

        components = {
            ComponentType.TOOL: [tool_component],
            ComponentType.RESOURCE: [resource_component],
            ComponentType.PROMPT: [prompt_component],
        }

        component_list = _build_component_list(components)

        assert len(component_list) == 3
        component_types = [comp["type"] for comp in component_list]
        assert "tool" in component_types
        assert "resource" in component_types
        assert "prompt" in component_types


class TestComponentCounts:
    """Test component count calculation."""

    def test_counts_empty_components(self) -> None:
        """Test counting empty component dictionary."""
        components = {}
        counts = _get_component_counts(components)

        assert counts["tools"] == 0
        assert counts["resources"] == 0
        assert counts["prompts"] == 0
        assert counts["total"] == 0

    def test_counts_mixed_components(self, sample_project: Path) -> None:
        """Test counting mixed component types."""
        tool1 = ParsedComponent(
            name="tool1",
            type=ComponentType.TOOL,
            file_path=sample_project / "tools" / "tool1.py",
            module_path="tools/tool1.py",
        )
        tool2 = ParsedComponent(
            name="tool2",
            type=ComponentType.TOOL,
            file_path=sample_project / "tools" / "tool2.py",
            module_path="tools/tool2.py",
        )

        resource1 = ParsedComponent(
            name="resource1",
            type=ComponentType.RESOURCE,
            file_path=sample_project / "resources" / "resource1.py",
            module_path="resources/resource1.py",
            uri_template="/api/resource1",
        )

        components = {
            ComponentType.TOOL: [tool1, tool2],
            ComponentType.RESOURCE: [resource1],
            ComponentType.PROMPT: [],
        }

        counts = _get_component_counts(components)

        assert counts["tools"] == 2
        assert counts["resources"] == 1
        assert counts["prompts"] == 0
        assert counts["total"] == 3

    def test_counts_with_missing_component_types(self, sample_project: Path) -> None:
        """Test counting when some component types are missing from dictionary."""
        tool1 = ParsedComponent(
            name="tool1",
            type=ComponentType.TOOL,
            file_path=sample_project / "tools" / "tool1.py",
            module_path="tools/tool1.py",
        )

        # Only include tools, missing resources and prompts
        components = {ComponentType.TOOL: [tool1]}

        counts = _get_component_counts(components)

        assert counts["tools"] == 1
        assert counts["resources"] == 0  # Should default to 0
        assert counts["prompts"] == 0  # Should default to 0
        assert counts["total"] == 1 