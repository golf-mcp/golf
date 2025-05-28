"""OAuth provider implementation for GolfMCP.

This module provides an implementation of the MCP OAuthAuthorizationServerProvider
interface for GolfMCP servers. It handles the OAuth 2.0 authentication flow,
token management, and client registration.
"""

import os
import time
import uuid
from datetime import datetime
from typing import Any

import httpx
import jwt
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
)
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthToken,
)
from starlette.responses import RedirectResponse

from .provider import ProviderConfig


class TokenStorage:
    """Simple in-memory token storage.

    This class provides a simple in-memory storage for OAuth tokens,
    authorization codes, and client information. In a production
    environment, this should be replaced with a persistent storage
    solution.
    """

    def __init__(self) -> None:
        """Initialize the token storage."""
        self.auth_codes = {}  # code_str -> AuthorizationCode
        self.refresh_tokens = {}  # token_str -> RefreshToken
        self.access_tokens = {}  # token_str -> AccessToken
        self.clients = {}  # client_id -> OAuthClientInformationFull
        self.provider_tokens = {}  # mcp_access_token_str -> provider_access_token_str
        self.auth_code_to_provider_token = {}  # auth_code_str -> provider_access_token_str

    def store_auth_code(
        self, code: str, auth_code_obj: AuthorizationCode
    ) -> None:  # Renamed auth_code to auth_code_obj for clarity
        """Store an authorization code.

        Args:
            code: The authorization code string
            auth_code_obj: The authorization code object
        """
        self.auth_codes[code] = auth_code_obj

    def get_auth_code(self, code: str) -> AuthorizationCode | None:
        """Get an authorization code by value.

        Args:
            code: The authorization code string

        Returns:
            The authorization code object or None if not found
        """
        return self.auth_codes.get(code)

    def delete_auth_code(self, code: str) -> None:
        """Delete an authorization code and its associated provider token mapping.

        Args:
            code: The authorization code string
        """
        if code in self.auth_codes:
            del self.auth_codes[code]
        if code in self.auth_code_to_provider_token:
            del self.auth_code_to_provider_token[code]

    def store_auth_code_provider_token_mapping(
        self, auth_code_str: str, provider_token: str
    ) -> None:
        """Store a mapping from an auth_code string to a provider_token string."""
        self.auth_code_to_provider_token[auth_code_str] = provider_token

    def get_provider_token_for_auth_code(self, auth_code_str: str) -> str | None:
        """Retrieve a provider_token string using an auth_code string."""
        return self.auth_code_to_provider_token.get(auth_code_str)

    def store_client(self, client_id: str, client: OAuthClientInformationFull) -> None:
        """Store client information.

        Args:
            client_id: The client ID
            client: The client information
        """
        self.clients[client_id] = client

    def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Get client information by ID.

        Args:
            client_id: The client ID

        Returns:
            The client information or None if not found
        """
        # _diag_logger.info(f"TokenStorage: get_client called for client_id '{client_id}'. Known clients: {list(self.clients.keys())}") # Optional: uncomment for debugging
        return self.clients.get(client_id)

    def store_refresh_token(self, token: str, refresh_token: RefreshToken) -> None:
        """Store a refresh token.

        Args:
            token: The refresh token string
            refresh_token: The refresh token object
        """
        self.refresh_tokens[token] = refresh_token

    def get_refresh_token(self, token: str) -> RefreshToken | None:
        """Get a refresh token by value.

        Args:
            token: The refresh token string

        Returns:
            The refresh token object or None if not found
        """
        return self.refresh_tokens.get(token)

    def delete_refresh_token(self, token: str) -> None:
        """Delete a refresh token.

        Args:
            token: The refresh token string
        """
        if token in self.refresh_tokens:
            del self.refresh_tokens[token]

    def store_access_token(self, token: str, access_token: AccessToken) -> None:
        """Store an access token.

        Args:
            token: The access token string
            access_token: The access token object
        """
        self.access_tokens[token] = access_token

    def get_access_token(self, token: str) -> AccessToken | None:
        """Get an access token by value.

        Args:
            token: The access token string

        Returns:
            The access token object or None if not found
        """
        return self.access_tokens.get(token)

    def delete_access_token(self, token: str) -> None:
        """Delete an access token.

        Args:
            token: The access token string
        """
        if token in self.access_tokens:
            del self.access_tokens[token]

    def store_provider_token(self, mcp_token: str, provider_token: str) -> None:
        """Store a provider token mapping.

        Args:
            mcp_token: The MCP token string
            provider_token: The provider token string (e.g., GitHub token)
        """
        self.provider_tokens[mcp_token] = provider_token

    def get_provider_token(self, mcp_token: str) -> str | None:
        """Get the provider token associated with an MCP token.

        This is a non-standard method to allow access to the provider token
        (e.g., GitHub token) for a given MCP token. This can be used by
        tools that need to access provider APIs.

        Args:
            mcp_token: The MCP token

        Returns:
            The provider token or None if not found
        """
        return self.provider_tokens.get(mcp_token)  # Changed from self.storage to self


class GolfOAuthProvider(OAuthAuthorizationServerProvider):
    """OAuth provider implementation for GolfMCP.

    This class implements the OAuthAuthorizationServerProvider interface
    for GolfMCP servers. It handles the OAuth 2.0 authentication flow,
    token management, and client registration.
    """

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize the provider.

        Args:
            config: The provider configuration
        """
        self.config = config
        self.storage = TokenStorage()
        self.state_mapping: dict[str, dict[str, Any]] = {}  # Initialize state_mapping

        # Register default client
        self._register_default_client()

    def _get_client_id(self) -> str:
        """Get the client ID from config or environment."""
        if self.config.client_id:
            return self.config.client_id

        if self.config.client_id_env_var:
            value = os.environ.get(self.config.client_id_env_var)
            if value:
                return value

        return "missing-client-id"

    def _get_client_secret(self) -> str:
        """Get the client secret from config or environment."""
        if self.config.client_secret:
            return self.config.client_secret

        if self.config.client_secret_env_var:
            value = os.environ.get(self.config.client_secret_env_var)
            if value:
                return value

        return "missing-client-secret"

    def _get_jwt_secret(self) -> str:
        """Get the JWT secret from config. It's expected to be resolved by server startup."""
        if self.config.jwt_secret:
            # _diag_logger.info(f"GolfOAuthProvider: Using JWT secret from config: {self.config.jwt_secret[:5]}...")
            return self.config.jwt_secret
        else:
            raise ValueError(
                "JWT Secret is not configured in the provider. Check server logs and environment variables."
            )

    def _register_default_client(self) -> None:
        """Register a default client for MCP."""
        # These are the URIs where *this server* is allowed to redirect an MCP client
        # after successful authentication and MCP auth code generation.
        client_redirect_uris = [
            # Common redirect URI for MCP Inspector running locally
            "http://localhost:5173/callback",
            "http://127.0.0.1:5173/callback",
            # A generic callback relative to the server's issuer URL, if needed by some clients
            # This assumes such a client-side endpoint exists.
            f"{self.config.issuer_url.rstrip('/') if self.config.issuer_url else 'http://localhost:3000'}/client/callback",
        ]

        default_client = OAuthClientInformationFull(
            client_id="default",
            client_name="Default MCP Client",
            client_secret="",  # Public client
            redirect_uris=client_redirect_uris,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",  # Public client
            scope=" ".join(self.config.scopes),
        )
        self.storage.store_client("default", default_client)

    def _generate_jwt(
        self, subject: str, scopes: list[str], expires_in: int = None
    ) -> str:
        """Generate a JWT token.

        Args:
            subject: The subject of the token (usually client_id)
            scopes: The scopes granted to the token
            expires_in: The token lifetime in seconds (or None for default)

        Returns:
            The signed JWT token
        """
        now = int(time.time())
        expiry = now + (expires_in or self.config.token_expiration)

        payload = {
            "iss": self.config.issuer_url or "golf:auth",
            "sub": subject,
            "iat": now,
            "exp": expiry,
            "scp": scopes,
        }

        jwt_secret = self._get_jwt_secret()
        return jwt.encode(payload, jwt_secret, algorithm="HS256")

    def _verify_jwt(self, token: str) -> dict[str, Any] | None:
        """Verify a JWT token."""
        jwt_secret = self._get_jwt_secret()  # Get secret first
        # _diag_logger.info(f"GolfOAuthProvider: _verify_jwt attempting to use secret: {jwt_secret[:5]}...")

        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                options={"verify_signature": True},
            )

            if payload.get("exp", 0) < time.time():
                exp_timestamp = payload.get("exp")
                current_timestamp = time.time()
                (
                    str(datetime.fromtimestamp(exp_timestamp))
                    if exp_timestamp is not None
                    else "N/A"
                )
                str(datetime.fromtimestamp(current_timestamp))
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.PyJWTError:
            return None
        except Exception:  # Catch any other unexpected error during decode
            return None

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Get client information by ID.

        Args:
            client_id: The client ID

        Returns:
            The client information or None if not found
        """
        return self.storage.get_client(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a new client."""
        # Add detailed logging at the beginning
        getattr(
            client_info, "client_id", "UNKNOWN (client_info has no client_id attribute)"
        )
        try:
            # Validate the client information
            if not client_info.client_id:
                raise RegistrationError(
                    error="invalid_client_metadata",
                    error_description="Client ID is missing in client_info provided to register_client",
                )

            if not client_info.redirect_uris:
                raise RegistrationError(
                    error="invalid_redirect_uri",
                    error_description="At least one redirect URI is required",
                )

            # Store the client
            self.storage.store_client(client_info.client_id, client_info)
        except Exception:
            raise  # Re-raise the exception so FastMCP can handle it

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,  # params from MCP client
    ) -> str:
        """Handle an authorization request.
        This method is called when an MCP client requests authorization.
        It should return a URL to redirect the user to the external IdP (e.g., GitHub).
        """
        import secrets
        import urllib.parse

        idp_flow_state = secrets.token_hex(16)
        mcp_client_original_state = params.state

        self.state_mapping[idp_flow_state] = {
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "code_challenge_method": (
                "S256" if params.code_challenge else None
            ),  # Store S256 if challenge exists, else None
            "scopes": params.scopes,
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "mcp_client_original_state": mcp_client_original_state,
        }

        # Use self.config.callback_path for consistency
        idp_callback_uri = (
            f"{self.config.issuer_url.rstrip('/')}{self.config.callback_path}"
        )

        client_id = self._get_client_id()

        auth_params_for_idp = {
            "client_id": client_id,
            "redirect_uri": idp_callback_uri,
            "scope": " ".join(self.config.scopes),
            "state": idp_flow_state,
            "response_type": "code",
        }

        if params.code_challenge:
            auth_params_for_idp["code_challenge"] = params.code_challenge
            # Always use S256 if a challenge is present, as it's the standard and what the client sends.
            auth_params_for_idp["code_challenge_method"] = "S256"

        query_for_idp = urllib.parse.urlencode(auth_params_for_idp)

        return f"{self.config.authorize_url}?{query_for_idp}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, code: str
    ) -> AuthorizationCode | None:
        """Load an authorization code.

        Args:
            client: The client information
            code: The authorization code

        Returns:
            The authorization code object or None if not found
        """
        auth_code = self.storage.get_auth_code(code)

        if not auth_code:
            return None

        # Verify the code belongs to this client
        if auth_code.client_id != client.client_id:
            return None

        # Verify the code hasn't expired
        if auth_code.expires_at and auth_code.expires_at < datetime.now().timestamp():
            self.storage.delete_auth_code(code)
            return None

        return auth_code

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        code: AuthorizationCode,  # This is AuthorizationCode object
    ) -> OAuthToken:
        """Exchange an authorization code for tokens.

        Args:
            client: The client information
            code: The authorization code object

        Returns:
            The OAuth token response

        Raises:
            TokenError: If the code exchange fails
        """
        # Retrieve the provider token that was stored temporarily during callback
        provider_token = self.storage.get_provider_token_for_auth_code(code.code)

        # Delete the code and its mapping to ensure one-time use
        self.storage.delete_auth_code(code.code)  # This now also deletes the mapping

        # Generate an access token
        access_token_str = self._generate_jwt(  # Renamed for clarity
            subject=client.client_id, scopes=code.scopes
        )

        # Generate a refresh token if needed
        refresh_token_str = (
            str(uuid.uuid4()) if "refresh_token" in client.grant_types else None
        )  # Renamed for clarity

        # Store the mapping from our new MCP access token to the provider's access token
        if provider_token and access_token_str:
            self.storage.store_provider_token(access_token_str, provider_token)

        # Store the tokens
        if refresh_token_str:
            self.storage.store_refresh_token(
                refresh_token_str,
                RefreshToken(
                    token=refresh_token_str,
                    client_id=client.client_id,
                    scopes=code.scopes,
                    expires_at=int(
                        datetime.now().timestamp() + (self.config.token_expiration * 24)
                    ),  # 24x longer, cast to int
                ),
            )

        # Store access token information for validation later
        # Note: For JWTs, we might not need to store them if we can verify the signature
        self.storage.store_access_token(
            access_token_str,
            AccessToken(
                token=access_token_str,
                client_id=client.client_id,
                scopes=code.scopes,
                expires_at=int(
                    datetime.now().timestamp() + self.config.token_expiration
                ),  # Cast to int
            ),
        )

        # Create and return the OAuth token response
        return OAuthToken(
            access_token=access_token_str,
            token_type="bearer",
            expires_in=self.config.token_expiration,
            refresh_token=refresh_token_str,
            scope=" ".join(code.scopes),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        """Load a refresh token.

        Args:
            client: The client information
            refresh_token: The refresh token string

        Returns:
            The refresh token object or None if not found
        """
        token = self.storage.get_refresh_token(refresh_token)

        if not token:
            return None

        # Verify the token belongs to this client
        if token.client_id != client.client_id:
            return None

        # Verify the token hasn't expired
        if token.expires_at and token.expires_at < datetime.now().timestamp():
            self.storage.delete_refresh_token(refresh_token)
            return None

        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Exchange a refresh token for a new token pair.

        Args:
            client: The client information
            refresh_token: The refresh token object
            scopes: The requested scopes (may be a subset of original)

        Returns:
            The new OAuth token response

        Raises:
            TokenError: If the token exchange fails
        """
        # Delete the old refresh token (implement token rotation for security)
        self.storage.delete_refresh_token(refresh_token.token)

        # Determine the scopes for the new token
        # If requested scopes are provided, they must be a subset of the original
        if scopes:
            valid_scopes = [s for s in scopes if s in refresh_token.scopes]
            if not valid_scopes:
                valid_scopes = refresh_token.scopes
        else:
            valid_scopes = refresh_token.scopes

        # Generate a new access token
        access_token = self._generate_jwt(subject=client.client_id, scopes=valid_scopes)

        # Generate a new refresh token
        new_refresh_token = str(uuid.uuid4())

        # Find the provider token if it exists from the old access token
        # Note: This assumes each refresh generates only one access token
        old_access_tokens = [
            token
            for token, data in self.storage.access_tokens.items()
            if data.client_id == client.client_id
        ]
        provider_token = None
        for old_token in old_access_tokens:
            provider_token = self.storage.get_provider_token(old_token)
            if provider_token:
                # Store the provider token mapping for the new access token
                self.storage.store_provider_token(access_token, provider_token)
                break

        # Store the new tokens
        self.storage.store_refresh_token(
            new_refresh_token,
            RefreshToken(
                token=new_refresh_token,
                client_id=client.client_id,
                scopes=valid_scopes,
                expires_at=int(
                    datetime.now().timestamp() + (self.config.token_expiration * 24)
                ),  # Cast to int
            ),
        )

        # Store access token information
        self.storage.store_access_token(
            access_token,
            AccessToken(
                token=access_token,
                client_id=client.client_id,
                scopes=valid_scopes,
                expires_at=int(
                    datetime.now().timestamp() + self.config.token_expiration
                ),  # Cast to int
            ),
        )

        # Create and return the OAuth token response
        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.config.token_expiration,
            refresh_token=new_refresh_token,
            scope=" ".join(valid_scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load and validate an access token."""

        payload = self._verify_jwt(token)
        if not payload:
            return None

        client_id = payload.get("sub")
        scopes = payload.get("scp", [])
        expires_at = payload.get("exp")

        access_token_obj = AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(expires_at) if expires_at is not None else None,
        )

        return access_token_obj

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """Revoke a token.

        Args:
            token: The token to revoke (access or refresh)
        """
        # Try to revoke as access token
        self.storage.delete_access_token(token.token)

        # Try to revoke as refresh token
        self.storage.delete_refresh_token(token.token)

        # Clean up provider token mapping if it exists
        provider_token = self.storage.get_provider_token(token.token)
        if provider_token:
            self.storage.provider_tokens.pop(token.token, None)

    def get_provider_token(self, mcp_token: str) -> str | None:
        """Get the provider token associated with an MCP token.

        This is a non-standard method to allow access to the provider token
        (e.g., GitHub token) for a given MCP token. This can be used by
        tools that need to access provider APIs.

        Args:
            mcp_token: The MCP token

        Returns:
            The provider token or None if not found
        """
        return self.storage.get_provider_token(mcp_token)


def create_callback_handler(provider: GolfOAuthProvider):
    """Create a callback handler for OAuth authorization.

    This function creates a callback handler that can be used to handle
    the OAuth callback from the provider (e.g., GitHub).

    Args:
        provider: The OAuth provider

    Returns:
        An async function that handles the callback
    """

    async def handle_callback(request):
        """Handle the OAuth callback.

        Args:
            request: The HTTP request

        Returns:
            The HTTP response
        """
        # Extract the code and state from the request
        idp_auth_code = request.query_params.get(
            "code"
        )  # Renamed for clarity: code from IdP
        idp_state = request.query_params.get(
            "state"
        )  # Renamed for clarity: state from IdP

        if not idp_auth_code:
            return RedirectResponse(
                "/auth-error?error=no_code_from_idp"
            )  # More specific error

        # Use provider.config.callback_path for consistency
        # This is the redirect_uri registered with the IdP and used in the /authorize step
        idp_callback_uri_for_token_exchange = (
            f"{provider.config.issuer_url.rstrip('/')}{provider.config.callback_path}"
        )

        client_id_for_idp = provider._get_client_id()
        client_secret_for_idp = provider._get_client_secret()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider.config.token_url,
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id_for_idp,
                    "client_secret": client_secret_for_idp,
                    "code": idp_auth_code,  # Use code from IdP
                    "redirect_uri": idp_callback_uri_for_token_exchange,
                },
            )

            if response.status_code != 200:
                error_detail = response.text[:200]  # Limit error detail length
                return RedirectResponse(
                    f"/auth-error?error=idp_token_exchange_failed&detail={urllib.parse.quote(error_detail)}"
                )

            # Get the provider token from the response
            token_data = response.json()
            provider_access_token = token_data.get(
                "access_token"
            )  # This is the token from GitHub/Google etc.

            if not provider_access_token:
                return RedirectResponse("/auth-error?error=no_access_token_from_idp")

        try:
            # Get user information from the provider using the token (optional step)
            # user_info = None (keep this if user_info is used later, otherwise remove)
            # ... (userinfo fetching logic if needed) ...

            original_mcp_client_details = provider.state_mapping.pop(
                idp_state, None
            )  # Use state from IdP
            if not original_mcp_client_details:
                return RedirectResponse("/auth-error?error=invalid_idp_state")

            original_mcp_client_id = original_mcp_client_details["client_id"]
            original_mcp_redirect_uri = original_mcp_client_details[
                "redirect_uri"
            ]  # MCP client's redirect_uri
            original_code_challenge = original_mcp_client_details["code_challenge"]
            original_code_challenge_method = original_mcp_client_details[
                "code_challenge_method"
            ]

            requested_scopes_for_mcp_server_str = original_mcp_client_details["scopes"]
            mcp_client_original_state_to_pass_back = original_mcp_client_details.get(
                "mcp_client_original_state"
            )
            original_redirect_uri_provided_explicitly = original_mcp_client_details[
                "redirect_uri_provided_explicitly"
            ]

            mcp_client = await provider.get_client(
                original_mcp_client_id
            )  # Renamed for clarity
            if not mcp_client:
                return RedirectResponse(
                    "/auth-error?error=mcp_client_not_found_post_callback"
                )

            final_scopes_for_mcp_auth_code: list[str]
            if requested_scopes_for_mcp_server_str:  # Scopes requested by MCP client
                final_scopes_for_mcp_auth_code = (
                    requested_scopes_for_mcp_server_str.split()
                )
            else:  # Default to client's registered scopes if none explicitly requested
                final_scopes_for_mcp_auth_code = (
                    mcp_client.scope.split() if mcp_client.scope else []
                )

            # This is the auth code our GolfMCP server issues to the MCP client
            mcp_auth_code_str = str(uuid.uuid4())

            # Store the mapping from our mcp_auth_code_str to the provider_access_token (e.g., GitHub token)
            # This will be retrieved when the MCP client exchanges mcp_auth_code_str for an MCP access token
            provider.storage.store_auth_code_provider_token_mapping(
                mcp_auth_code_str, provider_access_token
            )

            # Create the AuthorizationCode object for our server
            mcp_auth_code_obj = AuthorizationCode(  # Renamed for clarity
                code=mcp_auth_code_str,
                client_id=mcp_client.client_id,
                redirect_uri=original_mcp_redirect_uri,
                scopes=final_scopes_for_mcp_auth_code,
                expires_at=int(
                    datetime.now().timestamp() + 600
                ),  # 10 minutes, cast to int
                redirect_uri_provided_explicitly=original_redirect_uri_provided_explicitly,
                code_challenge=original_code_challenge,
                code_challenge_method=original_code_challenge_method,
            )

            # Store our auth code object (without provider_token as an attribute)
            provider.storage.store_auth_code(mcp_auth_code_str, mcp_auth_code_obj)

            query_params_for_mcp_client = {
                "code": mcp_auth_code_str  # Send our generated auth code to the MCP client
            }
            if mcp_client_original_state_to_pass_back:
                query_params_for_mcp_client["state"] = (
                    mcp_client_original_state_to_pass_back
                )

            import urllib.parse  # Ensure it's imported here too

            final_query_for_mcp_client = urllib.parse.urlencode(
                query_params_for_mcp_client
            )
            final_redirect_to_mcp_client = (
                f"{original_mcp_redirect_uri}?{final_query_for_mcp_client}"
            )

            return RedirectResponse(final_redirect_to_mcp_client)

        except Exception:
            # Avoid sending raw exception details to the client for security
            return RedirectResponse(
                "/auth-error?error=callback_processing_failed&detail=internal_server_error"
            )

    return handle_callback
