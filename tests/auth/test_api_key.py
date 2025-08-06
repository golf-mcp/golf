"""Tests for API key authentication."""

from golf.auth.api_key import (
    configure_api_key,
    get_api_key_config,
    is_api_key_configured,
)


class TestAPIKeyConfiguration:
    """Test API key configuration functionality."""

    def test_configure_api_key_basic(self) -> None:
        """Test basic API key configuration."""
        # Reset any existing configuration
        global _api_key_config
        from golf.auth import api_key

        api_key._api_key_config = None

        assert not is_api_key_configured()

        # Configure API key with defaults
        configure_api_key()

        assert is_api_key_configured()
        config = get_api_key_config()
        assert config is not None
        assert config.header_name == "X-API-Key"
        assert config.header_prefix == ""
        assert config.required is True

    def test_configure_api_key_custom(self) -> None:
        """Test API key configuration with custom settings."""
        # Reset configuration
        from golf.auth import api_key

        api_key._api_key_config = None

        # Configure with custom settings
        configure_api_key(header_name="Authorization", header_prefix="Bearer ", required=False)

        assert is_api_key_configured()
        config = get_api_key_config()
        assert config is not None
        assert config.header_name == "Authorization"
        assert config.header_prefix == "Bearer "
        assert config.required is False

    def test_clear_api_key_configuration(self) -> None:
        """Test clearing API key configuration."""
        # Configure first
        configure_api_key()
        assert is_api_key_configured()

        # Clear configuration by setting to None
        from golf.auth import api_key

        api_key._api_key_config = None

        assert not is_api_key_configured()
        assert get_api_key_config() is None

    def test_api_key_persistence(self) -> None:
        """Test that API key configuration persists across calls."""
        # Reset configuration
        from golf.auth import api_key

        api_key._api_key_config = None

        # Configure API key
        configure_api_key(header_name="Custom-Key")

        # Check it's still there
        assert is_api_key_configured()
        config1 = get_api_key_config()

        # Get config again
        config2 = get_api_key_config()

        assert config1 == config2
        assert config2.header_name == "Custom-Key"
