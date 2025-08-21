"""OAuth Proxy implementation for bridging non-DCR providers with MCP clients.

This module implements an OAuth proxy that allows MCP clients expecting Dynamic Client
Registration (DCR) to work with OAuth providers that use fixed client credentials
(like Okta Web Applications, GitHub Apps, Google Cloud Console apps, etc.).

The proxy acts as a bridge:
1. MCP clients register with the proxy → receive fixed upstream credentials
2. MCP clients start OAuth flow → proxy redirects to upstream provider
3. Upstream provider returns tokens → proxy validates and returns to client
4. MCP clients use tokens for API access → proxy validates tokens
"""

import secrets
import time
import base64
import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import httpx
from fastmcp.server.auth.auth import AuthProvider
from fastmcp.server.auth import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route


class OAuthProxy(AuthProvider):
    """OAuth proxy for bridging non-DCR providers with MCP clients expecting DCR.

    This proxy allows MCP clients to use OAuth providers that don't support Dynamic
    Client Registration by providing a fixed set of client credentials and handling
    the OAuth flow on behalf of the client.
    """

    def __init__(
        self,
        upstream_authorization_endpoint: str,
        upstream_token_endpoint: str,
        upstream_client_id: str,
        upstream_client_secret: str,
        base_url: str,
        token_verifier: TokenVerifier,
        upstream_revocation_endpoint: Optional[str] = None,
        redirect_path: str = "/oauth/callback",
        scopes_supported: Optional[List[str]] = None,
    ):
        """Initialize OAuth proxy.

        Args:
            upstream_authorization_endpoint: Upstream provider's authorization endpoint
            upstream_token_endpoint: Upstream provider's token endpoint
            upstream_client_id: Your registered client ID with upstream provider
            upstream_client_secret: Your registered client secret with upstream provider
            base_url: Public URL of this proxy server
            token_verifier: Token verifier for validating upstream tokens
            upstream_revocation_endpoint: Optional upstream revocation endpoint
            redirect_path: Callback path (must match provider registration)
            scopes_supported: Scopes this proxy supports
        """
        self.upstream_authorization_endpoint = upstream_authorization_endpoint
        self.upstream_token_endpoint = upstream_token_endpoint
        self.upstream_client_id = upstream_client_id
        self.upstream_client_secret = upstream_client_secret
        self.upstream_revocation_endpoint = upstream_revocation_endpoint
        self.base_url = base_url.rstrip("/")
        self.redirect_path = redirect_path
        self.redirect_uri = f"{self.base_url}{self.redirect_path}"
        self.token_verifier = token_verifier
        self.scopes_supported = scopes_supported or []

        # FastMCP expects this attribute for resource metadata
        self.resource_server_url = base_url

        # In-memory storage for active sessions (in production, use Redis/database)
        self._client_sessions: Dict[str, Dict[str, Any]] = {}
        self._registered_clients: Dict[str, Dict[str, Any]] = {}

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge pair."""
        # Generate a cryptographically secure random code_verifier
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")

        # Generate code_challenge using SHA256
        challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

        return code_verifier, code_challenge

    def get_routes(self) -> List[Route]:
        """Get OAuth metadata and flow routes."""
        routes = [
            # OAuth Authorization Server Metadata (RFC 8414)
            Route("/.well-known/oauth-authorization-server", self._metadata_endpoint, methods=["GET", "OPTIONS"]),
            # Protected Resource Metadata (RFC 9728)
            Route(
                "/.well-known/oauth-protected-resource", self._protected_resource_metadata, methods=["GET", "OPTIONS"]
            ),
            Route(
                "/.well-known/oauth-protected-resource/mcp",
                self._protected_resource_metadata,
                methods=["GET", "OPTIONS"],
            ),
            # OpenID Connect Discovery (for compatibility)
            Route("/.well-known/openid-configuration", self._openid_configuration, methods=["GET", "OPTIONS"]),
            # Dynamic Client Registration (RFC 7591) - simplified
            Route("/oauth/register", self._register_client_endpoint, methods=["POST", "OPTIONS"]),
            # OAuth Authorization endpoint
            Route("/oauth/authorize", self._authorize_endpoint, methods=["GET", "OPTIONS"]),
            # OAuth Token endpoint
            Route("/oauth/token", self._token_endpoint, methods=["POST", "OPTIONS"]),
            # OAuth callback from upstream provider
            Route(self.redirect_path, self._callback_endpoint, methods=["GET", "OPTIONS"]),
        ]

        # Add revocation endpoint if upstream supports it
        if self.upstream_revocation_endpoint:
            routes.append(Route("/oauth/revoke", self._revoke_endpoint, methods=["POST", "OPTIONS"]))

        return routes

    async def _metadata_endpoint(self, request: Request) -> Response:
        """OAuth Authorization Server Metadata endpoint (RFC 8414)."""
        if request.method == "OPTIONS":
            return self._cors_response()

        metadata = {
            "issuer": self.base_url,
            "authorization_endpoint": f"{self.base_url}/oauth/authorize",
            "token_endpoint": f"{self.base_url}/oauth/token",
            "registration_endpoint": f"{self.base_url}/oauth/register",
            "scopes_supported": self.scopes_supported,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
            "code_challenge_methods_supported": ["S256"],
        }

        if self.upstream_revocation_endpoint:
            metadata["revocation_endpoint"] = f"{self.base_url}/oauth/revoke"

        return self._cors_json_response(metadata)

    async def _protected_resource_metadata(self, request: Request) -> Response:
        """Protected Resource Metadata endpoint (RFC 9728)."""
        if request.method == "OPTIONS":
            return self._cors_response()

        metadata = {
            "resource": self.base_url,
            "authorization_servers": [self.base_url],
            "scopes_supported": self.scopes_supported,
            "bearer_methods_supported": ["header"],
            "resource_documentation": f"{self.base_url}",
        }

        return self._cors_json_response(metadata)

    async def _openid_configuration(self, request: Request) -> Response:
        """OpenID Connect Discovery endpoint (for compatibility)."""
        if request.method == "OPTIONS":
            return self._cors_response()

        # Provide minimal OpenID Connect metadata for compatibility
        metadata = {
            "issuer": self.base_url,
            "authorization_endpoint": f"{self.base_url}/oauth/authorize",
            "token_endpoint": f"{self.base_url}/oauth/token",
            "jwks_uri": f"{self.base_url}/.well-known/jwks.json",
            "registration_endpoint": f"{self.base_url}/oauth/register",
            "scopes_supported": self.scopes_supported + ["openid"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
            "code_challenge_methods_supported": ["S256"],
        }

        if self.upstream_revocation_endpoint:
            metadata["revocation_endpoint"] = f"{self.base_url}/oauth/revoke"

        return self._cors_json_response(metadata)

    def _cors_response(self) -> Response:
        """Return CORS preflight response."""
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Max-Age": "3600",
            },
        )

    def _cors_json_response(self, data: dict) -> JSONResponse:
        """Return JSON response with CORS headers."""
        return JSONResponse(
            data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
            },
        )

    async def _register_client_endpoint(self, request: Request) -> Response:
        """Simplified Dynamic Client Registration endpoint."""
        if request.method == "OPTIONS":
            return self._cors_response()

        try:
            data = await request.json()
        except Exception:
            return self._cors_json_response({"error": "invalid_request", "error_description": "Invalid JSON body"})

        # Generate client credentials
        client_id = f"proxy_client_{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(32)

        # Store client registration
        self._registered_clients[client_id] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": data.get("redirect_uris", []),
            "client_name": data.get("client_name", "MCP Client"),
            "created_at": int(time.time()),
        }

        response_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_secret_expires_at": 0,  # Never expires
            "redirect_uris": data.get("redirect_uris", []),
        }

        return self._cors_json_response(response_data)

    async def _authorize_endpoint(self, request: Request) -> Response:
        """OAuth authorization endpoint - redirects to upstream provider."""
        if request.method == "OPTIONS":
            return self._cors_response()

        params = dict(request.query_params)

        # Validate required parameters
        client_id = params.get("client_id")
        if not client_id or client_id not in self._registered_clients:
            return self._cors_json_response({"error": "invalid_client", "error_description": "Unknown client_id"})

        redirect_uri = params.get("redirect_uri")
        if not redirect_uri:
            return self._cors_json_response({"error": "invalid_request", "error_description": "Missing redirect_uri"})

        # Generate state to track this authorization session
        session_state = secrets.token_urlsafe(32)

        # Generate proxy's own PKCE pair for upstream provider
        proxy_code_verifier, proxy_code_challenge = self._generate_pkce_pair()

        # Store session data with both client and proxy PKCE info
        self._client_sessions[session_state] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "original_state": params.get("state"),
            # Client's PKCE challenge (for later validation)
            "client_code_challenge": params.get("code_challenge"),
            "client_code_challenge_method": params.get("code_challenge_method"),
            # Proxy's PKCE verifier (for upstream exchange)
            "proxy_code_verifier": proxy_code_verifier,
            "scope": params.get("scope", ""),
            "created_at": int(time.time()),
        }

        # Build upstream authorization URL with proxy's own PKCE challenge
        upstream_params = {
            "response_type": "code",
            "client_id": self.upstream_client_id,
            "redirect_uri": self.redirect_uri,
            "scope": params.get("scope", " ".join(self.scopes_supported)),
            "state": session_state,  # Use our session state
            "code_challenge": proxy_code_challenge,  # Use proxy's PKCE challenge
            "code_challenge_method": "S256",
        }

        upstream_url = f"{self.upstream_authorization_endpoint}?{urlencode(upstream_params)}"
        return RedirectResponse(upstream_url)

    async def _callback_endpoint(self, request: Request) -> Response:
        """Handle callback from upstream OAuth provider."""
        if request.method == "OPTIONS":
            return self._cors_response()

        params = dict(request.query_params)

        # Check for error from upstream
        if "error" in params:
            return self._cors_json_response(
                {
                    "error": params["error"],
                    "error_description": params.get("error_description", "Authorization failed"),
                }
            )

        # Get authorization code and state
        code = params.get("code")
        state = params.get("state")

        if not code or not state:
            return self._cors_json_response(
                {"error": "invalid_request", "error_description": "Missing code or state parameter"}
            )

        # Look up session
        session = self._client_sessions.get(state)
        if not session:
            return self._cors_json_response(
                {"error": "invalid_request", "error_description": "Invalid or expired state parameter"}
            )

        # Exchange code for tokens at upstream provider
        try:
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.upstream_client_id,
                "client_secret": self.upstream_client_secret,
            }

            # Add proxy's PKCE code_verifier for upstream token exchange
            if session.get("proxy_code_verifier"):
                token_data["code_verifier"] = session["proxy_code_verifier"]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.upstream_token_endpoint,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if response.status_code != 200:
                # Log the actual error for debugging
                error_details = f"Status: {response.status_code}"
                try:
                    error_body = response.json()
                    error_details += f", Body: {error_body}"
                except:
                    error_details += f", Text: {response.text}"

                return self._cors_json_response(
                    {
                        "error": "server_error",
                        "error_description": f"Failed to exchange authorization code: {error_details}",
                    }
                )

            tokens = response.json()

        except Exception as e:
            return self._cors_json_response(
                {"error": "server_error", "error_description": f"Token exchange failed: {str(e)}"}
            )

        # Generate a NEW authorization code for the client (not the upstream state)
        client_code = secrets.token_urlsafe(32)

        # Store the client code with tokens and original session data
        self._client_sessions[client_code] = {
            "client_id": session["client_id"],
            "redirect_uri": session["redirect_uri"],
            "original_state": session.get("original_state"),
            "client_code_challenge": session.get("client_code_challenge"),
            "client_code_challenge_method": session.get("client_code_challenge_method"),
            "tokens": tokens,  # Store the upstream tokens
            "completed_at": int(time.time()),
            "created_at": session.get("created_at"),
        }

        # Clean up the original session (keyed by upstream state)
        del self._client_sessions[state]

        # Build callback URL to original client with our NEW client code
        client_redirect_params = {"code": client_code}  # Use our NEW client code

        if session.get("original_state"):
            client_redirect_params["state"] = session["original_state"]

        client_callback_url = f"{session['redirect_uri']}?{urlencode(client_redirect_params)}"
        return RedirectResponse(client_callback_url)

    async def _token_endpoint(self, request: Request) -> Response:
        """OAuth token endpoint - returns tokens from completed sessions."""
        if request.method == "OPTIONS":
            return self._cors_response()

        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception:
            return self._cors_json_response({"error": "invalid_request", "error_description": "Invalid form data"})

        grant_type = data.get("grant_type")

        if grant_type == "authorization_code":
            return await self._handle_authorization_code_grant(data)
        elif grant_type == "refresh_token":
            return await self._handle_refresh_token_grant(data)
        else:
            return self._cors_json_response(
                {"error": "unsupported_grant_type", "error_description": f"Grant type '{grant_type}' is not supported"}
            )

    async def _handle_authorization_code_grant(self, data: Dict[str, str]) -> Response:
        """Handle authorization code grant."""
        code = data.get("code")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")

        # Validate client
        if not client_id or client_id not in self._registered_clients:
            return self._cors_json_response({"error": "invalid_client", "error_description": "Unknown client_id"})

        stored_client = self._registered_clients[client_id]

        # For PKCE flows, client secret is optional (RFC 7636)
        # Only validate client secret if one was provided
        if client_secret is not None and client_secret != "None":
            if stored_client["client_secret"] != client_secret:
                return self._cors_json_response(
                    {"error": "invalid_client", "error_description": "Invalid client_secret"}
                )

        # Look up session by code (which is our client code)
        session = self._client_sessions.get(code)

        if not session:
            return self._cors_json_response(
                {"error": "invalid_grant", "error_description": "Authorization code not found"}
            )

        if session["client_id"] != client_id:
            return self._cors_json_response(
                {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}
            )

        if "tokens" not in session:
            return self._cors_json_response(
                {"error": "invalid_grant", "error_description": "Authorization not completed"}
            )

        # Return the tokens from upstream
        tokens = session["tokens"]

        # Clean up the session
        del self._client_sessions[code]

        return self._cors_json_response(tokens)

    async def _handle_refresh_token_grant(self, data: Dict[str, str]) -> Response:
        """Handle refresh token grant by proxying to upstream."""
        refresh_token = data.get("refresh_token")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")

        # Validate client
        if not client_id or client_id not in self._registered_clients:
            return self._cors_json_response({"error": "invalid_client", "error_description": "Unknown client_id"})

        stored_client = self._registered_clients[client_id]
        if stored_client["client_secret"] != client_secret:
            return self._cors_json_response({"error": "invalid_client", "error_description": "Invalid client_secret"})

        # Proxy refresh to upstream provider
        try:
            token_data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.upstream_client_id,
                "client_secret": self.upstream_client_secret,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.upstream_token_endpoint,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if response.status_code != 200:
                upstream_error = (
                    response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                )
                return self._cors_json_response(
                    {
                        "error": upstream_error.get("error", "server_error"),
                        "error_description": upstream_error.get("error_description", "Token refresh failed"),
                    }
                )

            return self._cors_json_response(response.json())

        except Exception as e:
            return self._cors_json_response(
                {"error": "server_error", "error_description": f"Token refresh failed: {str(e)}"}
            )

    async def _revoke_endpoint(self, request: Request) -> Response:
        """OAuth token revocation endpoint."""
        if request.method == "OPTIONS":
            return self._cors_response()

        if not self.upstream_revocation_endpoint:
            return self._cors_json_response(
                {"error": "unsupported_operation", "error_description": "Token revocation not supported"}
            )

        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception:
            return self._cors_json_response({"error": "invalid_request", "error_description": "Invalid form data"})

        token = data.get("token")
        if not token:
            return self._cors_json_response(
                {"error": "invalid_request", "error_description": "Missing token parameter"}
            )

        # Proxy revocation to upstream provider
        try:
            revoke_data = {
                "token": token,
                "client_id": self.upstream_client_id,
                "client_secret": self.upstream_client_secret,
            }

            async with httpx.AsyncClient() as client:
                await client.post(
                    self.upstream_revocation_endpoint,
                    data=revoke_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            # RFC 7009: successful revocation returns 200
            return self._cors_json_response({})

        except Exception as e:
            return self._cors_json_response(
                {"error": "server_error", "error_description": f"Token revocation failed: {str(e)}"}
            )

    async def verify_request(self, request: Request) -> Optional[AccessToken]:
        """Verify incoming request using the configured token verifier."""
        return await self.token_verifier.verify_request(request)

    async def verify_token(self, token: str) -> dict:
        """Verify a bearer token using the configured token verifier."""
        try:
            result = await self.token_verifier.verify_token(token)

            # If result is None but no exception was raised, create a proper auth info object
            if result is None:
                from types import SimpleNamespace

                auth_info = SimpleNamespace()
                auth_info.client_id = "oauth_proxy"
                auth_info.scopes = ["openid"]
                auth_info.expires_at = None  # FastMCP checks for this attribute
                return auth_info

            return result
        except Exception as e:
            raise

    def get_resource_metadata_url(self) -> Optional[str]:
        """Get the resource metadata URL for this proxy."""
        if self.resource_server_url:
            return f"{self.resource_server_url}/.well-known/oauth-authorization-server"
        return None
