"""Release A authentication code-generation integration tests."""

from unittest.mock import patch

import pytest
from fastmcp import FastMCP

from golf.auth.factory import _create_remote_provider
from golf.auth.providers import JWTAuthConfig, RemoteAuthConfig, StaticTokenConfig
from golf.core.builder_auth import generate_auth_code, generate_auth_routes


def test_generated_configured_auth_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider construction errors must abort generated-server import."""
    config = StaticTokenConfig(tokens={"test": {"client_id": "test", "scopes": []}})
    monkeypatch.setattr("golf.core.builder_auth.get_api_key_config", lambda: None)
    monkeypatch.setattr("golf.core.builder_auth.get_auth_config", lambda: config)
    components = generate_auth_code("test")
    setup_code = "\n".join(components["setup_code"])

    assert "auth_provider = None" not in setup_code
    assert "except Exception" not in setup_code
    with (
        patch("golf.auth.factory.create_auth_provider", side_effect=RuntimeError("invalid auth")),
        pytest.raises(RuntimeError, match="invalid auth"),
    ):
        exec("\n".join([*components["imports"], setup_code]), {})


def test_fastmcp_registers_auth_routes_once() -> None:
    """Golf relies solely on FastMCP 3.4.7 auth route registration."""
    provider = _create_remote_provider(
        RemoteAuthConfig(
            authorization_servers=["https://auth.example.com"],
            resource_server_url="https://api.example.com",
            token_verifier_config=JWTAuthConfig(
                jwks_uri="https://auth.example.com/.well-known/jwks.json",
                audience="https://api.example.com",
            ),
        )
    )
    app = FastMCP("test", auth=provider).http_app()
    protected_resource_routes = [
        route.path for route in app.routes if route.path.startswith("/.well-known/oauth-protected-resource")
    ]

    assert protected_resource_routes == ["/.well-known/oauth-protected-resource/mcp"]
    assert generate_auth_routes() == ""
