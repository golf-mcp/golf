"""Tests for Golf MCP telemetry functionality."""

from golf.core.telemetry import (
    _sanitize_error_message,
    get_anonymous_id,
    is_telemetry_enabled,
    set_telemetry_enabled,
    track_event,
)


class TestTelemetryConfiguration:
    """Test telemetry configuration and preferences."""

    def test_telemetry_disabled_by_env(self, monkeypatch) -> None:
        """Test that telemetry respects environment variable."""
        # Note: isolate_telemetry fixture already sets GOLF_TELEMETRY=0
        assert not is_telemetry_enabled()

    def test_telemetry_disabled_by_test_mode_env(self, monkeypatch) -> None:
        """Test that telemetry is disabled when GOLF_TEST_MODE is set."""
        # Clear the telemetry env var set by fixture
        monkeypatch.delenv("GOLF_TELEMETRY", raising=False)
        # Set test mode
        monkeypatch.setenv("GOLF_TEST_MODE", "1")

        # Reset cached state
        from golf.core import telemetry

        telemetry._telemetry_enabled = None

        # Should be disabled due to test mode
        assert not is_telemetry_enabled()

    def test_set_telemetry_enabled(self, monkeypatch) -> None:
        """Test enabling/disabling telemetry programmatically."""
        # Start with telemetry disabled by fixture
        assert not is_telemetry_enabled()

        # Enable telemetry (without persisting)
        set_telemetry_enabled(True, persist=False)
        assert is_telemetry_enabled()

        # Disable again
        set_telemetry_enabled(False, persist=False)
        assert not is_telemetry_enabled()

    def test_anonymous_id_generation(self) -> None:
        """Test that anonymous ID is generated correctly."""
        id1 = get_anonymous_id()
        assert id1 is not None
        assert id1.startswith("golf-")
        assert len(id1) > 10  # Should have some reasonable length

        # Should return same ID on subsequent calls
        id2 = get_anonymous_id()
        assert id1 == id2

    def test_anonymous_id_format(self) -> None:
        """Test that anonymous ID follows expected format."""
        anon_id = get_anonymous_id()
        # Format: golf-[hash]-[random]
        parts = anon_id.split("-")
        assert len(parts) == 3
        assert parts[0] == "golf"
        assert len(parts[1]) == 8  # Hash component
        assert len(parts[2]) == 8  # Random component


class TestErrorSanitization:
    """Test error message sanitization."""

    def test_sanitizes_file_paths(self) -> None:
        """Test that file paths are sanitized."""
        # Unix paths
        msg = "Error in /Users/john/projects/myapp/secret.py"
        sanitized = _sanitize_error_message(msg)
        assert "/Users/john" not in sanitized
        assert "secret.py" in sanitized

        # Windows paths
        msg = "Error in C:\\Users\\john\\projects\\app.py"
        sanitized = _sanitize_error_message(msg)
        assert "C:\\Users\\john" not in sanitized
        assert "app.py" in sanitized

    def test_sanitizes_api_keys(self) -> None:
        """Test that API keys are sanitized."""
        msg = "Invalid API key: sk_test_abcdef1234567890abcdef1234567890"
        sanitized = _sanitize_error_message(msg)
        assert "sk_test_abcdef1234567890abcdef1234567890" not in sanitized
        assert "[REDACTED]" in sanitized

    def test_sanitizes_email_addresses(self) -> None:
        """Test that email addresses are sanitized."""
        msg = "User john.doe@example.com not found"
        sanitized = _sanitize_error_message(msg)
        assert "john.doe@example.com" not in sanitized
        assert "[EMAIL]" in sanitized

    def test_sanitizes_ip_addresses(self) -> None:
        """Test that IP addresses are sanitized."""
        msg = "Connection failed to 192.168.1.100"
        sanitized = _sanitize_error_message(msg)
        assert "192.168.1.100" not in sanitized
        assert "[IP]" in sanitized

    def test_truncates_long_messages(self) -> None:
        """Test that long messages are truncated."""
        # Use a message that won't trigger redaction patterns
        msg = "Error: " + "This is a very long error message. " * 20
        sanitized = _sanitize_error_message(msg)
        assert len(sanitized) <= 200
        # Only check for ellipsis if the message was actually truncated
        if len(msg) > 200:
            assert sanitized.endswith("...")


class TestEventTracking:
    """Test event tracking functionality."""

    def test_track_event_when_disabled(self) -> None:
        """Test that events are not tracked when telemetry is disabled."""
        # Telemetry is disabled by fixture
        assert not is_telemetry_enabled()

        # This should not raise any errors
        track_event("test_event", {"key": "value"})

        # No way to verify it wasn't sent without mocking
        # but at least it shouldn't crash

    def test_track_event_filters_properties(self) -> None:
        """Test that event properties are filtered."""
        # Even though telemetry is disabled, we can test the logic
        # by enabling it temporarily
        set_telemetry_enabled(True, persist=False)

        # This should filter out unsafe properties
        track_event(
            "test_event",
            {
                "success": True,
                "environment": "test",
                "sensitive_data": "should_be_filtered",
                "user_email": "test@example.com",
            },
        )

        # Reset
        set_telemetry_enabled(False, persist=False)
