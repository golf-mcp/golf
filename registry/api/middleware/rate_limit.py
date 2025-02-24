from datetime import UTC, datetime
from fastapi import Request 
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ...core.config import get_settings
from ...core.logging.logging import log_service
from ...core.logging.models import LogLevel
from ...db.redis import get_redis_client

settings = get_settings()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.redis = get_redis_client() if self.settings.ENV != "test" else None
        self.window_size = settings.RATE_LIMIT_WINDOW
        
        # Set rate limits
        if self.settings.ENV == "test":
            self.max_requests = {
                "token": 100,
                "verify": 100,
                "register": 100,
                "providers/register": 100,
                "api/v1/providers/register": 100,
                "default": 100
            }
            self.default_limit = 100
        else:
            self.max_requests = {
                "token": settings.RATE_LIMIT_TOKEN,
                "verify": settings.RATE_LIMIT_VERIFY,
                "register": settings.RATE_LIMIT_REGISTER,
                "providers/register": settings.RATE_LIMIT_REGISTER,
                "api/v1/providers/register": settings.RATE_LIMIT_REGISTER,
                "default": settings.RATE_LIMIT_DEFAULT
            }
            self.default_limit = settings.RATE_LIMIT_DEFAULT

    async def dispatch(self, request: Request, call_next):
        """Check if request is within rate limits"""
        # Skip all rate limiting in test environment
        if self.settings.ENV == "test":
            return await call_next(request)
            
        # Initialize variables outside try block
        agent_id = request.headers.get("agent-id")
        provider_id = None
        
        # Extract provider ID from path for provider endpoints
        if request.url.path.startswith("/providers/"):
            parts = request.url.path.split("/")
            if len(parts) >= 3:
                provider_id = parts[2]  # /providers/{id}/...
        
        # Skip rate limiting for endpoints that don't require auth
        public_paths = [
            "/health"
        ]
        
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)
        
        try:
            now = datetime.now(UTC).timestamp()
            
            # Get the full path and try different variations
            full_path = request.url.path.strip("/")
            path_parts = full_path.split("/")
            
            log_service.log_event(
                "rate_limit_debug",
                {
                    "path": full_path,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "agent_id": agent_id,
                    "provider_id": provider_id
                },
                level=LogLevel.DEBUG
            )
            
            # Try most specific to least specific paths
            possible_paths = [
                full_path,  # Full path: api/v1/providers/register
                "/".join(path_parts[-2:]),  # providers/register
                path_parts[-1],  # register
            ]
            
            # Find the most specific matching path
            limit_key = next(
                (path for path in possible_paths if path in self.max_requests),
                path_parts[-1]  # fallback to last segment
            )
            
            # Check rate limits based on agent or provider ID
            if not agent_id and not provider_id:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing authentication"}
                )

            # Set up Redis keys
            keys = []
            if agent_id:
                keys.append(f"rate_limit:agent:{agent_id}:{limit_key}")
            if provider_id:
                keys.append(f"rate_limit:provider:{provider_id}:{limit_key}")

            # Check all applicable rate limits
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.zremrangebyscore(key, 0, now - self.window_size)
                pipe.zcard(key)
            results = pipe.execute()

            # Get request counts (every other result is a count)
            request_counts = results[1::2]
            limit = self.max_requests.get(limit_key, self.default_limit)

            # Check if any limit is exceeded
            if any(count >= limit for count in request_counts):
                log_service.log_event(
                    "rate_limit_exceeded",
                    {
                        "agent_id": agent_id,
                        "provider_id": provider_id,
                        "path": full_path,
                        "requests": max(request_counts),
                        "limit": limit
                    },
                    level=LogLevel.ERROR
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"}
                )

            # Add this request to all applicable counters
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, self.window_size)
            pipe.execute()

            return await call_next(request)

        except Exception as e:
            log_service.log_event(
                "rate_limit_error",
                {
                    "error": str(e),
                    "agent_id": agent_id,
                    "provider_id": provider_id
                },
                level=LogLevel.ERROR
            )
            return await call_next(request) 