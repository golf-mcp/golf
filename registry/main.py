from fastapi import FastAPI
from contextlib import asynccontextmanager
from .api import init_api
from .api.middleware.security import SecurityMiddleware
from .api.middleware.auth import AuthMiddleware
from .api.middleware.rate_limit import RateLimitMiddleware
from .api.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .db import initialize_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database with all models
    initialize_models()
    # Then initialize the app
    yield
    # Cleanup

def create_app() -> FastAPI:
    # Get fresh settings
    settings = get_settings()
    
    app = FastAPI(
        title="Agent Registry API",
        description="API for managing agent registrations and tokens",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add middleware in order (last added = first executed)
    app.add_middleware(CORSMiddleware)       # CORS
    app.add_middleware(SecurityMiddleware)    # Security headers
    app.add_middleware(AuthMiddleware)        # Authentication
    app.add_middleware(RateLimitMiddleware)   # Rate limiting last so it's executed first
    
    # Initialize API routes
    init_api(app)
    
    return app

app = create_app()




