import logging
from typing import Callable, List, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from authed.sdk import Authed

logger = logging.getLogger(__name__)

class AuthedMiddleware(BaseHTTPMiddleware):
    """Middleware that adds Authed authentication to MCP servers.
    
    This middleware can be configured to:
    1. Require Authed auth for all endpoints
    2. Allow fallback to non-Authed connections
    3. Only apply to specific paths
    """
    
    def __init__(
        self, 
        app, 
        authed: Authed,
        require_auth: bool = True,
        exclude_paths: Optional[List[str]] = None,
        debug: bool = False
    ):
        """
        Initialize the Authed middleware.
        
        Args:
            app: The ASGI application
            authed: Initialized Authed SDK instance
            require_auth: If True, all requests must be authenticated with Authed
                         If False, will allow requests without Authed auth (fallback mode)
            exclude_paths: List of paths to exclude from authentication
            debug: Enable debug logging
        """
        super().__init__(app)
        self.authed = authed
        self.require_auth = require_auth
        self.exclude_paths = exclude_paths or []
        self.debug = debug
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Skip auth for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            if self.debug:
                logger.debug(f"Skipping auth for excluded path: {request.url.path}")
            return await call_next(request)
        
        if self.debug:
            logger.debug(f"Verifying request to {request.url.path}")
            logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Check for Authed Authentication headers
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        has_authed_headers = auth_header is not None
        
        if not has_authed_headers:
            if self.debug:
                logger.debug("Request doesn't have auth headers")
            
            if self.require_auth:
                # If auth is required, reject the request
                return JSONResponse(
                    content={"error": "Unauthorized - Missing Authed authentication"},
                    status_code=401
                )
            else:
                # If auth is not required, allow the request to proceed
                if self.debug:
                    logger.debug("Allowing non-authenticated request (fallback mode)")
                request.state.authenticated = False
                return await call_next(request)
        
        # We have auth headers, so verify them
        auth_handler = self.authed.auth
        
        try:
            # Use the SDK's verify_request method
            is_valid = await auth_handler.verify_request(
                request.method,
                str(request.url),
                dict(request.headers)
            )
            
            if not is_valid:
                if self.debug:
                    logger.debug("Authed authentication failed")
                
                if self.require_auth:
                    return JSONResponse(
                        content={"error": "Unauthorized - Invalid Authed authentication"},
                        status_code=401
                    )
                else:
                    # If fallback is allowed, let the request proceed but mark as not authenticated
                    if self.debug:
                        logger.debug("Allowing request with invalid auth (fallback mode)")
                    request.state.authenticated = False
                    return await call_next(request)
            
            # Auth succeeded, add info to request state
            request.state.authenticated = True
            if self.debug:
                logger.debug(f"Authentication successful for {request.url.path}")
            
            # Call the next middleware or endpoint
            return await call_next(request)
        
        except TypeError as e:
            # Handle specific errors like quote_from_bytes
            logger.error(f"Type error in authentication: {str(e)}")
            if "quote_from_bytes" in str(e) and not self.require_auth:
                # This is a known error with URL quoting - allow through if auth not required
                request.state.authenticated = False
                return await call_next(request)
            elif self.require_auth:
                return JSONResponse(
                    content={"error": f"Authentication error: {str(e)}"},
                    status_code=401
                )
            else:
                # If fallback is allowed, let the request proceed but mark as not authenticated
                if self.debug:
                    logger.debug(f"Allowing request despite auth error: {str(e)} (fallback mode)")
                request.state.authenticated = False
                return await call_next(request)
            
        except Exception as e:
            # Handle authentication errors
            logger.error(f"Authentication error: {str(e)}")
            
            if self.require_auth:
                return JSONResponse(
                    content={"error": f"Authentication failed: {str(e)}"},
                    status_code=401
                )
            else:
                # If fallback is allowed, let the request proceed but mark as not authenticated
                if self.debug:
                    logger.debug(f"Allowing request despite auth error: {str(e)} (fallback mode)")
                request.state.authenticated = False
                return await call_next(request)
