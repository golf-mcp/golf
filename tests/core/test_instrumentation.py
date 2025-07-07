"""Tests for OpenTelemetry instrumentation functionality."""

import asyncio
import os
from unittest.mock import Mock, patch

import pytest

from golf.telemetry.instrumentation import (
    get_tracer,
    init_telemetry,
    instrument_prompt,
    instrument_resource,
    instrument_tool,
)


class TestTelemetryInitialization:
    """Test OpenTelemetry initialization functionality."""

    def test_init_telemetry_with_otlp_http_endpoint(self, monkeypatch):
        """Test telemetry initialization with OTLP HTTP exporter."""
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp_http")
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"
        )
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-service")

        with patch("golf.telemetry.instrumentation.trace.set_tracer_provider"):
            provider = init_telemetry("test-service")
            assert provider is not None

    def test_init_telemetry_missing_endpoint_returns_none(self, monkeypatch):
        """Test that missing OTLP endpoint returns None."""
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp_http")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        provider = init_telemetry("test-service")
        assert provider is None

    def test_init_telemetry_with_console_exporter(self, monkeypatch):
        """Test telemetry initialization with console exporter."""
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")

        with patch("golf.telemetry.instrumentation.trace.set_tracer_provider"):
            provider = init_telemetry("test-service")
            assert provider is not None

    def test_init_telemetry_with_golf_platform_auto_config(self, monkeypatch):
        """Test auto-configuration for Golf platform."""
        monkeypatch.setenv("GOLF_API_KEY", "test-key-123")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        with patch("golf.telemetry.instrumentation.trace.set_tracer_provider"):
            provider = init_telemetry("test-service")
            assert provider is not None
            assert os.environ.get("OTEL_TRACES_EXPORTER") == "otlp_http"
            assert (
                os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
                == "https://golf-backend.golf-auth-1.authed-qukc4.ryvn.run/api/v1/otel"
            )

    def test_init_telemetry_with_headers(self, monkeypatch):
        """Test telemetry initialization with custom headers."""
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp_http")
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"
        )
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_HEADERS", "x-api-key=secret,x-custom=value"
        )

        with patch("golf.telemetry.instrumentation.trace.set_tracer_provider"):
            provider = init_telemetry("test-service")
            assert provider is not None


class TestToolInstrumentation:
    """Test tool function instrumentation."""

    @pytest.fixture
    def mock_tracer(self):
        """Mock tracer for testing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_span)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_context_manager

        with patch(
            "golf.telemetry.instrumentation.get_tracer", return_value=mock_tracer
        ):
            yield mock_tracer, mock_span

    def test_instrument_tool_with_telemetry_enabled(self, mock_tracer):
        """Test tool instrumentation when telemetry is enabled."""
        tracer, span = mock_tracer

        # Mock that telemetry is enabled
        with patch("golf.telemetry.instrumentation._provider", Mock()):

            def sample_tool(param1: str, param2: int = 42) -> dict:
                return {"result": f"processed {param1} with {param2}"}

            instrumented_tool = instrument_tool(sample_tool, "test-tool")
            result = instrumented_tool("test_input", param2=100)

            # Verify the original function was called and returned expected result
            assert result == {"result": "processed test_input with 100"}

            # Verify span was created with correct name
            tracer.start_as_current_span.assert_called_once_with(
                "mcp.tool.test-tool.execute"
            )

            # Verify span attributes were set
            span.set_attribute.assert_any_call("mcp.component.type", "tool")
            span.set_attribute.assert_any_call("mcp.tool.name", "test-tool")

    def test_instrument_tool_with_telemetry_disabled(self):
        """Test tool instrumentation when telemetry is disabled."""
        # Mock that telemetry is disabled
        with patch("golf.telemetry.instrumentation._provider", None):

            def sample_tool(param: str) -> str:
                return f"result_{param}"

            instrumented_tool = instrument_tool(sample_tool, "test-tool")
            result = instrumented_tool("input")

            # Should return original function result unchanged
            assert result == "result_input"
            assert instrumented_tool == sample_tool  # Should be the original function

    @pytest.mark.asyncio
    async def test_instrument_async_tool(self, mock_tracer):
        """Test instrumentation of async tool functions."""
        tracer, span = mock_tracer

        with patch("golf.telemetry.instrumentation._provider", Mock()):

            async def async_tool(param: str) -> str:
                await asyncio.sleep(0.01)  # Simulate async work
                return f"async_result_{param}"

            instrumented_tool = instrument_tool(async_tool, "async-tool")
            result = await instrumented_tool("test")

            assert result == "async_result_test"
            tracer.start_as_current_span.assert_called_once_with(
                "mcp.tool.async-tool.execute"
            )

    def test_instrument_tool_handles_exceptions(self, mock_tracer):
        """Test tool instrumentation handles exceptions properly."""
        tracer, span = mock_tracer

        with patch("golf.telemetry.instrumentation._provider", Mock()):

            def failing_tool(param: str) -> str:
                raise ValueError(f"Error processing {param}")

            instrumented_tool = instrument_tool(failing_tool, "failing-tool")

            with pytest.raises(ValueError, match="Error processing test"):
                instrumented_tool("test")

            # Verify exception was recorded
            assert span.record_exception.called
            span.set_status.assert_called_once()


class TestResourceInstrumentation:
    """Test resource function instrumentation."""

    @pytest.fixture
    def mock_tracer(self):
        """Mock tracer for testing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_span)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_context_manager

        with patch(
            "golf.telemetry.instrumentation.get_tracer", return_value=mock_tracer
        ):
            yield mock_tracer, mock_span

    def test_instrument_static_resource(self, mock_tracer):
        """Test instrumentation of static resource."""
        tracer, span = mock_tracer

        with patch("golf.telemetry.instrumentation._provider", Mock()):

            def static_resource() -> str:
                return "static content"

            instrumented_resource = instrument_resource(
                static_resource, "file://static.txt"
            )
            result = instrumented_resource()

            assert result == "static content"
            tracer.start_as_current_span.assert_called_once_with(
                "mcp.resource.static.read"
            )
            span.set_attribute.assert_any_call("mcp.component.type", "resource")
            span.set_attribute.assert_any_call("mcp.resource.uri", "file://static.txt")
            span.set_attribute.assert_any_call("mcp.resource.is_template", False)

    def test_instrument_template_resource(self, mock_tracer):
        """Test instrumentation of template resource."""
        tracer, span = mock_tracer

        with patch("golf.telemetry.instrumentation._provider", Mock()):

            def template_resource(file_id: str) -> str:
                return f"content for {file_id}"

            instrumented_resource = instrument_resource(
                template_resource, "file://files/{file_id}"
            )
            result = instrumented_resource("123")

            assert result == "content for 123"
            tracer.start_as_current_span.assert_called_once_with(
                "mcp.resource.template.read"
            )
            span.set_attribute.assert_any_call("mcp.resource.is_template", True)

    def test_instrument_resource_with_telemetry_disabled(self):
        """Test resource instrumentation when telemetry is disabled."""
        with patch("golf.telemetry.instrumentation._provider", None):

            def sample_resource() -> str:
                return "resource content"

            instrumented_resource = instrument_resource(
                sample_resource, "file://test.txt"
            )
            result = instrumented_resource()

            assert result == "resource content"
            assert instrumented_resource == sample_resource


class TestPromptInstrumentation:
    """Test prompt function instrumentation."""

    @pytest.fixture
    def mock_tracer(self):
        """Mock tracer for testing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_span)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_context_manager

        with patch(
            "golf.telemetry.instrumentation.get_tracer", return_value=mock_tracer
        ):
            yield mock_tracer, mock_span

    def test_instrument_prompt(self, mock_tracer):
        """Test prompt instrumentation."""
        tracer, span = mock_tracer

        with patch("golf.telemetry.instrumentation._provider", Mock()):

            def sample_prompt(query: str) -> list:
                return [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": query},
                ]

            instrumented_prompt = instrument_prompt(sample_prompt, "test-prompt")
            result = instrumented_prompt("Hello")

            assert len(result) == 2
            assert result[0]["role"] == "system"
            assert result[1]["content"] == "Hello"

            tracer.start_as_current_span.assert_called_once_with(
                "mcp.prompt.test-prompt.generate"
            )
            span.set_attribute.assert_any_call("mcp.component.type", "prompt")
            span.set_attribute.assert_any_call("mcp.prompt.name", "test-prompt")

    def test_instrument_prompt_with_telemetry_disabled(self):
        """Test prompt instrumentation when telemetry is disabled."""
        with patch("golf.telemetry.instrumentation._provider", None):

            def sample_prompt(query: str) -> str:
                return f"Generated prompt for: {query}"

            instrumented_prompt = instrument_prompt(sample_prompt, "test-prompt")
            result = instrumented_prompt("test")

            assert result == "Generated prompt for: test"
            assert instrumented_prompt == sample_prompt


class TestGetTracer:
    """Test tracer retrieval functionality."""

    def test_get_tracer_with_provider_enabled(self):
        """Test getting tracer when provider is enabled."""
        with patch("golf.telemetry.instrumentation._provider", Mock()):
            with patch(
                "golf.telemetry.instrumentation.trace.get_tracer"
            ) as mock_get_tracer:
                tracer = get_tracer()
                mock_get_tracer.assert_called_once_with("golf.mcp.components", "1.0.0")

    def test_get_tracer_with_provider_disabled(self):
        """Test getting tracer when provider is disabled."""
        with patch("golf.telemetry.instrumentation._provider", None):
            with patch(
                "golf.telemetry.instrumentation.trace.get_tracer"
            ) as mock_get_tracer:
                tracer = get_tracer()
                mock_get_tracer.assert_called_once_with(
                    "golf.mcp.components.noop", "1.0.0"
                )


class TestIntegrationScenarios:
    """Test end-to-end integration scenarios."""

    def test_full_telemetry_workflow(self, monkeypatch):
        """Test complete telemetry workflow from init to instrumentation."""
        # Set up environment for telemetry
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-integration")

        # Initialize telemetry
        with patch("golf.telemetry.instrumentation.trace.set_tracer_provider"):
            provider = init_telemetry("test-service")
            assert provider is not None

        # Test tool instrumentation in the context
        with patch("golf.telemetry.instrumentation._provider", provider):

            def test_tool(name: str) -> str:
                return f"Hello {name}"

            instrumented_tool = instrument_tool(test_tool, "greeting-tool")
            result = instrumented_tool("World")
            assert result == "Hello World"

    def test_golf_platform_integration_workflow(self, monkeypatch):
        """Test Golf platform integration scenario."""
        # Simulate Golf platform environment
        monkeypatch.setenv("GOLF_API_KEY", "golf_test_key_123")
        monkeypatch.setenv("GOLF_SERVER_ID", "server_abc")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        with patch("golf.telemetry.instrumentation.trace.set_tracer_provider"):
            provider = init_telemetry("golf-server")
            assert provider is not None

        # Verify auto-configuration
        assert os.environ.get("OTEL_TRACES_EXPORTER") == "otlp_http"
        assert (
            os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            == "https://golf-backend.golf-auth-1.authed-qukc4.ryvn.run/api/v1/otel"
        )
        assert "X-Golf-Key=golf_test_key_123" in os.environ.get(
            "OTEL_EXPORTER_OTLP_HEADERS", ""
        )

    def test_mixed_component_instrumentation(self):
        """Test instrumenting multiple component types together."""
        with patch("golf.telemetry.instrumentation._provider", Mock()):
            with patch("golf.telemetry.instrumentation.get_tracer") as mock_get_tracer:
                mock_tracer = Mock()
                mock_get_tracer.return_value = mock_tracer

                # Instrument different component types
                def tool_func() -> str:
                    return "tool"

                def resource_func() -> str:
                    return "resource"

                def prompt_func() -> str:
                    return "prompt"

                instrumented_tool = instrument_tool(tool_func, "test-tool")
                instrumented_resource = instrument_resource(
                    resource_func, "test://resource"
                )
                instrumented_prompt = instrument_prompt(prompt_func, "test-prompt")

                # All should use the same tracer instance
                assert mock_get_tracer.call_count == 3
