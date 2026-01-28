"""Tests for authentication provider creation and configuration."""

import os
import pytest
from unittest.mock import Mock, patch
from pydantic import ValidationError

from golf.auth.providers import JWTAuthConfig, OAuthServerConfig, RemoteAuthConfig, OAuthProxyConfig, StaticTokenConfig
from golf.auth.factory import (
    _create_jwt_provider,
    _create_oauth_server_provider,
    _create_remote_provider,
    _create_oauth_proxy_provider,
)


class TestJWTProviderCreation:
    """Test JWT verifier creation from configurations."""

    def test_jwt_creation_with_direct_values(self) -> None:
        """Test JWT verifier creation with direct configuration values."""
        config = JWTAuthConfig(
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            issuer="https://auth.example.com",
            audience="https://api.example.com",
            required_scopes=["read", "write"],
        )

        # Mock FastMCP's JWTVerifier (imported within the function)
        with patch("fastmcp.server.auth.JWTVerifier") as mock_jwt_verifier:
            mock_instance = Mock()
            mock_jwt_verifier.return_value = mock_instance

            provider = _create_jwt_provider(config)

            # Verify JWTVerifier was called with correct parameters
            mock_jwt_verifier.assert_called_once_with(
                public_key=None,
                jwks_uri="https://auth.example.com/.well-known/jwks.json",
                issuer="https://auth.example.com",
                audience="https://api.example.com",
                algorithm="RS256",
                required_scopes=["read", "write"],
            )

            assert provider == mock_instance

    def test_jwt_creation_with_public_key(self) -> None:
        """Test JWT verifier creation with public key instead of JWKS URI."""
        public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEF..."
        config = JWTAuthConfig(
            public_key=public_key, issuer="https://auth.example.com", audience="https://api.example.com"
        )

        with patch("fastmcp.server.auth.JWTVerifier") as mock_jwt_verifier:
            mock_instance = Mock()
            mock_jwt_verifier.return_value = mock_instance

            provider = _create_jwt_provider(config)

            mock_jwt_verifier.assert_called_once_with(
                public_key=public_key,
                jwks_uri=None,
                issuer="https://auth.example.com",
                audience="https://api.example.com",
                algorithm="RS256",
                required_scopes=[],
            )

    def test_jwt_creation_with_env_variables(self) -> None:
        """Test JWT verifier creation with environment variables."""
        config = JWTAuthConfig(
            jwks_uri="https://default.example.com/.well-known/jwks.json",
            issuer="https://default.example.com",
            audience="https://default-api.example.com",
            jwks_uri_env_var="JWKS_URI",
            issuer_env_var="JWT_ISSUER",
            audience_env_var="JWT_AUDIENCE",
        )

        env_vars = {
            "JWKS_URI": "https://env.example.com/.well-known/jwks.json",
            "JWT_ISSUER": "https://env.example.com",
            "JWT_AUDIENCE": "https://env-api.example.com,https://env-api2.example.com",
        }

        with patch.dict(os.environ, env_vars), patch("fastmcp.server.auth.JWTVerifier") as mock_jwt_verifier:
            mock_instance = Mock()
            mock_jwt_verifier.return_value = mock_instance

            provider = _create_jwt_provider(config)

            # Environment variables should override config values
            mock_jwt_verifier.assert_called_once_with(
                public_key=None,
                jwks_uri="https://env.example.com/.well-known/jwks.json",
                issuer="https://env.example.com",
                audience=["https://env-api.example.com", "https://env-api2.example.com"],  # Comma-separated list
                algorithm="RS256",
                required_scopes=[],
            )

    def test_jwt_creation_env_single_audience(self) -> None:
        """Test JWT verifier with single audience from environment variable."""
        config = JWTAuthConfig(
            jwks_uri="https://auth.example.com/.well-known/jwks.json", audience_env_var="JWT_AUDIENCE"
        )

        with (
            patch.dict(os.environ, {"JWT_AUDIENCE": "https://single-api.example.com"}),
            patch("fastmcp.server.auth.JWTVerifier") as mock_jwt_verifier,
        ):
            mock_instance = Mock()
            mock_jwt_verifier.return_value = mock_instance

            provider = _create_jwt_provider(config)

            # Single audience should remain as string
            mock_jwt_verifier.assert_called_once_with(
                public_key=None,
                jwks_uri="https://auth.example.com/.well-known/jwks.json",
                issuer=None,
                audience="https://single-api.example.com",
                algorithm="RS256",
                required_scopes=[],
            )

    def test_jwt_creation_missing_key_source(self) -> None:
        """Test JWT verifier creation fails without key source."""
        # This test validates that the Pydantic model itself catches the error
        with pytest.raises(
            ValidationError,
            match="Either public_key, jwks_uri, or their environment variable equivalents must be provided",
        ):
            JWTAuthConfig(issuer="https://auth.example.com", audience="https://api.example.com")

    def test_jwt_creation_both_key_sources(self) -> None:
        """Test JWT verifier creation fails with both key sources."""
        # This test validates that the Pydantic model itself catches the error
        with pytest.raises(ValidationError, match="Provide either public_key or jwks_uri"):
            JWTAuthConfig(
                public_key="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEF...",
                jwks_uri="https://auth.example.com/.well-known/jwks.json",
            )

    def test_jwt_creation_fastmcp_import_error(self) -> None:
        """Test JWT verifier creation handles FastMCP import errors."""
        config = JWTAuthConfig(jwks_uri="https://auth.example.com/.well-known/jwks.json")

        with patch("fastmcp.server.auth.JWTVerifier", side_effect=ImportError("FastMCP not available")):
            with pytest.raises(ImportError, match="FastMCP not available"):
                _create_jwt_provider(config)


class TestRemoteAuthCreation:
    """Test remote auth provider creation with JWT verifier underneath."""

    def test_remote_auth_creation_basic(self) -> None:
        """Test basic remote auth provider creation."""
        jwt_config = JWTAuthConfig(jwks_uri="https://auth.example.com/.well-known/jwks.json")
        config = RemoteAuthConfig(
            authorization_servers=["https://auth1.example.com", "https://auth2.example.com"],
            resource_server_url="https://api.example.com",
            token_verifier_config=jwt_config,
        )

        with (
            patch("fastmcp.server.auth.RemoteAuthProvider") as mock_remote_provider,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth,
        ):
            mock_token_verifier = Mock()
            mock_token_verifier.verify_token = Mock()  # Add verify_token method for duck typing
            mock_create_auth.return_value = mock_token_verifier

            mock_remote_instance = Mock()
            mock_remote_provider.return_value = mock_remote_instance

            provider = _create_remote_provider(config)

            # Verify token verifier was created from JWT config
            mock_create_auth.assert_called_once_with(jwt_config)

            # Verify RemoteAuthProvider was created with correct parameters
            mock_remote_provider.assert_called_once_with(
                token_verifier=mock_token_verifier,
                authorization_servers=["https://auth1.example.com", "https://auth2.example.com"],
                resource_server_url="https://api.example.com",
            )

            assert provider == mock_remote_instance

    def test_remote_auth_with_env_variables(self) -> None:
        """Test remote auth creation with environment variable resolution."""
        jwt_config = JWTAuthConfig(jwks_uri="https://auth.example.com/.well-known/jwks.json")
        config = RemoteAuthConfig(
            authorization_servers=["https://default1.com", "https://default2.com"],
            resource_server_url="https://default-api.com",
            token_verifier_config=jwt_config,
            authorization_servers_env_var="AUTH_SERVERS",
            resource_server_url_env_var="RESOURCE_URL",
        )

        env_vars = {
            "AUTH_SERVERS": "https://env-auth1.com,https://env-auth2.com,https://env-auth3.com",
            "RESOURCE_URL": "https://env-api.com",
        }

        with (
            patch.dict(os.environ, env_vars),
            patch("fastmcp.server.auth.RemoteAuthProvider") as mock_remote_provider,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth,
        ):
            mock_token_verifier = Mock()
            mock_token_verifier.verify_token = Mock()
            mock_create_auth.return_value = mock_token_verifier

            mock_remote_instance = Mock()
            mock_remote_provider.return_value = mock_remote_instance

            provider = _create_remote_provider(config)

            # Environment variables should override config values
            mock_remote_provider.assert_called_once_with(
                token_verifier=mock_token_verifier,
                authorization_servers=["https://env-auth1.com", "https://env-auth2.com", "https://env-auth3.com"],
                resource_server_url="https://env-api.com",
            )

    def test_remote_auth_invalid_token_verifier(self) -> None:
        """Test remote auth creation fails with invalid token verifier."""
        jwt_config = JWTAuthConfig(jwks_uri="https://auth.example.com/.well-known/jwks.json")
        config = RemoteAuthConfig(
            authorization_servers=["https://auth1.example.com"],
            resource_server_url="https://api.example.com",
            token_verifier_config=jwt_config,
        )

        with (
            patch("fastmcp.server.auth.RemoteAuthProvider") as mock_remote_provider,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth,
        ):
            # Mock token verifier without verify_token method
            mock_invalid_verifier = Mock(spec=[])  # No verify_token method
            mock_create_auth.return_value = mock_invalid_verifier

            with pytest.raises(ValueError, match="Remote auth provider requires a TokenVerifier"):
                _create_remote_provider(config)

    def test_remote_auth_fastmcp_import_error(self) -> None:
        """Test remote auth creation handles FastMCP import errors."""
        jwt_config = JWTAuthConfig(jwks_uri="https://auth.example.com/.well-known/jwks.json")
        config = RemoteAuthConfig(
            authorization_servers=["https://auth1.example.com"],
            resource_server_url="https://api.example.com",
            token_verifier_config=jwt_config,
        )

        with patch("fastmcp.server.auth.RemoteAuthProvider", side_effect=ImportError("FastMCP not available")):
            with pytest.raises(ImportError, match="FastMCP not available"):
                _create_remote_provider(config)

    def test_get_routes_presence_passthrough(self) -> None:
        """Test that get_routes method is available on created remote auth provider."""
        jwt_config = JWTAuthConfig(jwks_uri="https://auth.example.com/.well-known/jwks.json")
        config = RemoteAuthConfig(
            authorization_servers=["https://auth1.example.com"],
            resource_server_url="https://api.example.com",
            token_verifier_config=jwt_config,
        )

        with (
            patch("fastmcp.server.auth.RemoteAuthProvider") as mock_remote_provider,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth,
        ):
            mock_token_verifier = Mock()
            mock_token_verifier.verify_token = Mock()
            mock_create_auth.return_value = mock_token_verifier

            # Mock remote provider with get_routes method
            mock_remote_instance = Mock()
            mock_routes = [Mock(), Mock()]  # Mock OAuth metadata routes
            mock_remote_instance.get_routes.return_value = mock_routes
            mock_remote_provider.return_value = mock_remote_instance

            provider = _create_remote_provider(config)

            # Verify get_routes method exists and returns routes
            assert hasattr(provider, "get_routes")
            routes = provider.get_routes()
            assert routes == mock_routes
            mock_remote_instance.get_routes.assert_called_once()


class TestOAuthServerCreation:
    """Test OAuth server provider creation with version guards."""

    def test_oauth_server_creation_basic(self) -> None:
        """Test basic OAuth server provider creation when FastMCP is available."""
        config = OAuthServerConfig(
            base_url="https://auth.example.com",
            issuer_url="https://auth.example.com",
            valid_scopes=["read", "write"],
            default_scopes=["read"],
        )

        with (
            patch("fastmcp.server.auth.OAuthProvider") as mock_oauth_provider,
            patch("mcp.server.auth.settings.RevocationOptions") as mock_revocation_options,
        ):
            mock_oauth_instance = Mock()
            mock_oauth_provider.return_value = mock_oauth_instance

            mock_revocation_instance = Mock()
            mock_revocation_options.return_value = mock_revocation_instance

            provider = _create_oauth_server_provider(config)

            # Verify OAuthProvider was created with correct parameters
            call_args = mock_oauth_provider.call_args[1]  # Get keyword arguments
            assert call_args["base_url"] == "https://auth.example.com"
            assert call_args["issuer_url"] == "https://auth.example.com"
            assert call_args["service_documentation_url"] is None
            assert call_args["client_registration_options"] is None  # Disabled for security
            assert call_args["required_scopes"] == []
            # RevocationOptions should be created (don't check exact instance)
            # Note: The real RevocationOptions is used, not the mock

            assert provider == mock_oauth_instance

    def test_oauth_server_with_env_variables(self) -> None:
        """Test OAuth server creation with environment variable resolution."""
        config = OAuthServerConfig(base_url="https://default.example.com", base_url_env_var="OAUTH_BASE_URL")

        env_vars = {"OAUTH_BASE_URL": "https://env.example.com"}

        with (
            patch.dict(os.environ, env_vars),
            patch("fastmcp.server.auth.OAuthProvider") as mock_oauth_provider,
            patch("mcp.server.auth.settings.RevocationOptions"),
        ):
            mock_oauth_instance = Mock()
            mock_oauth_provider.return_value = mock_oauth_instance

            provider = _create_oauth_server_provider(config)

            # Environment variable should override config value
            call_args = mock_oauth_provider.call_args[1]  # Get keyword arguments
            assert call_args["base_url"] == "https://env.example.com"

    def test_oauth_server_env_validation(self) -> None:
        """Test OAuth server creation validates environment variables."""
        config = OAuthServerConfig(base_url="https://default.example.com", base_url_env_var="OAUTH_BASE_URL")

        # Invalid URL in environment variable
        env_vars = {"OAUTH_BASE_URL": "not-a-valid-url"}

        with patch.dict(os.environ, env_vars):
            with pytest.raises(ValueError, match="Invalid base URL from environment variable"):
                _create_oauth_server_provider(config)

    def test_oauth_server_production_localhost_validation(self) -> None:
        """Test OAuth server blocks localhost URLs in production."""
        config = OAuthServerConfig(base_url="https://localhost:8080")

        with patch.dict(os.environ, {"GOLF_ENV": "production"}):
            with pytest.raises(ValueError, match="Cannot use localhost/loopback addresses in production"):
                _create_oauth_server_provider(config)

    def test_oauth_server_fastmcp_version_guard(self) -> None:
        """Test OAuth server creation handles FastMCP version compatibility."""
        config = OAuthServerConfig(base_url="https://auth.example.com")

        # Simulate older FastMCP version without OAuthProvider
        with patch("fastmcp.server.auth.OAuthProvider", side_effect=ImportError("OAuthProvider not available")):
            with pytest.raises(ImportError, match="OAuthProvider not available"):
                _create_oauth_server_provider(config)

    def test_oauth_server_without_token_revocation(self) -> None:
        """Test OAuth server creation with token revocation disabled."""
        config = OAuthServerConfig(base_url="https://auth.example.com", allow_token_revocation=False)

        with (
            patch("fastmcp.server.auth.OAuthProvider") as mock_oauth_provider,
            patch("mcp.server.auth.settings.RevocationOptions") as mock_revocation_options,
        ):
            mock_oauth_instance = Mock()
            mock_oauth_provider.return_value = mock_oauth_instance

            provider = _create_oauth_server_provider(config)

            # Verify revocation options were not created
            mock_revocation_options.assert_not_called()

            # Verify OAuthProvider was called with None revocation options
            call_args = mock_oauth_provider.call_args[1]
            assert call_args["revocation_options"] is None


class TestOAuthProxyDynamicRedirectUris:
    """Test OAuth proxy configuration with dynamic redirect URI validation."""

    def _create_base_config(self, **kwargs) -> OAuthProxyConfig:
        """Create a base OAuth proxy config with required fields for testing."""
        token_verifier = StaticTokenConfig(tokens={"test-token": {"client_id": "test", "scopes": ["read"]}})
        defaults = {
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "base_url": "https://proxy.example.com",
            "token_verifier_config": token_verifier,
        }
        defaults.update(kwargs)
        return OAuthProxyConfig(**defaults)

    def test_config_with_static_redirect_patterns(self) -> None:
        """Test config creation with static redirect patterns list."""
        config = self._create_base_config(
            allowed_redirect_patterns=["https://app1.example.com/*", "https://app2.example.com/*"],
            allowed_redirect_schemes=["myapp", "custom"],
        )

        assert config.allowed_redirect_patterns == ["https://app1.example.com/*", "https://app2.example.com/*"]
        assert config.allowed_redirect_schemes == ["myapp", "custom"]
        assert config.allowed_redirect_patterns_func is None
        assert config.allowed_redirect_schemes_func is None
        assert config.redirect_uri_validator is None

    def test_config_with_callable_patterns_func(self) -> None:
        """Test config creation with callable that returns patterns dynamically."""
        call_count = 0

        def get_patterns() -> list[str]:
            nonlocal call_count
            call_count += 1
            # Simulate feature flag check
            return ["https://dynamic-app.example.com/*"]

        config = self._create_base_config(
            allowed_redirect_patterns_func=get_patterns,
        )

        assert config.allowed_redirect_patterns_func is not None
        assert callable(config.allowed_redirect_patterns_func)

        # Call the function to verify it works
        patterns = config.allowed_redirect_patterns_func()
        assert patterns == ["https://dynamic-app.example.com/*"]
        assert call_count == 1

        # Call again to verify it can be called multiple times
        patterns = config.allowed_redirect_patterns_func()
        assert call_count == 2

    def test_config_with_callable_schemes_func(self) -> None:
        """Test config creation with callable that returns schemes dynamically."""

        def get_schemes() -> list[str]:
            # Could check feature flags, database, etc.
            return ["myapp", "vscode"]

        config = self._create_base_config(
            allowed_redirect_schemes_func=get_schemes,
        )

        assert config.allowed_redirect_schemes_func is not None
        schemes = config.allowed_redirect_schemes_func()
        assert schemes == ["myapp", "vscode"]

    def test_config_with_redirect_uri_validator(self) -> None:
        """Test config creation with custom redirect URI validator function."""
        allowed_uris = {"https://allowed.example.com/callback", "https://also-allowed.example.com/oauth"}

        def validate_uri(uri: str) -> bool:
            return uri in allowed_uris

        config = self._create_base_config(
            redirect_uri_validator=validate_uri,
        )

        assert config.redirect_uri_validator is not None
        assert config.redirect_uri_validator("https://allowed.example.com/callback") is True
        assert config.redirect_uri_validator("https://not-allowed.example.com/callback") is False

    def test_config_with_mixed_static_and_dynamic(self) -> None:
        """Test config with both static patterns and dynamic validator."""

        def dynamic_validator(uri: str) -> bool:
            return uri.startswith("https://dynamic")

        config = self._create_base_config(
            allowed_redirect_patterns=["https://static.example.com/*"],
            allowed_redirect_patterns_func=lambda: ["https://func.example.com/*"],
            redirect_uri_validator=dynamic_validator,
        )

        # All configurations should be set
        assert config.allowed_redirect_patterns == ["https://static.example.com/*"]
        assert config.allowed_redirect_patterns_func is not None
        assert config.redirect_uri_validator is not None

    def test_factory_passes_callable_to_enterprise(self) -> None:
        """Test that factory function passes callable parameters to enterprise package."""
        patterns_func = lambda: ["https://dynamic.example.com/*"]  # noqa: E731
        schemes_func = lambda: ["myscheme"]  # noqa: E731
        validator = lambda uri: uri.startswith("https://")  # noqa: E731

        config = self._create_base_config(
            allowed_redirect_patterns=["https://static.example.com/*"],
            allowed_redirect_schemes=["http", "https"],
            allowed_redirect_patterns_func=patterns_func,
            allowed_redirect_schemes_func=schemes_func,
            redirect_uri_validator=validator,
        )

        # Mock the golf_enterprise module import
        mock_enterprise = Mock()
        mock_provider_instance = Mock()
        mock_enterprise.create_oauth_proxy_provider.return_value = mock_provider_instance

        import sys

        with patch.dict(sys.modules, {"golf_enterprise": mock_enterprise}):
            provider = _create_oauth_proxy_provider(config)

            # Verify the enterprise function was called
            mock_enterprise.create_oauth_proxy_provider.assert_called_once()

            # Get the resolved config passed to the enterprise function
            resolved_config = mock_enterprise.create_oauth_proxy_provider.call_args[0][0]

            # Verify static patterns are passed
            assert resolved_config.allowed_redirect_patterns == ["https://static.example.com/*"]
            assert resolved_config.allowed_redirect_schemes == ["http", "https"]

            # Verify callable functions are passed through
            assert resolved_config.allowed_redirect_patterns_func is patterns_func
            assert resolved_config.allowed_redirect_schemes_func is schemes_func
            assert resolved_config.redirect_uri_validator is validator

            assert provider == mock_provider_instance

    def test_factory_resolves_patterns_from_env_var(self) -> None:
        """Test that factory resolves static patterns from environment variable."""
        config = self._create_base_config(
            allowed_redirect_patterns_env_var="REDIRECT_PATTERNS",
            allowed_redirect_schemes_env_var="REDIRECT_SCHEMES",
        )

        env_vars = {
            "REDIRECT_PATTERNS": "https://env1.example.com/*, https://env2.example.com/*",
            "REDIRECT_SCHEMES": "myapp, custom",
        }

        # Mock the golf_enterprise module import
        mock_enterprise = Mock()
        mock_enterprise.create_oauth_proxy_provider.return_value = Mock()

        import sys

        with patch.dict(os.environ, env_vars), patch.dict(sys.modules, {"golf_enterprise": mock_enterprise}):
            _create_oauth_proxy_provider(config)

            resolved_config = mock_enterprise.create_oauth_proxy_provider.call_args[0][0]
            assert resolved_config.allowed_redirect_patterns == [
                "https://env1.example.com/*",
                "https://env2.example.com/*",
            ]
            assert resolved_config.allowed_redirect_schemes == ["myapp", "custom"]

    def test_callable_integration_with_feature_flags(self) -> None:
        """Test realistic integration pattern with simulated feature flags."""
        # Simulate a feature flag service
        feature_flags = {"enable_new_redirect_uris": False}

        def get_allowed_patterns() -> list[str]:
            base_patterns = ["https://legacy-app.example.com/*"]
            if feature_flags["enable_new_redirect_uris"]:
                base_patterns.append("https://new-app.example.com/*")
            return base_patterns

        config = self._create_base_config(
            allowed_redirect_patterns_func=get_allowed_patterns,
        )

        # Initial call - feature flag disabled
        patterns = config.allowed_redirect_patterns_func()
        assert patterns == ["https://legacy-app.example.com/*"]

        # Enable feature flag
        feature_flags["enable_new_redirect_uris"] = True

        # Call again - should include new pattern
        patterns = config.allowed_redirect_patterns_func()
        assert patterns == ["https://legacy-app.example.com/*", "https://new-app.example.com/*"]

    def test_callable_with_async_simulation(self) -> None:
        """Test that callable can wrap async operations (sync wrapper pattern)."""
        # Simulate a database lookup that might be async in real code
        db_allowed_uris = ["https://db-uri-1.example.com/callback"]

        def sync_db_lookup_wrapper(uri: str) -> bool:
            # In real code, this might use asyncio.run() or similar
            return uri in db_allowed_uris

        config = self._create_base_config(
            redirect_uri_validator=sync_db_lookup_wrapper,
        )

        assert config.redirect_uri_validator("https://db-uri-1.example.com/callback") is True
        assert config.redirect_uri_validator("https://unknown.example.com/callback") is False

        # Simulate adding a new URI to the "database"
        db_allowed_uris.append("https://new-uri.example.com/callback")

        # Validator should now accept the new URI
        assert config.redirect_uri_validator("https://new-uri.example.com/callback") is True
