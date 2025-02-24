from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
from ...core.config import get_settings
from ...core.logging.logging import log_service

settings = get_settings()

class CORSMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Parse CORS settings from environment
        self.allowed_origins = json.loads(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, str) else settings.CORS_ORIGINS
        self.allowed_methods = json.loads(settings.CORS_METHODS) if isinstance(settings.CORS_METHODS, str) else settings.CORS_METHODS
        self.allowed_headers = json.loads(settings.CORS_HEADERS) if isinstance(settings.CORS_HEADERS, str) else settings.CORS_HEADERS
        self.allow_credentials = settings.CORS_CREDENTIALS if not isinstance(settings.CORS_CREDENTIALS, str) else settings.CORS_CREDENTIALS.lower() == "true"

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")

        if not origin:
            return await call_next(request)

        allowed_origin = self._get_allow_origin(origin)
        
        if request.method == "OPTIONS":
            response = Response()
        else:
            response = await call_next(request)

        if allowed_origin:
            # Set CORS headers
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
            response.headers["Access-Control-Max-Age"] = "3600"
            response.headers["Vary"] = "Origin"
            
            # Prevent caching
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    def _get_allow_origin(self, origin: str) -> str:
        # Direct match
        if origin in self.allowed_origins:
            return origin
            
        # Handle localhost variations
        if origin.startswith(("http://localhost", "http://127.0.0.1")):
            log_service.log_event(
                "cors_localhost_match",
                {"origin": origin}
            )
            return origin
            
        # Handle wildcard domains
        for allowed in self.allowed_origins:
            if allowed.startswith("https://*."):
                domain = allowed.replace("https://*.", "")
                if origin.endswith(f".{domain}"):
                    log_service.log_event(
                        "cors_wildcard_match",
                        {
                            "origin": origin,
                            "pattern": allowed,
                            "domain": domain
                        }
                    )
                    return origin
        
        log_service.log_event(
            "cors_origin_rejected",
            {"origin": origin}
        )
        return ""