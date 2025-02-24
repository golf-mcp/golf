from .routes import api_router
from fastapi import FastAPI

def init_api(app: FastAPI):
    # Add routes without prefix
    app.include_router(api_router)

__all__ = ['init_api'] 