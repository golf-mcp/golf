"""Tests for golf.telemetry.errors module."""

from unittest.mock import MagicMock, patch

from golf.telemetry.errors import record_http_error, record_runtime_error


class TestRecordRuntimeError:
    """Tests for record_runtime_error function."""

    def test_records_exception_to_span(self):
        """Test that exception is recorded to the current span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            error = ValueError("test error")
            record_runtime_error(error, "test_operation")

        mock_span.record_exception.assert_called_once()
        mock_span.set_status.assert_called_once()
        mock_span.add_event.assert_called_once()

    def test_does_nothing_when_no_span(self):
        """Test that function is safe when no span exists."""
        with patch("golf.telemetry.errors.trace.get_current_span", return_value=None):
            # Should not raise
            record_runtime_error(ValueError("test"), "test_operation")

    def test_does_nothing_when_span_not_recording(self):
        """Test that function is safe when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_runtime_error(ValueError("test"), "test_operation")

        mock_span.record_exception.assert_not_called()

    def test_includes_custom_attributes(self):
        """Test that custom attributes are included."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_runtime_error(
                ValueError("test"),
                "test_operation",
                component="golf-mcp-enterprise",
                attributes={"tenant_id": "123", "feature": "auth"},
            )

        # Verify attributes were passed
        call_kwargs = mock_span.record_exception.call_args.kwargs
        assert "error.tenant_id" in call_kwargs["attributes"]
        assert "error.feature" in call_kwargs["attributes"]

    def test_sets_error_status_with_context(self):
        """Test that span status includes operation context."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_runtime_error(ValueError("bad value"), "startup_script")

        status_call = mock_span.set_status.call_args[0][0]
        assert "startup_script" in status_call.description
        assert "ValueError" in status_call.description

    def test_error_event_includes_operation_and_type(self):
        """Test that the error event includes operation and error type."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_runtime_error(RuntimeError("test failure"), "health_check")

        # Check add_event was called with correct event name and attributes
        event_call = mock_span.add_event.call_args
        event_name = event_call[0][0]
        event_attrs = event_call[0][1]

        assert event_name == "golf.runtime_error"
        assert event_attrs["operation"] == "health_check"
        assert event_attrs["error.type"] == "RuntimeError"
        assert event_attrs["error.message"] == "test failure"

    def test_custom_component_name(self):
        """Test that custom component name is used in event and status."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_runtime_error(
                ValueError("test"),
                "auth_validation",
                component="golf-mcp-enterprise",
            )

        # Check event name includes component
        event_name = mock_span.add_event.call_args[0][0]
        assert event_name == "golf-mcp-enterprise.runtime_error"

        # Check status includes component
        status_call = mock_span.set_status.call_args[0][0]
        assert "golf-mcp-enterprise.auth_validation" in status_call.description

    def test_exception_attributes_include_source_and_operation(self):
        """Test that exception recording includes error.source and error.operation."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_runtime_error(ValueError("test"), "startup_script", component="golf")

        call_kwargs = mock_span.record_exception.call_args.kwargs
        assert call_kwargs["attributes"]["error.source"] == "golf"
        assert call_kwargs["attributes"]["error.operation"] == "startup_script"
        assert call_kwargs["escaped"] is True


class TestRecordHttpError:
    """Tests for record_http_error function."""

    def test_records_4xx_error_to_span(self):
        """Test that 4xx errors are recorded to the current span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(401, "POST", "/oauth/token", "oauth_token")

        mock_span.set_status.assert_called_once()
        mock_span.set_attribute.assert_called()
        mock_span.add_event.assert_called_once()

    def test_records_5xx_error_to_span(self):
        """Test that 5xx errors are recorded to the current span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(503, "GET", "/health", "health_check")

        mock_span.set_status.assert_called_once()
        mock_span.add_event.assert_called_once()

    def test_does_nothing_for_success_codes(self):
        """Test that success codes (< 400) are not recorded as errors."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(200, "GET", "/health", "health_check")
            record_http_error(201, "POST", "/resource", "create_resource")
            record_http_error(302, "GET", "/redirect", "redirect")

        mock_span.set_status.assert_not_called()
        mock_span.add_event.assert_not_called()

    def test_does_nothing_when_no_span(self):
        """Test that function is safe when no span exists."""
        with patch("golf.telemetry.errors.trace.get_current_span", return_value=None):
            # Should not raise
            record_http_error(500, "GET", "/error", "test")

    def test_does_nothing_when_span_not_recording(self):
        """Test that function is safe when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(500, "GET", "/error", "test")

        mock_span.set_status.assert_not_called()

    def test_categorizes_client_errors(self):
        """Test that 4xx errors are categorized as client_error."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(401, "POST", "/oauth/token", "oauth_token")

        event_attrs = mock_span.add_event.call_args[0][1]
        assert event_attrs["error.category"] == "client_error"

    def test_categorizes_server_errors(self):
        """Test that 5xx errors are categorized as server_error."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(500, "GET", "/api", "api_request")

        event_attrs = mock_span.add_event.call_args[0][1]
        assert event_attrs["error.category"] == "server_error"

    def test_includes_error_message(self):
        """Test that error message is included when provided."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(
                401, "POST", "/oauth/token", "oauth_token",
                error_message="Invalid credentials"
            )

        event_attrs = mock_span.add_event.call_args[0][1]
        assert event_attrs["error.message"] == "Invalid credentials"

        status_call = mock_span.set_status.call_args[0][0]
        assert "Invalid credentials" in status_call.description

    def test_includes_custom_attributes(self):
        """Test that custom attributes are included."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(
                403, "GET", "/api/resource", "api_request",
                attributes={"tenant_id": "123", "user_id": "456"}
            )

        event_attrs = mock_span.add_event.call_args[0][1]
        assert event_attrs["error.tenant_id"] == "123"
        assert event_attrs["error.user_id"] == "456"

    def test_custom_component_name(self):
        """Test that custom component name is used in event and status."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(
                500, "GET", "/api", "api_request",
                component="golf-mcp-enterprise"
            )

        event_name = mock_span.add_event.call_args[0][0]
        assert event_name == "golf-mcp-enterprise.http_error"

        status_call = mock_span.set_status.call_args[0][0]
        assert "golf-mcp-enterprise.api_request" in status_call.description

    def test_event_includes_all_http_details(self):
        """Test that event includes all HTTP details."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(404, "DELETE", "/api/users/123", "delete_user")

        event_attrs = mock_span.add_event.call_args[0][1]
        assert event_attrs["http.status_code"] == 404
        assert event_attrs["http.method"] == "DELETE"
        assert event_attrs["http.path"] == "/api/users/123"
        assert event_attrs["operation"] == "delete_user"
        assert event_attrs["error.source"] == "golf"

    def test_sets_http_status_code_attribute(self):
        """Test that HTTP status code is set as span attribute."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("golf.telemetry.errors.trace.get_current_span", return_value=mock_span):
            record_http_error(503, "GET", "/health", "health_check")

        mock_span.set_attribute.assert_called_with("http.status_code", 503)
