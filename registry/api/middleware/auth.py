from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException

from ...services.agent_service import AgentService 
from ...services.provider_service import ProviderService
from ...core.config import get_settings

agent_service = AgentService()
provider_service = ProviderService()
settings = get_settings()

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Skip auth for public endpoints
        public_paths = [
            "/health",
            "/agents/register"  # Keep agent registration public
        ]
        
        path = request.url.path
        if any(path.startswith(public_path) for public_path in public_paths):
            return await call_next(request)

        # Check for internal API key first - if present and valid, allow all requests
        api_key = request.headers.get("x-api-key")
        if api_key:
            if not settings.INTERNAL_API_KEY:
                raise HTTPException(
                    status_code=500,
                    detail="Internal API key not configured"
                )
            if api_key == settings.INTERNAL_API_KEY:
                return await call_next(request)
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        # For all protected routes, require provider auth
        if path.startswith("/providers/") or path.startswith("/agents/") or path.startswith("/logs"):
            provider_secret = request.headers.get("provider-secret")
            if not provider_secret:
                raise HTTPException(
                    status_code=401,
                    detail="Provider authentication required"
                )
            
            provider = provider_service.get_provider_by_secret(provider_secret)
            if not provider:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid provider credentials"
                )
                
            # Store provider in request state for use in endpoints
            request.state.provider = provider
            return await call_next(request)
            
        # Allow other requests to proceed
        return await call_next(request) 