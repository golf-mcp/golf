from fastapi import APIRouter
from .agents import router as agents_router
from .providers import router as providers_router
from .tokens import router as tokens_router
from .logs import router as logs_router
from .health import router as health_router

api_router = APIRouter()

api_router.include_router(agents_router)
api_router.include_router(providers_router)
api_router.include_router(tokens_router)
api_router.include_router(logs_router)
api_router.include_router(health_router)

__all__ = ['api_router'] 