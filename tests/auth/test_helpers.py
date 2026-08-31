"""Tests for safe authentication context helpers."""

from unittest.mock import patch

from fastmcp.server.auth import AccessToken

from golf.auth import get_caller_auth


def test_get_caller_auth_omits_mcp_resource_token() -> None:
    """Caller inspection exposes identity metadata, never bearer credentials."""
    access_token = AccessToken(
        token="secret-mcp-resource-token",
        client_id="client-123",
        scopes=["read", "write"],
        subject="user-456",
        resource="https://mcp.example.com",
    )

    with patch("fastmcp.server.dependencies.get_access_token", return_value=access_token):
        caller = get_caller_auth()

    assert caller is not None
    assert caller.client_id == "client-123"
    assert caller.scopes == ("read", "write")
    assert caller.subject == "user-456"
    assert caller.resource == "https://mcp.example.com"
    assert not hasattr(caller, "token")
