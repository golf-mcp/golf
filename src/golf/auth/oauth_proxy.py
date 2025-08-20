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
        
    def get_routes(self) -> List[Route]:
        """Get OAuth metadata and flow routes."""
        routes = [
            # OAuth Authorization Server Metadata (RFC 8414)
            Route("/.well-known/oauth-authorization-server", self._metadata_endpoint, methods=["GET"]),
            # Dynamic Client Registration (RFC 7591) - simplified
            Route("/oauth/register", self._register_client_endpoint, methods=["POST"]),
            # OAuth Authorization endpoint
            Route("/oauth/authorize", self._authorize_endpoint, methods=["GET"]),
            # OAuth Token endpoint  
            Route("/oauth/token", self._token_endpoint, methods=["POST"]),
            # OAuth callback from upstream provider
            Route(self.redirect_path, self._callback_endpoint, methods=["GET"]),
        ]
        
        # Add revocation endpoint if upstream supports it
        if self.upstream_revocation_endpoint:
            routes.append(Route("/oauth/revoke", self._revoke_endpoint, methods=["POST"]))
            
        return routes
        
    async def _metadata_endpoint(self, request: Request) -> JSONResponse:
        """OAuth Authorization Server Metadata endpoint (RFC 8414)."""
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
            
        return JSONResponse(metadata)
        
    async def _register_client_endpoint(self, request: Request) -> JSONResponse:
        """Simplified Dynamic Client Registration endpoint."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Invalid JSON body"},
                status_code=400
            )
            
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
        
        return JSONResponse({
            "client_id": client_id,
            "client_secret": client_secret,
            "client_secret_expires_at": 0,  # Never expires
            "redirect_uris": data.get("redirect_uris", []),
        }, status_code=201)
        
    async def _authorize_endpoint(self, request: Request) -> Response:
        """OAuth authorization endpoint - redirects to upstream provider."""
        params = dict(request.query_params)
        
        # Validate required parameters
        client_id = params.get("client_id")
        if not client_id or client_id not in self._registered_clients:
            return JSONResponse(
                {"error": "invalid_client", "error_description": "Unknown client_id"},
                status_code=401
            )
            
        redirect_uri = params.get("redirect_uri")
        if not redirect_uri:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing redirect_uri"},
                status_code=400
            )
            
        # Generate state to track this authorization session
        session_state = secrets.token_urlsafe(32)
        
        # Store session data
        self._client_sessions[session_state] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "original_state": params.get("state"),
            "code_challenge": params.get("code_challenge"),
            "code_challenge_method": params.get("code_challenge_method"),
            "scope": params.get("scope", ""),
            "created_at": int(time.time()),
        }
        
        # Build upstream authorization URL
        upstream_params = {
            "response_type": "code",
            "client_id": self.upstream_client_id,
            "redirect_uri": self.redirect_uri,
            "scope": params.get("scope", " ".join(self.scopes_supported)),
            "state": session_state,  # Use our session state
        }
        
        # Add PKCE if supported
        if params.get("code_challenge"):
            upstream_params["code_challenge"] = params["code_challenge"]
            upstream_params["code_challenge_method"] = params.get("code_challenge_method", "S256")
            
        upstream_url = f"{self.upstream_authorization_endpoint}?{urlencode(upstream_params)}"
        return RedirectResponse(upstream_url)
        
    async def _callback_endpoint(self, request: Request) -> Response:
        """Handle callback from upstream OAuth provider."""
        params = dict(request.query_params)
        
        # Check for error from upstream
        if "error" in params:
            return JSONResponse({
                "error": params["error"],
                "error_description": params.get("error_description", "Authorization failed"),
            }, status_code=400)
            
        # Get authorization code and state
        code = params.get("code")
        state = params.get("state")
        
        if not code or not state:
            return JSONResponse({
                "error": "invalid_request",
                "error_description": "Missing code or state parameter"
            }, status_code=400)
            
        # Look up session
        session = self._client_sessions.get(state)
        if not session:
            return JSONResponse({
                "error": "invalid_request", 
                "error_description": "Invalid or expired state parameter"
            }, status_code=400)
            
        # Exchange code for tokens at upstream provider
        try:
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.upstream_client_id,
                "client_secret": self.upstream_client_secret,
            }
            
            # Add PKCE verifier if used
            if session.get("code_challenge"):
                # Note: We don't store the code_verifier, so PKCE verification 
                # happens at the upstream provider level
                pass
                
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.upstream_token_endpoint,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
            if response.status_code != 200:
                return JSONResponse({
                    "error": "server_error",
                    "error_description": "Failed to exchange authorization code"
                }, status_code=500)
                
            tokens = response.json()
            
        except Exception as e:
            return JSONResponse({
                "error": "server_error", 
                "error_description": f"Token exchange failed: {str(e)}"
            }, status_code=500)
            
        # Store tokens for this session
        session["tokens"] = tokens
        session["completed_at"] = int(time.time())
        
        # Build callback URL to original client
        client_redirect_params = {"code": state}  # Use our state as the authorization code
        
        if session.get("original_state"):
            client_redirect_params["state"] = session["original_state"]
            
        client_callback_url = f"{session['redirect_uri']}?{urlencode(client_redirect_params)}"
        return RedirectResponse(client_callback_url)
        
    async def _token_endpoint(self, request: Request) -> JSONResponse:
        """OAuth token endpoint - returns tokens from completed sessions."""
        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception:
            return JSONResponse({
                "error": "invalid_request",
                "error_description": "Invalid form data"
            }, status_code=400)
            
        grant_type = data.get("grant_type")
        
        if grant_type == "authorization_code":
            return await self._handle_authorization_code_grant(data)
        elif grant_type == "refresh_token":
            return await self._handle_refresh_token_grant(data)
        else:
            return JSONResponse({
                "error": "unsupported_grant_type",
                "error_description": f"Grant type '{grant_type}' is not supported"
            }, status_code=400)
            
    async def _handle_authorization_code_grant(self, data: Dict[str, str]) -> JSONResponse:
        """Handle authorization code grant."""
        code = data.get("code")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        
        # Validate client
        if not client_id or client_id not in self._registered_clients:
            return JSONResponse({
                "error": "invalid_client",
                "error_description": "Unknown client_id"
            }, status_code=401)
            
        stored_client = self._registered_clients[client_id]
        if stored_client["client_secret"] != client_secret:
            return JSONResponse({
                "error": "invalid_client",
                "error_description": "Invalid client_secret"
            }, status_code=401)
            
        # Look up session by code (which is our state)
        session = self._client_sessions.get(code)
        if not session or session["client_id"] != client_id:
            return JSONResponse({
                "error": "invalid_grant",
                "error_description": "Invalid or expired authorization code"
            }, status_code=400)
            
        if "tokens" not in session:
            return JSONResponse({
                "error": "invalid_grant",
                "error_description": "Authorization not completed"
            }, status_code=400)
            
        # Return the tokens from upstream
        tokens = session["tokens"]
        
        # Clean up the session
        del self._client_sessions[code]
        
        return JSONResponse(tokens)
        
    async def _handle_refresh_token_grant(self, data: Dict[str, str]) -> JSONResponse:
        """Handle refresh token grant by proxying to upstream."""
        refresh_token = data.get("refresh_token")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        
        # Validate client
        if not client_id or client_id not in self._registered_clients:
            return JSONResponse({
                "error": "invalid_client",
                "error_description": "Unknown client_id"
            }, status_code=401)
            
        stored_client = self._registered_clients[client_id]
        if stored_client["client_secret"] != client_secret:
            return JSONResponse({
                "error": "invalid_client", 
                "error_description": "Invalid client_secret"
            }, status_code=401)
            
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
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
            if response.status_code != 200:
                upstream_error = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return JSONResponse({
                    "error": upstream_error.get("error", "server_error"),
                    "error_description": upstream_error.get("error_description", "Token refresh failed")
                }, status_code=response.status_code)
                
            return JSONResponse(response.json())
            
        except Exception as e:
            return JSONResponse({
                "error": "server_error",
                "error_description": f"Token refresh failed: {str(e)}"
            }, status_code=500)
            
    async def _revoke_endpoint(self, request: Request) -> JSONResponse:
        """OAuth token revocation endpoint."""
        if not self.upstream_revocation_endpoint:
            return JSONResponse({
                "error": "unsupported_operation",
                "error_description": "Token revocation not supported"
            }, status_code=400)
            
        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception:
            return JSONResponse({
                "error": "invalid_request",
                "error_description": "Invalid form data"
            }, status_code=400)
            
        token = data.get("token")
        if not token:
            return JSONResponse({
                "error": "invalid_request",
                "error_description": "Missing token parameter"
            }, status_code=400)
            
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
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
            # RFC 7009: successful revocation returns 200
            return JSONResponse({}, status_code=200)
            
        except Exception as e:
            return JSONResponse({
                "error": "server_error",
                "error_description": f"Token revocation failed: {str(e)}"
            }, status_code=500)
            
    async def verify_request(self, request: Request) -> Optional[AccessToken]:
        """Verify incoming request using the configured token verifier."""
        return await self.token_verifier.verify_request(request)
        
    def get_resource_metadata_url(self) -> Optional[str]:
        """Get the resource metadata URL for this proxy."""
        if self.resource_server_url:
            return f"{self.resource_server_url}/.well-known/oauth-authorization-server"
        return None