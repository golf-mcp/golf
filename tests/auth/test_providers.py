"""Tests for authentication provider creation and configuration."""

import os
import sys
import pytest
from unittest.mock import Mock, patch
from pydantic import ValidationError

from golf.auth.providers import JWTAuthConfig, OAuthServerConfig, RemoteAuthConfig, OAuthProxyConfig
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


class TestOAuthProxyCreation:
    """Test OAuth proxy creation from configurations."""

    def test_oauth_proxy_creation_basic(self) -> None:
        """Test OAuth proxy creation with basic configuration."""
        # Create token verifier config
        token_verifier_config = JWTAuthConfig(
            jwks_uri="https://github.com/.well-known/jwks.json",
            issuer="https://github.com",
            audience="api://github",
            required_scopes=["read:user"],
        )

        config = OAuthProxyConfig(
            upstream_authorization_endpoint="https://github.com/login/oauth/authorize",
            upstream_token_endpoint="https://github.com/login/oauth/access_token",
            upstream_client_id="github_client_id",
            upstream_client_secret="github_client_secret",
            base_url="https://my-proxy.example.com",
            scopes_supported=["read:user", "user:email"],
            token_verifier_config=token_verifier_config,
        )

        # Mock our local OAuthProxy import
        with (
            patch("golf.auth.oauth_proxy.OAuthProxy") as mock_oauth_proxy_class,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth_provider,
        ):
            # Mock token verifier
            mock_token_verifier = Mock()
            mock_token_verifier.verify_token = Mock()
            mock_token_verifier.required_scopes = ["read:user"]
            mock_create_auth_provider.return_value = mock_token_verifier

            provider = _create_oauth_proxy_provider(config)

            # Verify token verifier was created
            mock_create_auth_provider.assert_called_once_with(token_verifier_config)

            # Verify OAuthProxy was called with correct parameters
            mock_oauth_proxy_class.assert_called_once_with(
                upstream_authorization_endpoint="https://github.com/login/oauth/authorize",
                upstream_token_endpoint="https://github.com/login/oauth/access_token",
                upstream_client_id="github_client_id",
                upstream_client_secret="github_client_secret",
                upstream_revocation_endpoint=None,
                base_url="https://my-proxy.example.com",
                redirect_path="/oauth/callback",
                token_verifier=mock_token_verifier,
                scopes_supported=["read:user", "user:email"],
            )

            # Verify token verifier scopes were updated
            assert mock_token_verifier.required_scopes == ["read:user", "user:email"]

            assert provider == mock_oauth_proxy_class.return_value

    def test_oauth_proxy_with_env_variables(self) -> None:
        """Test OAuth proxy creation with environment variable configuration."""
        token_verifier_config = JWTAuthConfig(
            jwks_uri="https://oauth2.googleapis.com/oauth2/v3/certs",
            issuer="https://accounts.google.com",
            audience="my-google-client-id",
        )

        config = OAuthProxyConfig(
            upstream_authorization_endpoint="https://default.example.com/auth",
            upstream_token_endpoint="https://default.example.com/token",
            upstream_client_id="default_client_id",
            upstream_client_secret="default_client_secret",
            base_url="https://default.example.com",
            upstream_authorization_endpoint_env_var="GOOGLE_AUTH_ENDPOINT",
            upstream_token_endpoint_env_var="GOOGLE_TOKEN_ENDPOINT",
            upstream_client_id_env_var="GOOGLE_CLIENT_ID",
            upstream_client_secret_env_var="GOOGLE_CLIENT_SECRET",
            base_url_env_var="PROXY_BASE_URL",
            scopes_supported=["openid", "profile", "email"],
            token_verifier_config=token_verifier_config,
        )

        env_vars = {
            "GOOGLE_AUTH_ENDPOINT": "https://accounts.google.com/o/oauth2/v2/auth",
            "GOOGLE_TOKEN_ENDPOINT": "https://oauth2.googleapis.com/token",
            "GOOGLE_CLIENT_ID": "env_google_client_id",
            "GOOGLE_CLIENT_SECRET": "env_google_client_secret",
            "PROXY_BASE_URL": "https://env-proxy.example.com",
        }

        # Mock our local OAuthProxy import
        with (
            patch("golf.auth.oauth_proxy.OAuthProxy") as mock_oauth_proxy_class,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth_provider,
            patch.dict(os.environ, env_vars),
        ):
            # Mock token verifier
            mock_token_verifier = Mock()
            mock_token_verifier.verify_token = Mock()
            mock_token_verifier.required_scopes = []
            mock_create_auth_provider.return_value = mock_token_verifier

            provider = _create_oauth_proxy_provider(config)

            # Verify environment variables were used
            mock_oauth_proxy_class.assert_called_once_with(
                upstream_authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
                upstream_token_endpoint="https://oauth2.googleapis.com/token",
                upstream_client_id="env_google_client_id",
                upstream_client_secret="env_google_client_secret",
                upstream_revocation_endpoint=None,
                base_url="https://env-proxy.example.com",
                redirect_path="/oauth/callback",
                token_verifier=mock_token_verifier,
                scopes_supported=["openid", "profile", "email"],
            )

            assert provider == mock_oauth_proxy_class.return_value

    def test_oauth_proxy_invalid_token_verifier(self) -> None:
        """Test OAuth proxy creation with invalid token verifier."""
        token_verifier_config = JWTAuthConfig(
            jwks_uri="https://example.com/.well-known/jwks.json",
        )

        config = OAuthProxyConfig(
            upstream_authorization_endpoint="https://provider.example.com/auth",
            upstream_token_endpoint="https://provider.example.com/token",
            upstream_client_id="client_id",
            upstream_client_secret="client_secret",
            base_url="https://proxy.example.com",
            token_verifier_config=token_verifier_config,
        )

        # Mock our local OAuthProxy import
        with (
            patch("golf.auth.oauth_proxy.OAuthProxy") as mock_oauth_proxy_class,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth_provider,
        ):
            # Mock invalid token verifier (missing verify_token method)
            mock_invalid_verifier = Mock(spec=[])  # No verify_token method
            mock_create_auth_provider.return_value = mock_invalid_verifier

            with pytest.raises(ValueError, match="OAuth proxy requires a TokenVerifier"):
                _create_oauth_proxy_provider(config)

    def test_oauth_proxy_missing_required_config(self) -> None:
        """Test OAuth proxy creation fails with missing required configuration."""
        token_verifier_config = JWTAuthConfig(jwks_uri="https://example.com/.well-known/jwks.json")

        # Test missing upstream_client_id - should fail at config validation level
        with pytest.raises(ValidationError, match="Client credentials cannot be empty"):
            OAuthProxyConfig(
                upstream_authorization_endpoint="https://provider.example.com/auth",
                upstream_token_endpoint="https://provider.example.com/token",
                upstream_client_id="",  # Empty, should fail
                upstream_client_secret="client_secret",
                base_url="https://proxy.example.com",
                token_verifier_config=token_verifier_config,
            )

    def test_oauth_proxy_creation_success(self) -> None:
        """Test OAuth proxy creation succeeds with local implementation."""
        token_verifier_config = JWTAuthConfig(jwks_uri="https://example.com/.well-known/jwks.json")

        config = OAuthProxyConfig(
            upstream_authorization_endpoint="https://provider.example.com/auth",
            upstream_token_endpoint="https://provider.example.com/token",
            upstream_client_id="client_id",
            upstream_client_secret="client_secret",
            base_url="https://proxy.example.com",
            token_verifier_config=token_verifier_config,
        )

        # Mock our local OAuthProxy implementation
        with (
            patch("golf.auth.oauth_proxy.OAuthProxy") as mock_oauth_proxy_class,
            patch("golf.auth.factory.create_auth_provider") as mock_create_auth_provider,
        ):
            # Mock token verifier
            mock_token_verifier = Mock()
            mock_token_verifier.verify_token = Mock()
            mock_token_verifier.required_scopes = []
            mock_create_auth_provider.return_value = mock_token_verifier

            provider = _create_oauth_proxy_provider(config)

            # Verify OAuthProxy was created successfully with our local implementation
            mock_oauth_proxy_class.assert_called_once()
            assert provider == mock_oauth_proxy_class.return_value
