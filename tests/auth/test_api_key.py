"""Tests for deprecated API key header extraction."""

from collections.abc import Generator

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from golf.auth.api_key import (
    ApiKeyMiddleware,
    configure_api_key,
    extract_api_key_from_headers,
    get_api_key_config,
    is_api_key_configured,
    reset_api_key_config,
)


@pytest.fixture(autouse=True)
def reset_api_key_config_fixture() -> Generator[None, None, None]:
    """Keep API key configuration isolated between tests."""
    reset_api_key_config()
    yield
    reset_api_key_config()


class TestAPIKeyConfiguration:
    """Test API key configuration functionality."""

    def test_configure_api_key_is_deprecated(self) -> None:
        """Calling configure_api_key() must warn that it is not authentication."""
        with pytest.warns(DeprecationWarning, match="not MCP authentication"):
            configure_api_key()

    def test_configure_api_key_basic(self) -> None:
        """Test basic API key configuration."""
        assert not is_api_key_configured()

        configure_api_key()

        assert is_api_key_configured()
        config = get_api_key_config()
        assert config is not None
        assert config.header_name == "X-API-Key"
        assert config.header_prefix == ""
        assert config.required is True

    def test_configure_api_key_custom(self) -> None:
        """Test API key configuration with custom settings."""
        configure_api_key(header_name="Authorization", header_prefix="Bearer ", required=False)

        assert is_api_key_configured()
        config = get_api_key_config()
        assert config is not None
        assert config.header_name == "Authorization"
        assert config.header_prefix == "Bearer "
        assert config.required is False

    def test_clear_api_key_configuration(self) -> None:
        """Test clearing API key configuration."""
        configure_api_key()
        assert is_api_key_configured()

        reset_api_key_config()

        assert not is_api_key_configured()
        assert get_api_key_config() is None

    def test_api_key_persistence(self) -> None:
        """Test that API key configuration persists across calls."""
        configure_api_key(header_name="Custom-Key")

        assert is_api_key_configured()
        config1 = get_api_key_config()
        config2 = get_api_key_config()

        assert config1 == config2
        assert config2 is not None
        assert config2.header_name == "Custom-Key"

    def test_extract_strips_configured_prefix(self) -> None:
        configure_api_key(header_name="Authorization", header_prefix="Bearer ")
        config = get_api_key_config()
        assert config is not None
        assert extract_api_key_from_headers({"Authorization": "Bearer secret"}, config) == "secret"


def _app_with_api_key_middleware() -> TestClient:
    async def ok(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "api_key": getattr(request.state, "api_key", None)})

    app = Starlette(
        routes=[
            Route("/", ok),
            Route("/health", ok),
        ],
        middleware=[Middleware(ApiKeyMiddleware)],
    )
    return TestClient(app)


class TestApiKeyMiddleware:
    """HTTP-level tests for pass-through header extraction."""

    def test_any_present_value_is_forwarded(self) -> None:
        """Golf does not validate the key; any non-empty value is extracted."""
        configure_api_key()
        client = _app_with_api_key_middleware()

        response = client.get("/", headers={"X-API-Key": "anything-at-all"})

        assert response.status_code == 200
        assert response.json()["api_key"] == "anything-at-all"

    def test_missing_header_is_rejected_when_required(self) -> None:
        configure_api_key()
        client = _app_with_api_key_middleware()

        response = client.get("/")

        assert response.status_code == 401

    def test_missing_header_is_allowed_when_optional(self) -> None:
        configure_api_key(required=False)
        client = _app_with_api_key_middleware()

        response = client.get("/")

        assert response.status_code == 200
        assert response.json()["api_key"] is None

    def test_bearer_prefix_is_stripped(self) -> None:
        configure_api_key(header_name="Authorization", header_prefix="Bearer ")
        client = _app_with_api_key_middleware()

        response = client.get("/", headers={"Authorization": "Bearer upstream-secret"})

        assert response.status_code == 200
        assert response.json()["api_key"] == "upstream-secret"

    def test_health_endpoint_skips_extraction(self) -> None:
        configure_api_key()
        client = _app_with_api_key_middleware()

        response = client.get("/health")

        assert response.status_code == 200
