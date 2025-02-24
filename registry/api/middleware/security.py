from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException

from ...core.config import get_settings
from ...core.logging.logging import log_service

settings = get_settings()

class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.min_tls_version = settings.MIN_TLS_VERSION
        self.secure_ciphers = settings.SECURE_CIPHERS
        self.csp_policy = settings.CSP_POLICY
        self.env = settings.ENV

    async def dispatch(self, request: Request, call_next):
        # Only enforce TLS in production
        if self.env == "production":
            protocol = request.headers.get("X-Forwarded-Proto", "http")
            if protocol != "https":
                raise HTTPException(status_code=400, detail="HTTPS required")

            # Get TLS version from headers (set by reverse proxy)
            tls_version = request.headers.get("X-TLS-Version")
            if not tls_version or tls_version < self.min_tls_version:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported TLS version"
                )

        response = await call_next(request)
        
        # Don't add security headers for OPTIONS requests
        if request.method == "OPTIONS":
            return response
            
        # Security Headers - more lenient in development
        headers = {
            # HTTPS enforcement - only in production
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload" if self.env == "production" else "",
            
            # Content type protection
            "X-Content-Type-Options": "nosniff",
            
            # Frame protection - allow in development
            "X-Frame-Options": "DENY" if self.env == "production" else "SAMEORIGIN",
            
            # XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer Policy - more lenient in development
            "Referrer-Policy": "strict-origin-when-cross-origin" if self.env == "production" else "no-referrer-when-downgrade",
        }
        
        # Only add non-empty headers
        response.headers.update({k: v for k, v in headers.items() if v})
        
        # Add CSP only in production
        if self.env == "production":
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        return response 